/* -*- mode: c; c-file-style: "k&r" -*- */
/* librsync/filebuf.c -- Abstract read to and from FILE* buffers.

   Copyright (C) 1999, 2000 by Martin Pool.
   Copyright (C) 1999 by tridge@samba.org.

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
   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
*/

					/* To walk on water you've
					   gotta sink in the ice.
					   -- Shihad, `The General Electric'. */

#include "includes.h"
#include "hsync.h"
#include "private.h"
#include "compress.h"

// #define DEBUG 1
const int filebuf_tag = 23031976;

struct file_buf {
    int dogtag;

    FILE *f;
    FILE *f_cache;

    /* Maximum amount to read from the file, or -1 if we can read
       until EOF. */
    ssize_t length;
};

hs_filebuf_t *hs_filebuf_from_file(FILE * fp)
{
    hs_filebuf_t *fb;

    fb = calloc(1, sizeof(hs_filebuf_t));
    return_val_if_fail(fb, NULL);

    fb->dogtag = filebuf_tag;
    fb->f = fp;
    fb->f_cache = NULL;
    fb->length = -1;

    return fb;
}


/* TODO: Add matching close/free function. */

hs_filebuf_t *hs_filebuf_open(char const *filename, char const *mode)
{
    FILE *fp;

    fp = fopen(filename, mode);
    if (!fp) {
	_hs_fatal("error opening %s for mode %s", filename, mode);
	return NULL;
    }

    return hs_filebuf_from_file(fp);
}



ssize_t hs_filebuf_read(void *private, char *buf, size_t len)
{
    struct file_buf *fbuf = (struct file_buf *) private;
    size_t n;
    size_t len2;

    assert(fbuf->dogtag == filebuf_tag);

    if (fbuf->length == 0) {
	n = 0;
	goto out;
    }

    if (fbuf->length == -1) {
	n = fread(buf, 1, len, fbuf->f);
	if (n > 0 && fbuf->f_cache) {
	    fwrite(buf, 1, n, fbuf->f_cache);
	}
	goto out;
    }

    if (fbuf->length >= 0)
	len2 = MIN(len, (size_t) fbuf->length);
    else
	len2 = len;

    n = fread(buf, 1, len2, fbuf->f);

    if (n <= 0) {
	fbuf->length = 0;
	n = 0;
	goto out;
    }

    fbuf->length -= n;

    if (n > 0 && fbuf->f_cache) {
	fwrite(buf, 1, n, fbuf->f_cache);
    }

  out:

    return n;
}

ssize_t hs_filebuf_zread(void *private, char *buf, size_t len)
{
    size_t ret;

    ret = decomp_read(hs_filebuf_read, private, buf, len);

    return ret;
}

ssize_t hs_filebuf_write(void *private, char const *buf, size_t len)
{
    struct file_buf *fbuf = (struct file_buf *) private;
    size_t n;

    assert(fbuf->dogtag == filebuf_tag);
    n = fwrite(buf, 1, len, fbuf->f);
    if (fbuf->f_cache && n > 0) {
	fwrite(buf, 1, n, fbuf->f_cache);
    }

    return n;
}


ssize_t hs_filebuf_zwrite(void *private, char const *buf, size_t len)
{
    size_t ret;

    ret = comp_write(hs_filebuf_write, private, buf, len);

    return ret;
}

ssize_t
hs_filebuf_read_ofs(void *private, char *buf, size_t len, off_t ofs)
{
    struct file_buf *fbuf = (struct file_buf *) private;
    size_t n;

    assert(fbuf->dogtag == filebuf_tag);
    assert(fbuf->f);
    if (fseek(fbuf->f, ofs, SEEK_SET)) {
	fprintf(stderr, "hs_filebuf_read_ofs: "
		"seek to %ld failed: %s\n", (long) ofs, strerror(errno));
	return -1;
    }

    n = fread(buf, 1, len, fbuf->f);

    return n;
}
