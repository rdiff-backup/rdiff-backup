/*				       	-*- c-file-style: "bsd" -*-
 *
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool
 * Copyright (C) 1998 by Andrew Tridgell 
 * 
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

/* Originally from rsync.  Thanks, tridge! */

/* MAP POINTERS:
  
   This provides functionality somewhat similar to mmap() but using
   read(). It gives sliding window access to a file. With certain
   constraints, this is suitable for use on sockets and similar things
   that cannot normally support seek or mmap. Specifically, the caller
   must never attempt to move backwards or to skip forwards without
   reading.  Both of these are implicitly true for libhsync when
   interacting with a socket.

   It's not an error to try to map past the end of a file.  If you do
   this, the map will run up to the end of the file, and a flag will
   be returned to indicate that EOF was observed.  This will be
   checked each time you try to map past the end, so something good
   will happen if the file grows underneath you.

   If the file is open with O_NONBLOCK, then the operating system may
   choose to fail an attempt to read, saying that it would block.  In
   this case, the map will not not fail, but it will indicate that
   zero bytes are available.  The caller should be smart about doing a
   select(2) on the fd and calling back when more data is
   available. */


/* TODO: Test this through a unix-domain or TCP localhost socket and
 * see what happens.
 * 
 * TODO: Optionally debug this by simulating short reads.
 *
 * TODO: Make the default buffer smaller and make sure we test what
 * happens when it grows.
 *
 * TODO: Add an option to say we will never seek backwards, and so old
 * data can be discarded immediately.
 *
 * TODO: Is it really worth the trouble of handling files that grow?
 * */

/* The Unix98 pread(2) function is pretty interesting: it reads data
 * at a given offset, but without moving the file offset and in only a
 * single call.  Cute, but probably pointless in this application. */

/* mapptr is fine, but it's not optimized for reading from a socket into
 * nad.
 *
 * What's wrong?
 *
 * mapptr has the problem in this situation that it will try to read
 * more data than is strictly required, and this damages liveness.
 * Also, though this is less important, it retains old data in the
 * buffer even when we know we won't use it, and this is bad.
 *
 * On the other hand perhaps having less code is more important than
 * all the code being optimal. */


/*----------------------------------------------------------------------
 *
 *  ====================================================  file
 *     ||||||||||||||||||||||||||||||||||||||||||         buffer
 *             $$$$$$$$$$$$$$$$$$$$$$$$$$                 window
 *
 * We have three overlapping extents here: the file is the sequence of
 * bytes from the stream.  The buffer covers a certain region of it,
 * but not all of the buffer is necessarily valid.  The window is the
 * section of the buffer that contains valid data. */


#include "includes.h"

#define CHUNK_SIZE (1024)
#define IO_BUFFER_SIZE (4092)

/* We'll read data in windows of this size, unless otherwise indicated. */
#if HS_BIG_WINDOW
static ssize_t const DEFAULT_WINDOW_SIZE = (ssize_t) (256 * 1024);
#else
static ssize_t const DEFAULT_WINDOW_SIZE = (ssize_t) (16 * 1024);
#endif
static int const HS_MAP_TAG = 189900;


/* 
   HS_MAP structure:
  
   TAG is a dogtag, and always equal to HS_MAP_TAG if the structure is
   valid.  FD is of course the file descriptor we're using for input.
  
   P points to the start of the allocated data buffer.  P_SIZE is the
   amount of allocated buffer at P, not all of which necessarily
   contains valid file data.
  
   P_FD_OFFSET is the current absolute position of the file cursor.
   We use this to avoid doing seeks if we're already in the right
   position.  P_OFFSET is the absolute position in the file covered by
   P[0].  P_LEN is the number of bytes after that point that are valid
   in P.
 */
struct hs_map {
    int             tag;
    /*@null@*/ char *p;
    int             fd;
    ssize_t	    p_size, p_len;
    hs_off_t        p_offset, p_fd_offset;
};


/* Set up a new file mapping.
  
   The file cursor is assumed to be at position 0 when this is called.
   For nonseekable files this is arbitrary; for seekable files bad
   things will happen if that's not true and we later have to seek. */
hs_map_t *
_hs_map_file(int fd)
{
    hs_map_t       *map;

    map = _hs_alloc_struct(hs_map_t);

    map->tag = HS_MAP_TAG;
    map->fd = fd;
    map->p = NULL;
    map->p_size = 0;
    map->p_offset = 0;
    map->p_fd_offset = 0;
    map->p_len = 0;

    return map;
}


/* Read data into MAP at &p[READ_OFFSET].  Return the number of bytes
   added to the buffer, and set REACHED_EOF if appropriate.

   The amount of data is specified in an opportunistic, lazy way, with
   the idea being that we make IO operations as large as possible
   without blocking for any longer than is necessary when waiting for
   data from a network.

   Therefore, the function tries to read at least MIN_SIZE bytes,
   unless it encounters an EOF or error.  It reads up to MAX_SIZE
   bytes, and there must be that much space in the buffer.  Once
   MIN_SIZE bytes have been received, no new IO operations will
   start. */
static ssize_t
_hs_map_do_read(hs_map_t *map,
		hs_off_t const read_offset,
		ssize_t const max_size, ssize_t const min_size,
		int *reached_eof)
{
    ssize_t total_read = 0;	/* total amount read in */
    ssize_t nread;
    ssize_t buf_remain = max_size; /* buffer space left */
    char *p = map->p + read_offset;

    assert(max_size > 0);
    assert(min_size >= 0);
    assert(read_offset >= 0);
    assert(map->tag == HS_MAP_TAG);
    
    do {
	nread = read(map->fd, p, (size_t) buf_remain);

	_hs_trace("tried to read %ld bytes, result %ld",
		  (long) buf_remain, (long) nread);

	if (nread < 0  &&  errno == EWOULDBLOCK) {
	    _hs_trace("input from this file would block");
	    break; /* go now */
	} else if (nread < 0) {
	    _hs_error("read error in hs_mapptr: %s", strerror(errno));
	    /* Should we return null here?  We ought to tell the
               caller about this somehow, but at the same time we
               don't want to discard the data we have already
               received. */
	    break;
	} else if (nread == 0) {
	    /* GNU libc manual: A value of zero indicates end-of-file
	     * (except if the value of the SIZE argument is also
	     * zero).  This is not considered an error.  If you keep
	     * *calling `read' while at end-of-file, it will keep
	     * returning zero and doing nothing else.  */
	    *reached_eof = 1;
	    break;
	}

	total_read += nread;
	p += nread;
	buf_remain -= nread;
    } while (total_read < min_size);

    _hs_trace("wanted %ld to %ld bytes, read %ld bytes%s",
	      (long) min_size, (long) max_size, (long) total_read,
	      *reached_eof ? ", now at eof" : "");

    return total_read;
}


/* Return a pointer to a mapped region of a file, of at least LEN
   bytes.  You can read from (but not write to) this region just as if
   it were mmap'd.
  
   If the file reaches EOF, then the region mapped may be less than is
   requested.  In this case, LEN will be reduced, and REACHED_EOF will
   be set.

   LEN may be increased if more data than you requested is
   available.

   The buffer is only valid until the next call to _hs_map_ptr on this
   map, or until _hs_unmap_file.  You certainly MUST NOT free the
   buffer.

   Iff an error occurs, returns NULL. */
/*@null@*/ const char *
_hs_map_ptr(hs_map_t * map, hs_off_t offset, ssize_t *len, int *reached_eof)
{
    /* window_{start,size} define the part of the file that will in
       the future be covered by the map buffer, if we have our way.

       read_{start,size} describes the region of the file that we want
       to read; we'll put it into the buffer starting at
       &p[read_offset]. */
    hs_off_t window_start, read_start;
    ssize_t window_size;
    ssize_t read_max_size;	/* space remaining */
    ssize_t read_min_size;	/* needed to fill this request */
    hs_off_t read_offset;
    ssize_t total_read, avail;

    assert(map->tag == HS_MAP_TAG);
    assert(len != NULL);	/* check pointers */
    assert(reached_eof != NULL);
    assert(offset >= 0);
    assert(*len > 0);
    *reached_eof = 0;

    _hs_trace("off=%ld, len=%ld",
	      map, (long) offset, (long) *len);

    /* in most cases the region will already be available */
    if (offset >= map->p_offset &&
	offset + *len <= map->p_offset + map->p_len) {
/*   	_hs_trace("region is already in the buffer"); */
	*len = map->p_len - (offset - map->p_offset);
	return (map->p + (offset - map->p_offset));
    }


    if (offset > (hs_off_t) (2 * CHUNK_SIZE)) {
	/* On some systems, it's much faster to do reads aligned with
	 * filesystem blocks.  This isn't the case on Linux, which has
	 * a pretty efficient filesystem and kernel/app interface, but
	 * we don't lose a lot by checking this. */
	window_start = offset - 2 * CHUNK_SIZE;
	
	/* Include only higher-order bits; assumes power of 2 */
	window_start &= ~((hs_off_t) (CHUNK_SIZE - 1));	
    } else {
	window_start = 0;
    }
    window_size = DEFAULT_WINDOW_SIZE;

    /* If the default window is not big enough to hold all the data,
       then expand it. */
    if (offset + *len > window_start + window_size) {
	window_size = (offset + *len) - window_start;
    }

    /* make sure we have allocated enough memory for the window */
    if (!map->p) {
	assert(map->p_size == 0);
	_hs_trace("allocate initial %ld byte window", (long) window_size);
	map->p = (char *) malloc((size_t) window_size);
	map->p_size = window_size;
    } else if (window_size > map->p_size) {
	_hs_trace("grow buffer to hold %ld byte window", (long) window_size);
	map->p = (char *) realloc(map->p, (size_t) window_size);
	map->p_size = window_size;
    }

    if (!map->p) {
	_hs_fatal("map_ptr: out of memory");
    }

    /* now try to avoid re-reading any bytes by reusing any bytes from the
     * previous buffer. */
    if (window_start >= map->p_offset &&
	window_start < map->p_offset + map->p_len &&
	window_start + window_size >= map->p_offset + map->p_len) {
	read_start = map->p_offset + map->p_len;
	read_offset = read_start - window_start;
	assert(read_offset >= 0);
	read_max_size = window_size - read_offset;
	memmove(map->p, map->p + (map->p_len - read_offset),
		(size_t) read_offset);
    } else {
	read_start = window_start;
	read_max_size = window_size;
	read_offset = 0;
    }

    map->p_offset = window_start;

    if (read_max_size <= 0) {
	_hs_trace("Warning: unexpected read size of %d in map_ptr\n",
		  read_max_size);
	return NULL;
    }

    if (map->p_fd_offset != read_start) {
	if (lseek(map->fd, read_start, SEEK_SET) != read_start) {
	    _hs_trace("lseek failed in map_ptr\n");
	    abort();
	}
	map->p_fd_offset = read_start;
    }

    /* Work out the minimum number of bytes we must read to cover the
       requested region. */
    read_min_size = *len + (offset - map->p_offset) - read_offset;
    assert(read_min_size >= 0);

    /* read_min_size may be >*len when offset > map->p_offset, i.e. we
       have to read in some data before the stuff the caller wants to
       see.  We read it anyhow to avoid seeking (in the case of a
       pipe) or because they might want to go back and see it later
       (in a file). */

    if (read_min_size > read_max_size) {
	_hs_fatal("we really screwed up: minimum size is %ld, but remaining "
		  "buffer is just %ld",
		  (long) read_min_size, (long) read_max_size);
    }
    
    total_read = _hs_map_do_read(map, read_offset, read_max_size,
				 read_min_size, reached_eof);
    assert(*reached_eof  ||  total_read >= read_min_size);
    map->p_fd_offset += total_read;

    /* If we didn't map all the data we wanted because we ran into * EOF,
     * then adjust everything so that the map doesn't hang out * over the end 
     * of the file.  */

    /* Amount of data now valid: the stuff at the start of the buffer * from
     * last time, plus the data now read in. */
    map->p_len = read_offset + total_read;

    if (total_read == read_max_size) {
	/* This was the formula before we worried about EOF, so assert
	 * that it's still the same. */
	assert(map->p_len == window_size);
    }

    /* Available data after the requested offset: we have p_len bytes *
     * altogether, but the client is interested in the ones starting * at
     * &p[offset - map->p_offset] */
    avail = map->p_len - (offset - map->p_offset);
    *len = avail;

    return map->p + (offset - map->p_offset);
}


/* Release a file mapping.  This does not close the underlying fd. */
void
_hs_unmap_file(hs_map_t * map)
{
    assert(map->tag == HS_MAP_TAG);
    if (map->p) {
	free(map->p);
	map->p = NULL;
    }
    memset(map, 0, sizeof(*map));
    free(map);
}
