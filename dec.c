/* -*- mode: c; c-file-style: "k&r" -*-  */

/* gddec.c -- Decode & extract signature from a gdiff-plus stream

   Copyright (C) 2000 by Martin Pool.

   This program is free software; you can redistribute it and/or
   modify it under the terms of the GNU General Public License as
   published by the Free Software Foundation; either version 2 of the
   License, or (at your option) any later version.
   
   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.
   
   You should have received a copy of the GNU General Public License
   along with this program; if not, write to the Free Software
   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA */


/* Here's a diagram of the decoding process:

       	       	       	   /---- OLDBODY <--- BODYCACHE
			  v		       ^
   UPSTREAM -chunked-> LTSTREAM	----> BODY ----+----> CLIENT
                \
                 -> SIGNATURE ---> SIGCACHE


   As we read input from upstream, we split the chunked encoding into
   the literal-token stream, and the server-generated signature.  We
   combine the ltstream with the old body to get the new value of the
   body.  This is sent downstream, and also written back into the cache.
   The signature is extracted and written into the signature cache
   so that we can send it up in the next request.
*/


#include "includes.h"

#include "hsync.h"
#include "hsyncproto.h"
#include "private.h"

#define MAXLITDATA	64*1024*1024
#define DEFLITBUFSIZE	1024


static int
_hs_copy(const uint32_t length,
	 hs_read_fn_t read_fn, void *read_priv,
	 hs_write_fn_t write_fn, void *write_priv,
	 hs_mdfour_t *newsum)
{
     ssize_t ret;
     char *buf;

     buf = malloc(length);
     if (!buf)
	  goto fail;

     ret = _hs_read_loop(read_fn, read_priv, buf, length);
     if (ret >= 0 && (ret < (int32_t) length)) {
	  errno = ENODATA;
	  goto fail;
     }

     if (newsum) 
	  hs_mdfour_update(newsum, buf, ret);

     ret = _hs_write_loop(write_fn, write_priv, buf, ret);
     if ((unsigned) ret != length)
	  goto fail;

     free(buf);
     return length;

 fail:
     if (buf)
	  free(buf);
     return -1;
}



static int _hs_check_gd_header(hs_read_fn_t ltread_fn, void *ltread_priv)
{
    int ret;
    uint32_t remote_magic, expect;

    expect = HS_LT_MAGIC;

    ret = _hs_read_netint(ltread_fn, ltread_priv, &remote_magic);
    return_val_if_fail(ret == 4, -1);
    if (remote_magic != expect) {
	_hs_fatal("version mismatch: %#010x != %#010x",
		  remote_magic, expect);
	errno = EBADMSG;
	return -1;
    }
    _hs_trace("got version %#010x", remote_magic);
    return 0;
}


static int
_hs_check_checksum(hs_read_fn_t ltread_fn, void *ltread_priv,
		   int length, hs_mdfour_t * newsum)
{
     char *buf;
     int ret;
     char actual_result[MD4_LENGTH];

     assert(length == MD4_LENGTH);
     buf = malloc(length);
     assert(buf);

     ret = _hs_read_loop(ltread_fn, ltread_priv, buf, length);
     assert(ret == length);

     hs_mdfour_result(newsum, actual_result);

     assert(memcmp(actual_result, buf, MD4_LENGTH) == 0);
     free(buf);

     return 1;
}

int
_hs_copy_ofs(uint32_t offset, uint32_t length,
	     hs_readofs_fn_t readofs_fn, void *readofs_priv,
	     hs_write_fn_t write_fn, void *write_priv,
	     hs_mdfour_t *newsum)
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
    } else if (ret != (int) length) {
	 _hs_error("short read: off=%d, len=%d, result=%d",
		   offset, length, ret);
	 errno = ENODATA;
	 goto fail;
    }

    if (newsum)
	 hs_mdfour_update(newsum, buf, ret);

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


ssize_t
hs_decode(hs_readofs_fn_t oldread_fn, void *oldread_priv,
	  hs_write_fn_t write_fn, void *write_priv,
	  hs_read_fn_t ltread_fn, void *ltread_priv,
	  hs_write_fn_t newsig_fn, void *newsig_priv, hs_stats_t * stats)
{
    int ret;
    uint8_t type;
    uint32_t length, offset;
    int kind;
    char *stats_str;
    hs_mdfour_t newsum;

    _hs_trace("**** begin %s", __FUNCTION__);
    bzero(stats, sizeof *stats);
    if (_hs_check_gd_header(ltread_fn, ltread_priv) < 0)
	return -1;

    hs_mdfour_begin(&newsum);

    while (1) {
	 ret = _hs_inhale_command(ltread_fn, ltread_priv, &kind, &length, &offset);
	 if (ret < 0) {
	      _hs_error("error while trying to read command byte");
	      return -1;
	 }

	 if (kind == op_kind_eof) {
	      _hs_trace("op_eof");
	      break;		/* We're done! Cool bananas */
	 } else if (kind == op_kind_literal) {
	      _hs_trace("LITERAL(len=%d)", length);
	      ret = _hs_copy(length, ltread_fn, ltread_priv, write_fn,
			     write_priv, &newsum);
	      return_val_if_fail(ret >= 0, -1);
	      stats->lit_cmds++;
	      stats->lit_bytes += length;
	 } else if (kind == op_kind_signature) {
	      _hs_trace("SIGNATURE(len=%d)", length);
	      ret = _hs_copy(length,
			     ltread_fn, ltread_priv,
			     newsig_fn, newsig_priv,
			     NULL);
	      return_val_if_fail(ret >= 0, -1);
	      stats->sig_cmds++;
	      stats->sig_bytes += length;
	} else if (kind == op_kind_copy) {
	     _hs_trace("COPY(offset=%d, len=%d)", offset, length);
	     ret = _hs_copy_ofs(offset, length,
				oldread_fn, oldread_priv,
				write_fn, write_priv,
				&newsum);
	     return_val_if_fail(ret >= 0, -1);
	     stats->copy_cmds++;
	     stats->copy_bytes += length;
	} else if (kind == op_kind_checksum) {
	     _hs_trace("CHECKSUM(len=%d)", length);
	     ret = _hs_check_checksum(ltread_fn, ltread_priv, length, &newsum);
	} else {
	    _hs_fatal("unexpected op kind %d!", type);
	}
    }

    if (ret < 0) {
	return ret;
    }

    stats_str = hs_format_stats(stats);
    _hs_trace("completed: %s", stats_str);
    free(stats_str);
    
    return 1;
}
