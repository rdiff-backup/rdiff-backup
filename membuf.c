/* -*- mode: c; c-file-style: "gnu" -*-  */

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

hs_membuf_t *
hs_membuf_new (void)
{
  hs_membuf_t *mb;

  mb = calloc (1, sizeof (hs_membuf_t));
  mb->alloc = 0;
  mb->length = -1;
  return mb;
}


off_t
hs_membuf_tell (void *private)
{
  return ((hs_membuf_t *) private)->ofs;
}


void
hs_membuf_truncate (hs_membuf_t *mb)
{
  mb->ofs = 0;
}


ssize_t
hs_membuf_write (void *private, char const *buf, size_t len)
{
  hs_membuf_t *bofs = (hs_membuf_t *) private;

#if DEBUG
  printf ("sig_writebuf(len=%d)\n", len);
#endif

  if (bofs->length != -1)
    {
      size_t remain = bofs->length - bofs->ofs;
      if (len > remain)
	len = remain;
    }
  else if (bofs->alloc < bofs->ofs + len)
    {
      bofs->alloc = MAX(bofs->alloc * 2, bofs->ofs + len);
      bofs->buf = realloc (bofs->buf, bofs->alloc);
      if (!bofs->buf)
	return -1;
    }

  memcpy (bofs->buf + bofs->ofs, buf, len);
  bofs->ofs += len;
  return len;
}


ssize_t
hs_membuf_read_ofs (void *private, char *buf, size_t len, off_t ofs)
{
  hs_membuf_t *mb = (hs_membuf_t *) private;

  assert (ofs >= 0);

  if ((mb->length != -1 && ofs < mb->length)
      || ((unsigned) ofs <  mb->alloc))
    {
      mb->ofs = ofs;
      return hs_membuf_read (private, buf, len);
    }
  else
    {
      _hs_error ("illegal seek to %ld in a %ld byte membuf",
	       (long) ofs, (long) mb->alloc);
      errno = EINVAL;
      return -1;
    }
}


ssize_t
hs_membuf_read (void *private, char *buf, size_t len)
{
  hs_membuf_t *bofs = (hs_membuf_t *) private;

#if DEBUG
  printf ("sig_readbuf(len=%d)\n", len);
#endif

  if (bofs->length != -1)
    {
      size_t remain = bofs->length - bofs->ofs;
      if (len > remain)
	len = remain;
    }

  memcpy (buf, bofs->buf + bofs->ofs, len);
  bofs->ofs += len;
  return len;
}



ssize_t hs_membuf_zwrite (void *private, char const *buf, size_t len)
{
  size_t ret;

  ret = comp_write (hs_membuf_write, private, buf, len);

  return ret;
}
