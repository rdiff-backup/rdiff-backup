/* -*- mode: c; c-file-style: "k&r" -*-  */

/* netio -- Network byte order IO
   Copyright (C) 2000 by Martin Pool <mbp@humbug.org.au>

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
   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
   USA
*/

#include "includes.h"
#include "hsync.h"
#include "private.h"


/* This will only return a short read if we reach eof.  The underlying
   functions are allowed to wimp out and return short if they
   want. */
int
_hs_read_loop(hs_read_fn_t read_fn, void *read_priv,
	      char *buf, size_t len)
{
    size_t count = 0;
    int ret;

    if (!len)
	return len;

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

int
_hs_write_loop(hs_write_fn_t write_fn, void *write_priv,
	       char const *buf, int len)
{
    int count = 0;
    int ret;
    int iter = 0;

    if (!len)
	return len;

    while (count < len) {
	ret = write_fn(write_priv, buf + count, len - count);
	count += ret;
	if (ret == -1)
	    return ret;
	if (ret == 0 && ++iter > 100) {
	    errno = EIO;
	    return -1;
	}
    }

    return count;
}


int
_hs_copy_ofs(uint32_t offset, uint32_t length,
	     hs_readofs_fn_t readofs_fn, void *readofs_priv,
	     hs_write_fn_t write_fn, void *write_priv)
{
    int ret;
    char *buf;

    if (length > INT32_MAX) {
	_hs_fatal("length %u is too big", length);
	return -1;
    }

    buf = malloc(length);

    ret = readofs_fn(readofs_priv, buf, length, offset);
    if (ret < 0) {
	 _hs_error("error in read callback: off=%d, len=%d",
		   offset, length);
	goto fail;
    } else if (ret >= 0 && ret < (int) length) {
	 _hs_error("short read: off=%d, len=%d, result=%d",
		   offset, length, ret);
	 errno = ENODATA;
	 goto fail;
    }

    ret = _hs_write_loop(write_fn, write_priv, buf, ret);
    if (ret != (int) length) {
	 _hs_error("error in write callback: off=%d, len=%d",
		   offset, length);
	 goto fail;
    }

    free(buf);
    return length;

  fail:
    free(buf);
    return -1;
}



int
_hs_write_netint(hs_write_fn_t write_fn, void *write_priv, uint32_t out)
{
    out = htonl(out);
    return _hs_write_loop(write_fn, write_priv, (void *) &out, sizeof out) == sizeof out
	? sizeof out : -1;
}


int
_hs_write_netshort(hs_write_fn_t write_fn, void *write_priv, uint16_t out)
{
    out = htons(out);
    return _hs_write_loop(write_fn, write_priv, (void *) &out, sizeof out) == sizeof out
	? sizeof out : -1;
}


int
_hs_write_netbyte(hs_write_fn_t write_fn, void *write_priv, uint8_t out)
{
    return _hs_write_loop(write_fn, write_priv, (void *) &out, sizeof out) == sizeof out
	? sizeof out : -1;
}


int
_hs_read_netshort(hs_read_fn_t read_fn, void *read_priv, uint16_t * result)
{
    uint16_t buf;
    int ret;

    ret = _hs_read_loop(read_fn, read_priv, (char *) &buf, sizeof buf);
    *result = ntohs(buf);

    return ret;
}


int
_hs_read_netint(hs_read_fn_t read_fn, void *read_priv, uint32_t * result)
{
    uint32_t buf;
    int ret;

    ret = _hs_read_loop(read_fn, read_priv, (char *) &buf, sizeof buf);

    *result = ntohl(buf);

    return ret;
}


int
_hs_read_netbyte(hs_read_fn_t read_fn, void *read_priv, uint8_t * result)
{
    uint8_t buf;
    int ret;
    const int len = sizeof buf;

    ret = _hs_read_loop(read_fn, read_priv, (char *) &buf, len);
    if (ret != len)
	return ret;

    if (ret == 0)
	return 0;

    *result = buf;

    return len;
}



int _hs_write_netvar(hs_write_fn_t write_fn, void *write_priv,
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
