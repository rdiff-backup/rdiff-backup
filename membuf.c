/* -*- mode: c; c-file-style: "k&r" -*-  */

/* librsync-membuf.h -- Abstract IO to memory buffers.

   Copyright (C) 1999, 2000 by Martin Pool <mbp@humbug.org.au>

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

#include "includes.h"
#include "hsync.h"
#include "private.h"
#include "compress.h"

static const int membuf_tag = 12341234;

hs_membuf_t *hs_membuf_new(void)
{
    hs_membuf_t *mb;

    mb = calloc(1, sizeof(hs_membuf_t));
    mb->dogtag = membuf_tag;
    mb->alloc = 0;
    mb->length = -1;
    return mb;
}


void hs_membuf_free(hs_membuf_t *mb)
{
     assert(mb->dogtag = membuf_tag);
     mb->dogtag = 0;
     free(mb);
}


/* Allow the caller read-only access to our buffer. */
size_t hs_membuf_getbuf(hs_membuf_t const *mb, char const **buf)
{
    assert(mb->dogtag == membuf_tag);
    *buf = mb->buf;
    return mb->length;
}


hs_membuf_t *hs_membuf_on_buffer(char *buf, int len)
{
    hs_membuf_t *mb;

    assert(len > 0);
    assert(buf);

    mb = calloc(1, sizeof(hs_membuf_t));
    assert(mb);
    mb->dogtag = membuf_tag;
    mb->alloc = 0;
    mb->length = len;
    mb->buf = buf;
    return mb;
}



off_t hs_membuf_tell(void *private)
{
    hs_membuf_t *mb = (hs_membuf_t *) private;
    assert(mb->dogtag == membuf_tag);
    return ((hs_membuf_t *) private)->ofs;
}


void hs_membuf_truncate(hs_membuf_t * mb)
{
    assert(mb->dogtag == membuf_tag);
    mb->ofs = 0;
}


ssize_t hs_membuf_write(void *private, char const *buf, size_t len)
{
    hs_membuf_t *mb = (hs_membuf_t *) private;
    assert(mb->dogtag == membuf_tag);

#if DEBUG
    printf("sig_writebuf(len=%d)\n", len);
#endif

    if (mb->length != -1) {
	size_t remain = mb->length - mb->ofs;
	if (len > remain)
	    len = remain;
    } else if (mb->alloc < mb->ofs + len) {
	mb->alloc = MAX(mb->alloc * 2, mb->ofs + len);
	mb->buf = realloc(mb->buf, mb->alloc);
	if (!mb->buf)
	    return -1;
    }

    memcpy(mb->buf + mb->ofs, buf, len);
    mb->ofs += len;
    return len;
}


ssize_t hs_membuf_read_ofs(void *private, char *buf, size_t len, off_t ofs)
{
    hs_membuf_t *mb = (hs_membuf_t *) private;

    assert(mb->dogtag == membuf_tag);
    assert(ofs >= 0);

    if ((mb->length != -1 && ofs < mb->length)
	|| ((unsigned) ofs < mb->alloc)) {
	mb->ofs = ofs;
	return hs_membuf_read(private, buf, len);
    } else {
	_hs_fatal("illegal seek to %ld in a %ld byte membuf",
		  (long) ofs, (long) mb->alloc);
	errno = EINVAL;
	return -1;
    }
}


ssize_t hs_membuf_read(void *private, char *buf, size_t len)
{
    hs_membuf_t *mb = (hs_membuf_t *) private;

#if DEBUG
    printf("sig_readbuf(len=%d)\n", len);
#endif

    assert(mb->dogtag == membuf_tag);
    if (mb->length != -1) {
	size_t remain = mb->length - mb->ofs;
	if (len > remain)
	    len = remain;
    }

    memcpy(buf, mb->buf + mb->ofs, len);
    mb->ofs += len;
    return len;
}



ssize_t hs_membuf_zwrite(void *private, char const *buf, size_t len)
{
    size_t ret;
    hs_membuf_t *mb = (hs_membuf_t *) private;

    assert(mb->dogtag == membuf_tag);
    ret = comp_write(hs_membuf_write, private, buf, len);

    return ret;
}
