/*=				       	-*- c-file-style: "bsd" -*-
 * rproxy -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 1999, 2000 by Martin Pool <mbp@humbug.org.au>
 * Copyright (C) 1999 by Andrew Tridgell <tridge@samba.org>
 * 
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public License
 * as published by the Free Software Foundation; either version 2.1 of
 * the License, or (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 * 
 * You should have received a copy of the GNU Lesser General Public
 * License along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */


/*
     XXX
      XXX
       XXX
        XXX    THIS FILE IS GOING AWAY SOON!
         XXX   filebufs are deprecated in favour of mapptr, etc
          XXX
           XXX
            XXX
  */




/* XXX: This file is becoming somewhat obsolete because we're moving to
   prefer mapptrs. */

#include "includes.h"

#include <unistd.h>
#include <stdio.h>
#include <sys/file.h>
#include <string.h>

const int       filebuf_tag = 24031976;

struct file_buf {
    int             dogtag;
    int             fd, fd_cache;
};


hs_filebuf_t   *
hs_filebuf_from_fd(int fd)
{
    hs_filebuf_t   *fb;

    if (fd == -1)
        _hs_fatal("called with fd of -1");

    fb = calloc(1, sizeof(hs_filebuf_t));
    assert(fb);

    fb->dogtag = filebuf_tag;
    fb->fd = fd;
    fb->fd_cache = -1;

    return fb;
}


void
hs_filebuf_add_cache(hs_filebuf_t * fb, int fd_cache)
{
    assert(fb);
    assert(fb->dogtag == filebuf_tag);

    fb->fd_cache = fd_cache;
}


/* TODO: Add matching close/free function. */

hs_filebuf_t   *
hs_filebuf_open(char const *filename, int mode)
{
    int             fd;

    fd = hs_file_open(filename, mode);
    if (fd == -1)
	return NULL;
    else
	return hs_filebuf_from_fd(fd);
}


void
hs_filebuf_close(hs_filebuf_t * fbuf)
{
    assert(fbuf->dogtag == filebuf_tag);

    if (close(fbuf->fd) < 0) {
        _hs_error("error closing fd%d: %s",
                  fbuf->fd, strerror(errno));
    }
    fbuf->fd = -1;

    if (fbuf->fd_cache != -1) {
        if (close(fbuf->fd_cache) < 0) {
            _hs_error("error closing cache fd%d: %s",
                      fbuf->fd_cache , strerror(errno));
        }
	fbuf->fd_cache = -1;
    }

    hs_bzero(fbuf, sizeof *fbuf);
    free(fbuf);
}



/* May return short */
ssize_t
hs_filebuf_read(void *private, byte_t *buf, size_t len)
{
    struct file_buf *fbuf = (struct file_buf *) private;
    ssize_t         n;

    assert(fbuf->dogtag == filebuf_tag);
    assert(fbuf->fd != -1);

#ifdef HS_ALWAYS_READ_SHORT
    len = MIN(len, 100);
#endif

    n = read(fbuf->fd, buf, len);

    if (n < 0) {
	_hs_error("error reading fd%d: %s", fbuf->fd, strerror(errno));
    }

    return n;
}


ssize_t
hs_filebuf_write(void *private, byte_t const *buf, size_t len)
{
    struct file_buf *fbuf = (struct file_buf *) private;
    ssize_t          n;
    ssize_t             cache_n;

    assert(fbuf->dogtag == filebuf_tag);
#ifdef HS_ALWAYS_READ_SHORT
    len = MIN(len, 100);
#endif
    n = write(fbuf->fd, buf, len);
    if (n < 0) {
        _hs_error("error writing to fd%d: %s",
                  fbuf->fd, strerror(errno));
    }
    
    if (fbuf->fd_cache != -1 && n > 0) {
	cache_n = write(fbuf->fd_cache, buf, n);
        if (cache_n < 0) {
            _hs_error("error writing to cache fd%d: %s",
                      fbuf->fd_cache, strerror(errno));
        }
    }


    return n;
}
