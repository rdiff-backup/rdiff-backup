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

char const *hs_log_domain = "libhsync";

static int
_hs_copy(const uint32_t length,
	 rs_read_fn_t read_fn, void *read_priv,
	 rs_write_fn_t write_fn, void *write_priv)
{
    ssize_t ret;
    char *buf;

    buf = malloc(length);

    ret = read_fn(read_priv, buf, length);
    if (ret >= 0 && (ret < (int32_t) length)) {
	errno = ENODATA;
	goto fail;
    }

    ret = write_fn(write_priv, buf, ret);
    if ((unsigned) ret != length)
	goto fail;

    free(buf);
    return length;

  fail:
    free(buf);
    return -1;
}



static int _hs_check_gd_header(rs_read_fn_t ltread_fn, void *ltread_priv)
{
    int ret;
    uint32_t remote_magic, expect;

    expect = HS_LT_MAGIC;

    ret = _hs_read_netint(ltread_fn, ltread_priv, &remote_magic);
    return_val_if_fail(ret == 4, -1);
    if (remote_magic != expect) {
	_hs_fatal("version mismatch: %#08x != %#08x",
		  remote_magic, expect);
	errno = EBADMSG;
	return -1;
    }
    return 0;
}



static int _hs_is_gd_eof(uint8_t cmd)
{
    return cmd == 0;
}


static int
_hs_is_gd_copy(uint8_t type, uint32_t * offset, uint32_t * length,
	       rs_read_fn_t read_fn, void *read_priv)
{
    uint8_t tmp8;
    uint16_t tmp16;
    uint32_t tmp32;

    if (type < op_copy_short_byte || type > op_copy_int_int)
	return 0;		/* nope */

    /* read the first parameter, being the offset */
    if (type == op_copy_short_byte
	|| type == op_copy_short_short || type == op_copy_short_int) {
	if (_hs_read_netshort(read_fn, read_priv, &tmp16) != sizeof tmp16)
	    return -1;
	*offset = tmp16;
    } else {
	/* must be an int */
	if (_hs_read_netint(read_fn, read_priv, &tmp32) != sizeof tmp32)
	    return -1;
	*offset = tmp32;
    }

    /* read the second, being the length. */
    if (type == op_copy_short_byte || type == op_copy_int_byte) {
	if (_hs_read_netbyte(read_fn, read_priv, &tmp8) != sizeof tmp8)
	    return -1;
	*length = tmp8;
    } else if (type == op_copy_short_short || type == op_copy_int_short) {
	if (_hs_read_netshort(read_fn, read_priv, &tmp16) != sizeof tmp16)
	    return -1;
	*length = tmp16;
    } else {
	if (_hs_read_netint(read_fn, read_priv, &tmp32) != sizeof tmp32)
	    return -1;
	*length = tmp32;
    }

    return 1;
}


static int
_hs_is_gd_literal(uint8_t cmd,
		  uint32_t * length, rs_read_fn_t read_fn, void *read_priv)
{
    int ret = 0;

    if (cmd == op_literal_int) {
	ret = _hs_read_netint(read_fn, read_priv, length);
    } else if (cmd == op_literal_short) {
	uint16_t tmp;
	ret = _hs_read_netshort(read_fn, read_priv, &tmp);
	*length = tmp;
    } else if (cmd == op_literal_byte) {
	uint8_t tmp;
	ret = _hs_read_netbyte(read_fn, read_priv, &tmp);
	*length = tmp;
    } else if (cmd >= op_literal_1 && cmd < op_literal_byte) {
	*length = cmd - op_literal_1 + 1;
	ret = 1;
    }

    return ret;
}



static int
_hs_is_gd_signature(uint8_t cmd,
		    uint32_t * length,
		    rs_read_fn_t read_fn, void *read_priv)
{
    int ret = 0;

    if (cmd == op_signature_int) {
	ret = _hs_read_netint(read_fn, read_priv, length);
    } else if (cmd == op_signature_short) {
	uint16_t tmp;
	ret = _hs_read_netshort(read_fn, read_priv, &tmp);
	*length = tmp;
    } else if (cmd == op_signature_byte) {
	uint8_t tmp;
	ret = _hs_read_netbyte(read_fn, read_priv, &tmp);
	*length = tmp;
    } else if (cmd >= op_signature_1 && cmd < op_signature_byte) {
	*length = cmd - op_signature_1 + 1;
	ret = 1;
    }

    return ret;
}



ssize_t
hs_decode(rs_readofs_fn_t oldread_fn, void *oldread_priv,
	  rs_write_fn_t write_fn, void *write_priv,
	  rs_read_fn_t ltread_fn, void *ltread_priv,
	  rs_write_fn_t newsig_fn, void *newsig_priv, hs_stats_t * stats)
{
    int ret;
    uint8_t type;
    uint32_t length, offset;

    _hs_trace("**** begin %s", __FUNCTION__);
    bzero(stats, sizeof *stats);
    if (_hs_check_gd_header(ltread_fn, ltread_priv) < 0)
	return -1;

    while (1) {
	ret = ltread_fn(ltread_priv, &type, 1);
	if (ret > 1) {
	    _hs_error("long read while trying to get a one-byte command!");
	    return -1;
	} else if (ret < 0) {
	    _hs_error("error while trying to read command byte");
	    return -1;
	} else if (ret == 0) {
	    _hs_error("unexpected end of file; "
		      "assuming that this was meant to be the end");
	    break;
	}

	if (_hs_is_gd_eof(type) > 0) {
	    _hs_trace("op_eof");
	    break;		/* We're done! Cool bananas */
	} else if (_hs_is_gd_literal(type, &length, ltread_fn, ltread_priv)
		   > 0) {
	    _hs_trace("op_literal len=%d", length);
	    ret = _hs_copy(length, ltread_fn, ltread_priv, write_fn,
			   write_priv);
	    return_val_if_fail(ret >= 0, -1);
	    stats->lit_cmds++;
	    stats->lit_bytes += length;
	} else
	    if (_hs_is_gd_signature(type, &length, ltread_fn, ltread_priv)
		> 0) {
	    _hs_trace("op_signature len=%d", length);
	    ret = _hs_copy(length, ltread_fn, ltread_priv, newsig_fn,
			   newsig_priv);
	    return_val_if_fail(ret >= 0, -1);
	    stats->sig_cmds++;
	    stats->sig_bytes += length;
	} else if (_hs_is_gd_copy(type, &offset, &length,
				  ltread_fn, ltread_priv) > 0) {
	    _hs_trace("op_copy offset=%d, len=%d", offset, length);
	    ret = _hs_copy_ofs(offset, length,
			       oldread_fn, oldread_priv,
			       write_fn, write_priv);
	    return_val_if_fail(ret >= 0, -1);
	    stats->copy_cmds++;
	    stats->copy_bytes += length;
	} else {
	    _hs_fatal("unexpected command %d!", type);
	}
    }

    if (ret < 0) {
	return ret;
    }

    _hs_trace("completed"
	      ": literal[%d cmds, %d bytes], "
	      "signature[%d cmds, %d bytes], "
	      "copy[%d cmds, %d bytes]",
	      stats->lit_cmds, stats->lit_bytes,
	      stats->sig_cmds, stats->sig_bytes,
	      stats->copy_cmds, stats->copy_bytes);
    return 1;
}
