/* -*- mode: c; c-file-style: "bsd" -*-  */

/* netio -- Network byte order IO Copyright (C) 2000 by Martin Pool
   <mbp@humbug.org.au>

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

/* This will only return a short read if we reach eof.  The underlying *
   functions are allowed to wimp out and return short if they * want. * *
   XXX: In the future this function may be deprecated in favour of * mapptr. */
int
_hs_read_loop(hs_read_fn_t read_fn, void *read_priv, byte_t *buf, size_t len)
{
    size_t          count = 0;
    int             ret;

    if (len == 0)
	return 0;

    while (count < len) {
	ret = read_fn(read_priv, buf + count, len - count);
	if (ret == 0)
	    return count;
	if (ret == -1)
	    return ret;
	count += ret;
    }

    return count;
}



/* Either read LEN bytes and return LEN, or zero for EOF, or fail *
   completely. */
int
_hs_must_read(hs_read_fn_t read_fn, void *read_priv, byte_t *buf, ssize_t len)
{
    ssize_t         count = 0;
    int             ret;

    if (len == 0)
	return 0;

    while (count < len) {
	ret = read_fn(read_priv, buf + count, len - count);
	if (ret == 0) {
	    /* it's OK to get an EOF at the start, but not in the middle of
	       the object. */
	    if (count == 0)
		return 0;
	    else {
		_hs_error("unexpected eof");
		return ret;
	    }
	}
	if (ret < 0)
	    return ret;
	count += ret;
    }

    assert(count == len);
    return count;
}


/* 
 * Insist on writing out a block of data, retrying if necessary.
 *
 * XXX: This may be deprecated in favour of hs_hose.
 */
size_t
_hs_write_loop(hs_write_fn_t write_fn, void *write_priv,
	       byte_t const *buf, size_t len)
{
    size_t          count = 0;
    int             ret;
    int             iter = 0;

    if (!len)
	return len;

    while (count < len) {
	ret = write_fn(write_priv, buf + count, len - count);
	count += ret;
	if (ret == -1)
	    return ret;
	if (ret == 0 && ++iter > 100) {
	    if (!errno)
		errno = EIO;
	    return -1;
	}
    }

    return count;
}


/* Either write the whole thing, or fail. */
int
hs_must_write(hs_write_fn_t write_fn, void *write_priv,
	      void const *buf, int len)
{
    int             ret;

    ret = _hs_write_loop(write_fn, write_priv, buf, len);
    if (ret == len)
	return len;
    else if (ret >= 0 && ret < len) {
	_hs_error("short write: wanted to send %d bytes, only got out %d",
		  len, ret);
	return -1;
    } else if (ret > len) {
	_hs_fatal("something's really crazy: "
		  "we wanted to send %d bytes, but wrote %d", len, ret);
	abort();
	return -1;
    } else {
	return -1;
    }
}




int
_hs_write_netint(hs_write_fn_t write_fn, void *write_priv, uint32_t out)
{
    uint32_t        net_out = htonl(out);

    return hs_must_write(write_fn, write_priv, &net_out, sizeof net_out);
}


int
_hs_write_netshort(hs_write_fn_t write_fn, void *write_priv, uint16_t out)
{
    uint16_t        net_out = htons(out);

    return hs_must_write(write_fn, write_priv, &net_out, sizeof net_out);
}


int
_hs_write_netbyte(hs_write_fn_t write_fn, void *write_priv, uint8_t out)
{
    return hs_must_write(write_fn, write_priv, &out, sizeof out);
}


int
_hs_read_netshort(hs_read_fn_t read_fn, void *read_priv, uint16_t * result)
{
    uint16_t        buf;
    int             ret;

    ret = _hs_must_read(read_fn, read_priv, (byte_t *) &buf, sizeof buf);
    *result = ntohs(buf);

    return ret;
}


int
_hs_read_netint(hs_read_fn_t read_fn, void *read_priv, uint32_t * result)
{
    uint32_t        buf;
    int             ret;

    ret = _hs_must_read(read_fn, read_priv, (byte_t *) &buf, sizeof buf);
    *result = ntohl(buf);

    return ret;
}


int
_hs_read_netbyte(hs_read_fn_t read_fn, void *read_priv, uint8_t * result)
{
    uint8_t         buf;
    int             ret;
    const int       len = sizeof buf;

    ret = _hs_must_read(read_fn, read_priv, (byte_t *) &buf, len);
    *result = buf;

    return len;
}



int
_hs_write_netvar(hs_write_fn_t write_fn, void *write_priv,
		 uint32_t value, int type)
{
    if (type == 1)
	return _hs_write_netbyte(write_fn, write_priv, value);
    else if (type == 2)
	return _hs_write_netshort(write_fn, write_priv, value);
    else if (type == 4)
	return _hs_write_netint(write_fn, write_priv, value);
    else
	assert(0);
}
