/* -*- mode: c; c-file-style: "bsd" -*- */
/* librsync/compress.c -- a shim between signature.c and librsync to add zlib 
   compression

   Copyright (C) 1999, 2000 by Martin Pool Copyright (C) 1999 by Andrew
   Tridgell

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
   Temple Place, Suite 330, Boston, MA 02111-1307 USA */

#include "includes.h"
#include "compress.h"

/* TODO: Remove the static stuff? */

static z_stream c;
static char     cbuf[1024];
static int      eof;

void
comp_init(void)
{
    memset(&c, 0, sizeof(c));

    deflateInit(&c, Z_DEFAULT_COMPRESSION);

    c.next_out = (Bytef *) cbuf;
    c.avail_out = sizeof(cbuf);
}


ssize_t
comp_write(ssize_t(*fn) (void *, char const *, size_t),
	   void *private, char const *buf, size_t len)
{
    size_t          to_write;
    int             err;

    c.next_in = (Bytef *) buf;
    c.avail_in = len;

    while (c.avail_in || (sizeof(cbuf) != c.avail_out)) {
	to_write = sizeof(cbuf) - c.avail_out;
	if (to_write) {
	    if (fn(private, cbuf, to_write) != (ssize_t) to_write) {
		fprintf(stderr, "Error in deflate\n");
		abort();
	    }
	    c.next_out = (Bytef *) cbuf;
	    c.avail_out = sizeof(cbuf);
	}
	if (c.avail_in) {
	    if ((err = deflate(&c, Z_NO_FLUSH) != Z_OK)) {
		fprintf(stderr, "Error2 in deflate\n");
	    }
	}
    }

    return len;
}


void
comp_flush(ssize_t(*fn) (void *, char const *, size_t), void *private)
{
    int             to_flush;
    int             err = Z_OK;



    while (err == Z_OK) {
	err = deflate(&c, Z_FINISH);
	to_flush = sizeof(cbuf) - c.avail_out;
	if (to_flush) {
	    if (fn(private, cbuf, to_flush) != to_flush) {
		fprintf(stderr, "error in deflate_flush: short_write\n");
		abort();
	    }
	    c.next_out = (Bytef *) cbuf;
	    c.avail_out = sizeof(cbuf);
	}
    }
}


void
decomp_init(void)
{
    eof = 0;
    memset(&c, 0, sizeof(c));

    inflateInit(&c);
    c.avail_in = 0;
    c.next_in = (Bytef *) cbuf;
}

ssize_t
decomp_read(ssize_t(*fn) (void *, char *, size_t),
	    void *private, char *buf, size_t len)
{
    c.avail_out = len;
    c.next_out = (Bytef *) buf;

    if (!eof && inflate(&c, Z_NO_FLUSH) == Z_STREAM_END) {
	eof = 1;
    }

    while (c.avail_out && !eof) {
	if ((char *) c.next_in > &cbuf[sizeof(cbuf) / 2]) {
	    memmove(cbuf, c.next_in, c.avail_in);
	    c.next_in = (Bytef *) cbuf;
	}

	if (c.avail_in < sizeof(cbuf)) {
	    if (fn(private, (char *) c.next_in + c.avail_in, 1) != 1) {
		_hs_fatal("error in inflate: couldn't read "
			  "one character\n");
		abort();
	    }
	    c.avail_in++;
	}

	if (inflate(&c, Z_NO_FLUSH) == Z_STREAM_END)
	    eof = 1;
    }

    return len - c.avail_out;
}

ssize_t
decomp_finish(ssize_t(*fn) (void *, char *, size_t), void *private)
{
    char            scrapbuf[1024];
    int             ret = 0;

    c.avail_out = 1024;
    c.next_out = (Bytef *) scrapbuf;

    if (!eof && ((ret = inflate(&c, Z_FINISH)) == Z_STREAM_END)) {
	eof = 1;
    }

    while (!eof) {
	if ((char *) c.next_in > &cbuf[sizeof(cbuf) / 2]) {
	    memmove(cbuf, c.next_in, c.avail_in);
	    c.next_in = (Bytef *) cbuf;
	}

	if (c.avail_in < sizeof(cbuf)) {
	    int             ret = 0;

	    if ((ret = fn(private, (char *) c.next_in + c.avail_in, 1)) != 1) {
		fprintf(stderr, "Error in inflate (%d)\n", ret);
		abort();
	    }
	    c.avail_in++;
	}

	if (inflate(&c, Z_FINISH) == Z_STREAM_END)
	    eof = 1;
	c.avail_out = 1024;
    }

    return 0;
}
