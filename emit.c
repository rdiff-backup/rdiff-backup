/* -*- mode: c; c-file-style: "gnu" -*-  */

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


static int
_hs_fits_in_byte (uint32_t val)
{
  return val <= UINT8_MAX;
}


static int
_hs_fits_in_short (uint32_t val)
{
  return val <= UINT16_MAX;
}


static int
_hs_fits_inline (uint32_t val)
{
  return val > 1 && val < (op_literal_last - op_literal_1);
}


int
_hs_emit_eof (rs_write_fn_t write_fn, void *write_priv)
{
  return _hs_write_netbyte (write_fn, write_priv, op_eof);
}


/* Emit the command header for literal data.  This will do either literal
   or signature depending on BASE. */
int
_hs_emit_chunk_cmd (rs_write_fn_t write_fn,
		    void *write_priv,
		    uint32_t size,
		    int base)
{
  assert (base == op_literal_1  ||  base == op_signature_1);
  
  if (_hs_fits_inline (size))
    {
      return _hs_write_netbyte (write_fn, write_priv,
				base + size - 1);
    }
  else if (_hs_fits_in_byte (size))
    {
      if (_hs_write_netbyte (write_fn, write_priv,
			     op_literal_byte - op_literal_1 + base) < 0)
	return -1;
      return _hs_write_netbyte (write_fn, write_priv, (uint8_t) size);
    }
  else if (_hs_fits_in_short (size))
    {
      if (_hs_write_netbyte (write_fn, write_priv,
			     op_literal_short - op_literal_1 + base) < 0)
	return -1;
      return _hs_write_netshort (write_fn, write_priv, (uint16_t) size);
    }
  else
    {
      if (_hs_write_netlong (write_fn, write_priv,
			     op_literal_int - op_literal_1 + base) < 0)
	return -1;
      return _hs_write_netlong (write_fn, write_priv, size);
    }
}


int
_hs_emit_copy (rs_write_fn_t write_fn, void *write_priv,
	       uint32_t offset, uint32_t length,
	       hs_stats_t *stats)
{
  int ret;

  stats->copy_cmds++;
  stats->copy_bytes += length;
  
  _hs_trace ("Writing COPY(%d, %d)", offset, length);

  /* TODO: All the other encoding options */
  ret = _hs_write_netbyte (write_fn, write_priv, op_copy_int_int);
  return_val_if_fail (ret > 0, -1);

  ret = _hs_write_netlong (write_fn, write_priv, offset);
  return_val_if_fail (ret > 0, -1);

  ret = _hs_write_netlong (write_fn, write_priv, length);
  return_val_if_fail (ret > 0, -1);
  
  return 1;
}


