/* -*- mode: c; c-file-style: "bsd" -*- * $Id: filebuf.c,v 1.20 2000/05/09
   10:44:27 mbp Exp $ * * librsync/filebuf.c -- Abstract read to and from
   FILE* buffers.

   Copyright (C) 1999, 2000 by Martin Pool. Copyright (C) 1999 by
   tridge@samba.org.

   This program is free software; you can redistribute it and/or modify it
   under the terms of the GNU General Public License as published by the Free 
   Software Foundation; either version 2 of the License, or (at your option)
   any later version.

   This program is distributed in the hope that it will be useful, but
   WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY 
   or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
   for more details.

   You should have received a copy of the GNU General Public License along
   with this program; if not, write to the Free Software Foundation, Inc., 59 
   Temple Place, Suite 330, Boston, MA  02111-1307  USA */

					/* To walk on water you've gotta sink 
					   in the ice. -- Shihad, `The
					   General Electric'. */

/* XXX: This file is becoming somewhat obsolete because we're moving to
   prefer mapptrs. */

#include "includes.h"

const int       filebuf_tag = 24031976;

struct file_buf {
    int             dogtag;

    int             fd, fd_cache;
};


/* This is deprecated because we'd rather not use FILE* */
hs_filebuf_t   *
hs_filebuf_from_file(FILE * fp)
{
    return hs_filebuf_from_fd(fileno(fp));
}


hs_filebuf_t   *
hs_filebuf_from_fd(int fd)
{
    hs_filebuf_t   *fb;

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

    fd = _hs_file_open(filename, mode);
    if (fd == -1)
	return NULL;
    else
	return hs_filebuf_from_fd(fd);
}


void
hs_filebuf_close(hs_filebuf_t * fbuf)
{
    assert(fbuf->dogtag == filebuf_tag);

    close(fbuf->fd);
    fbuf->fd = -1;

    if (fbuf->fd_cache != -1) {
	close(fbuf->fd_cache);
	fbuf->fd_cache = -1;
    }

    hs_bzero(fbuf, sizeof *fbuf);
    free(fbuf);
}



/* May return short */
ssize_t hs_filebuf_read(void *private, char *buf, size_t len)
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


ssize_t hs_filebuf_write(void *private, char const *buf, size_t len)
{
    struct file_buf *fbuf = (struct file_buf *) private;
    size_t          n;

    assert(fbuf->dogtag == filebuf_tag);
#ifdef HS_ALWAYS_READ_SHORT
    len = MIN(len, 100);
#endif
    n = write(fbuf->fd, buf, len);
    if (fbuf->fd_cache != -1 && n > 0) {
	write(fbuf->fd_cache, buf, n);
    }

    return n;
}
