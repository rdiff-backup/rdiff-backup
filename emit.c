/* -*- mode: c; c-file-style: "k&r" -*-  */

/* emit -- emit encoded commands to the client
   Copyright (C) 2000 by Martin Pool <mbp@humbug.org.au>
   Copyright (C) 1999 by Andrew Tridgell

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
#include "hsyncproto.h"
#include "private.h"
#include "emit.h"

static int _hs_fits_in_byte(uint32_t val)
{
    return val <= UINT8_MAX;
}


static int _hs_fits_in_short(uint32_t val)
{
    return val <= UINT16_MAX;
}


static int _hs_fits_in_int(uint64_t val)
{
    return val <= UINT32_MAX;
}


static int _hs_fits_inline(uint32_t val)
{
    return val > 1 && val < (op_literal_last - op_literal_1);
}


static int _hs_int_len(uint32_t val)
{
    if (_hs_fits_in_byte(val))
	return 1;
    else if (_hs_fits_in_short(val))
	return 2;
    else if (_hs_fits_in_int(val))
	return 4;
    else
	assert(0 && "can't handle files this long yet");
}


int _hs_emit_eof(rs_write_fn_t write_fn, void *write_priv,
		 hs_stats_t *stats UNUSED)
{
    return _hs_write_netbyte(write_fn, write_priv, op_eof);
}


/* Emit the command header for literal data.  This will do either literal
   or signature depending on BASE. */
int
_hs_emit_chunk_cmd(rs_write_fn_t write_fn,
		   void *write_priv, uint32_t size,
		   enum hs_op_kind kind)
{
     int type, cmd, base;

     assert(kind == op_kind_literal || kind == op_kind_signature);

     if (kind == op_kind_literal)
	  base = op_literal_1;
     else
	  base = op_signature_1;

     if (_hs_fits_inline(size)) {
	  return _hs_write_netbyte(write_fn, write_priv, base + size - 1);
     }
     
     type = _hs_int_len(size);
     cmd = base + op_literal_byte - op_literal_1;
     if (type == 1) {
	  ;
     } else if (type == 2) {
	  cmd += 1;
     } else if (type == 4) {
	  cmd += 2;
     } else {
	  assert(0);
     }

     if (_hs_write_netbyte(write_fn, write_priv, cmd) < 0)
	  return -1;

     return _hs_write_netvar(write_fn, write_priv, size, type);
}


int
_hs_emit_copy(rs_write_fn_t write_fn, void *write_priv,
	      uint32_t offset, uint32_t length, hs_stats_t * stats)
{
    int ret;
    int len_type, off_type;
    int cmd;

    stats->copy_cmds++;
    stats->copy_bytes += length;

    _hs_trace("Writing COPY(off=%d, len=%d)", offset, length);
    len_type = _hs_int_len(length);
    off_type = _hs_int_len(offset);

    /* We cannot specify the offset as a byte, because that would so
       rarely be useful.  */
    if (off_type == 1)
	 off_type = 2;

    /* Make sure this formula lines up with the values in hsyncproto.h */

    if (off_type == 2) {
	cmd = op_copy_short_byte;
    } else if (off_type == 4) {
	cmd = op_copy_int_byte;
    } else {
	 fprintf(stderr, "can't pack offset %d!\n", offset);
	 abort();
    }

    if (len_type == 1) {
	cmd += 0;
    } else if (len_type == 2) {
	cmd += 1;
    } else if (len_type == 4) {
	cmd += 2;
    } else {
	assert(0 && "unimplemented");
    }

    ret = _hs_write_netbyte(write_fn, write_priv, cmd);
    return_val_if_fail(ret > 0, -1);

    ret = _hs_write_netvar(write_fn, write_priv, offset, off_type);
    return_val_if_fail(ret > 0, -1);

    ret = _hs_write_netvar(write_fn, write_priv, length, len_type);
    return_val_if_fail(ret > 0, -1);

    return 1;
}
