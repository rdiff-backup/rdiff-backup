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



/* Either read LEN bytes and return LEN, or zero for EOF, or fail
   completely. */
int
_hs_must_read(hs_read_fn_t read_fn, void *read_priv,
	      char *buf, ssize_t len)
{
     ssize_t ret;
     ret = _hs_read_loop(read_fn, read_priv, buf, len);
     if (ret == len)
	  return ret;
     else if (ret == 0) {
	  _hs_error("unexpected EOF");
	  return ret;
     } else if (ret < 0) {
	  return -1;
     } else if (ret < len) {
	  _hs_error("short read where one is not allowed: got %d bytes, "
		    "wanted %d", ret, len);
	  return -1;
     } else { /* (ret > len) */
	  _hs_error("too much data returned from read: got %d bytes, "
		    "wanted just %d", ret, len);
	  return -1;
     }
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

    ret = _hs_must_read(read_fn, read_priv, (char *) &buf, sizeof buf);
    *result = ntohs(buf);

    return ret;
}


int
_hs_read_netint(hs_read_fn_t read_fn, void *read_priv, uint32_t * result)
{
    uint32_t buf;
    int ret;

    ret = _hs_must_read(read_fn, read_priv, (char *) &buf, sizeof buf);
    *result = ntohl(buf);

    return ret;
}


int
_hs_read_netbyte(hs_read_fn_t read_fn, void *read_priv, uint8_t * result)
{
    uint8_t buf;
    int ret;
    const int len = sizeof buf;

    ret = _hs_must_read(read_fn, read_priv, (char *) &buf, len);
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
