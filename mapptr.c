/* -*- mode: c; c-file-style: "bsd" -*- */
/* $Id$ */
/* 
   Copyright (C) 2000 by Martin Pool
   Copyright (C) 1998 by Andrew Tridgell 
   
   This program is free software; you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation; either version 2 of the License, or
   (at your option) any later version.
   
   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.
   
   You should have received a copy of the GNU General Public License
   along with this program; if not, write to the Free Software
   Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
*/

/* Originally from rsync */

/*
 * TODO: We need to make sure that this works cleanly only sockets and
 * similar things.  In that case, we don't know the `length' of the
 * file, and we can never seek.  I think this code will do that.  */

#include "includes.h"
#include "hsync.h"
#include "private.h"

#define WRITE_SIZE (32*1024)
#define CHUNK_SIZE (32*1024)
#define MAX_MAP_SIZE (256*1024)
#define IO_BUFFER_SIZE (4092)

int const HS_MAP_TAG = 189900;


struct hs_map {
     int tag;
     char *p;
     int fd, p_size, p_len;
     hs_off_t file_size, p_offset, p_fd_offset;
};


/* this provides functionality somewhat similar to mmap() but using
   read(). It gives sliding window access to a file. mmap() is not
   used because of the possibility of another program (such as a
   mailer) truncating the file thus giving us a SIGBUS */
hs_map_t *
hs_map_file(int fd,hs_off_t len)
{
     hs_map_t *map;
     map = (hs_map_t *)malloc(sizeof(*map));
     if (!map) {
	  _hs_fatal("map_file");
	  abort();
     }

     map->tag = HS_MAP_TAG;
     map->fd = fd;
     map->file_size = len;
     map->p = NULL;
     map->p_size = 0;
     map->p_offset = 0;
     map->p_fd_offset = 0;
     map->p_len = 0;

     return map;
}



/* slide the read window in the file */
char const *
hs_map_ptr(hs_map_t *map, hs_off_t offset, int len)
{
     int nread;
     hs_off_t window_start, read_start;
     int window_size, read_size, read_offset;
     int total_read;

     assert(map->tag == HS_MAP_TAG);

     /* TODO: Perhaps we should allow this, but why? */
     if (len == 0) {
	 errno = EINVAL;
	 return NULL;
     }

     /* can't go beyond the end of file */
     if (len > (map->file_size - offset)) {
	  len = map->file_size - offset;
     }

     /* in most cases the region will already be available */
     if (offset >= map->p_offset && 
	 offset+len <= map->p_offset+map->p_len) {
	  return (map->p + (offset - map->p_offset));
     }


     /* nope, we are going to have to do a read. Work out our desired window */
     if (offset > 2*CHUNK_SIZE) {
	  window_start = offset - 2*CHUNK_SIZE;
	  window_start &= ~((hs_off_t)(CHUNK_SIZE-1)); /* assumes power of 2 */
     } else {
	  window_start = 0;
     }
     window_size = MAX_MAP_SIZE;
     if (window_start + window_size > map->file_size) {
	  window_size = map->file_size - window_start;
     }
     if (offset + len > window_start + window_size) {
	  window_size = (offset+len) - window_start;
     }

     /* make sure we have allocated enough memory for the window */
     if (window_size > map->p_size) {
	  map->p = (char *) realloc(map->p, window_size);
	  if (!map->p) {
	       _hs_fatal("map_ptr: out of memory");
	       abort();
	  }
	  map->p_size = window_size;
     }

     /* now try to avoid re-reading any bytes by reusing any bytes from the previous
	buffer. */
     if (window_start >= map->p_offset &&
	 window_start < map->p_offset + map->p_len &&
	 window_start + window_size >= map->p_offset + map->p_len) {
	  read_start = map->p_offset + map->p_len;
	  read_offset = read_start - window_start;
	  read_size = window_size - read_offset;
	  memmove(map->p, map->p + (map->p_len - read_offset), read_offset);
     } else {
	  read_start = window_start;
	  read_size = window_size;
	  read_offset = 0;
     }

     if (read_size <= 0) {
	  _hs_trace("Warning: unexpected read size of %d in map_ptr\n",
		    read_size);
     } else {
	  if (map->p_fd_offset != read_start) {
	       if (lseek(map->fd,read_start,SEEK_SET) != read_start) {
		    _hs_trace("lseek failed in map_ptr\n");
		    abort();
	       }
	       map->p_fd_offset = read_start;
	  }

	  total_read = 0;
	  do {
	      nread = read(map->fd, map->p + read_offset, read_size - total_read);
	      
	      if (nread < 0) {
		   _hs_error("read error in %s: %s", __FUNCTION__,
			     strerror(errno));
		   break;
	      }

	      total_read += nread;
	      read_offset += nread;

	      if (nread == 0) {
		  /* early EOF in file. */
		  /* the best we can do is zero the buffer - the file
		     has changed mid transfer! */
		  memset(map->p+read_offset, 0, read_size - total_read);
		  break;
	      }
	  } while (total_read < read_size);

	  map->p_fd_offset += total_read;
     }

     map->p_offset = window_start;
     map->p_len = window_size;
  
     return map->p + (offset - map->p_offset); 
}


void
hs_unmap_file(hs_map_t *map)
{
     assert(map->tag == HS_MAP_TAG);
     if (map->p) {
	  free(map->p);
	  map->p = NULL;
     }
     memset(map, 0, sizeof(*map));
     free(map);
}

