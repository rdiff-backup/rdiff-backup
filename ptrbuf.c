/* -*- mode: c; c-file-style: "bsd" -*-  */
/* $Id$

   Copyright (C) 1999, 2000 by Martin Pool <mbp@humbug.org.au>

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

#include "includes.h"

static const int ptrbuf_tag = 384384;

/* An HS_PTRBUF_T is an abstract-io interface to a fixed in-memory buffer.
   The caller must arrange the buffer (perhaps it's a string cohstant, or
   perhaps they malloc it), and supply the base and length.  Trying to write
   past the end will fail. */

/* Allow the caller read-only access to our buffer. */
size_t
hs_ptrbuf_getbuf(hs_ptrbuf_t const *mb, byte_t const **buf)
{
    assert(mb->dogtag == ptrbuf_tag);
    *buf = mb->buf;
    return mb->length;
}


hs_ptrbuf_t    *
hs_ptrbuf_on_buffer(byte_t *buf, int len)
{
    hs_ptrbuf_t    *mb;

    assert(len >= 0);
    assert(buf);

    mb = calloc(1, sizeof(hs_ptrbuf_t));
    assert(mb);
    mb->dogtag = ptrbuf_tag;
    mb->length = len;
    mb->buf = buf;
    return mb;
}



hs_off_t
hs_ptrbuf_tell(void *private)
{
    hs_ptrbuf_t    *mb = (hs_ptrbuf_t *) private;

    assert(mb->dogtag == ptrbuf_tag);
    return ((hs_ptrbuf_t *) private)->ofs;
}


void
hs_ptrbuf_truncate(hs_ptrbuf_t * mb)
{
    assert(mb->dogtag == ptrbuf_tag);
    mb->ofs = 0;
}


ssize_t
hs_ptrbuf_write(void *private, byte_t const *buf, size_t len)
{
    hs_ptrbuf_t    *mb = (hs_ptrbuf_t *) private;

    assert(mb->dogtag == ptrbuf_tag);

    if (mb->length < mb->ofs + len) {
	return -1;
    }

    memcpy(mb->buf + mb->ofs, buf, len);
    mb->ofs += len;
    return len;
}


ssize_t
hs_ptrbuf_read_ofs(void *private, byte_t *buf, size_t len, hs_off_t ofs)
{
    hs_ptrbuf_t    *mb = (hs_ptrbuf_t *) private;

    assert(mb->dogtag == ptrbuf_tag);
    assert(ofs >= 0);

    if (ofs >= 0 && ofs < (hs_off_t) mb->length) {
	mb->ofs = ofs;
	return hs_ptrbuf_read(private, buf, len);
    } else {
	_hs_fatal("illegal seek to %ld in a %ld byte ptrbuf",
		  (long) ofs, (long) mb->length);
	errno = EINVAL;
	return -1;
    }
}


ssize_t
hs_ptrbuf_read(void *private, byte_t *buf, size_t len)
{
    hs_ptrbuf_t    *mb = (hs_ptrbuf_t *) private;
    size_t          remain = mb->length - mb->ofs;

    assert(mb->dogtag == ptrbuf_tag);

    if (len > remain)
	len = remain;

    memcpy(buf, mb->buf + mb->ofs, len);
    mb->ofs += len;
    return len;
}
