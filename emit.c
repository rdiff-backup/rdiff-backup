/* -*- mode: c; c-file-style: "bsd" -*-  */
/* $Id$ */
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

static int
_hs_fits_in_byte(size_t val)
{
    return val <= UINT8_MAX;
}


static int
_hs_fits_in_short(size_t val)
{
    return val <= UINT16_MAX;
}


static int
_hs_fits_in_int(size_t val)
{
    return val <= UINT32_MAX;
}


static int
_hs_int_len(hs_off_t val)
{
    if (_hs_fits_in_byte(val))
	return 1;
    else if (_hs_fits_in_short(val))
	return 2;
    else if (_hs_fits_in_int(val))
	return 4;
    else {
	_hs_fatal("can't handle files this long yet");
    }
}


int _hs_emit_eof(hs_write_fn_t write_fn, void *write_priv,
		 UNUSED(hs_stats_t *stats))
{
    _hs_trace("Writing EOF");
    return _hs_write_netbyte(write_fn, write_priv, (uint8_t) op_eof);
}


int
_hs_emit_checksum_cmd(hs_write_fn_t write_fn, void *write_priv, size_t size)
{
     int ret;
     
     _hs_trace("Writing CHECKSUM(len=%d)", size);
     ret = _hs_write_netbyte(write_fn, write_priv,
			     (uint8_t) op_checksum_short);
     if (ret != 1)
	  return -1;

     assert(_hs_fits_in_short(size));
     ret = _hs_write_netshort(write_fn, write_priv, (uint16_t) size);
     if (ret != 2)
	  return -1;

     return 3;
}



int
_hs_emit_filesum(hs_write_fn_t write_fn, void *write_priv,
		 char const *buf, size_t size)
{
     int ret;

     ret = _hs_emit_checksum_cmd(write_fn, write_priv, size);
     if (ret <= 0)
	  return -1;

     ret = _hs_write_loop(write_fn, write_priv, buf, size);
     if (ret != (int) size)
	  return -1;

     return 3 + size;
}


/* Emit the command header for literal data. */
int
_hs_emit_literal_cmd(hs_write_fn_t write_fn, void *write_priv, size_t size)
{
     int type;
     uint8_t cmd;
     
     _hs_trace("Writing LITERAL(len=%d)", size);

     if ((size >= 1)  &&  (size < (op_literal_last - op_literal_1))) {
	 cmd = (uint8_t) (op_literal_1 + size - 1);
	 return _hs_write_netbyte(write_fn, write_priv, cmd);
     }
     
     type = _hs_int_len(size);
     if (type == 1) {
	  cmd = (uint8_t) op_literal_byte;
     } else if (type == 2) {
	  cmd = (uint8_t) op_literal_short;
     } else if (type == 4) {
	 cmd = (uint8_t) op_literal_int;
     } else {
	 _hs_fatal("can't happen!");
     }

     if (_hs_write_netbyte(write_fn, write_priv, cmd) < 0)
	  return -1;

     return _hs_write_netvar(write_fn, write_priv, size, type);
}


/* Emit the command header for signature data. */
int
_hs_emit_signature_cmd(hs_write_fn_t write_fn, void *write_priv,
		       size_t size)
{
     int type;
     uint8_t cmd;
     
     _hs_trace("Writing SIGNATURE(len=%d)", size);

     if ((size >= 1)  &&  (size < (op_signature_last - op_signature_1))) {
	 cmd = (uint8_t) (op_signature_1 + size - 1);
	  return _hs_write_netbyte(write_fn, write_priv, cmd);
     }
     
     type = _hs_int_len((long) size);
     if (type == 1) {
	  cmd = (uint8_t) op_signature_byte;
     } else if (type == 2) {
	  cmd = (uint8_t) op_signature_short;
     } else if (type == 4) {
	  cmd = (uint8_t) op_signature_int;
     } else {
	 _hs_fatal("can't happen!");
     }

     if (_hs_write_netbyte(write_fn, write_priv, cmd) < 0)
	  return -1;

     return _hs_write_netvar(write_fn, write_priv, size, type);
}


int
_hs_emit_copy(hs_write_fn_t write_fn, void *write_priv,
	      hs_off_t offset, size_t length, hs_stats_t * stats)
{
    int ret;
    int len_type, off_type;
    int cmd;

    stats->copy_cmds++;
    stats->copy_bytes += length;

    _hs_trace("Writing COPY(off=%ld, len=%ld)", (long) offset, (long) length);
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
	_hs_fatal("can't pack offset %ld!", offset);
    }

    if (len_type == 1) {
	cmd += 0;
    } else if (len_type == 2) {
	cmd += 1;
    } else if (len_type == 4) {
	cmd += 2;
    } else {
	 _hs_fatal("can't pack length %ld as a %d byte number",
		   (long) length, len_type);
    }

    ret = _hs_write_netbyte(write_fn, write_priv, (uint8_t) cmd);
    if (ret < 0) return -1;

    ret = _hs_write_netvar(write_fn, write_priv, offset, off_type);
    if (ret < 0) return -1;

    ret = _hs_write_netvar(write_fn, write_priv, length, len_type);
    if (ret < 0) return -1;

    return 1;
}
