/* -*- mode: c; c-file-style: "k&r" -*-  */

/* litbuf -- buffer of data waiting to go out as signature or literal
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
#include "hsyncproto.h"
#include "private.h"
#include "emit.h"


/* Queue byte VALUE into the literal-data buffer. */
int _hs_append_literal(hs_membuf_t * litbuf, char value)
{
    hs_membuf_write(litbuf, &value, sizeof value);

    return 0;
}


/* Write out accumulated data.  We've built up some literal or
   signature data waiting to go out in LITBUF, and we're ready to
   write it to WRITE_FN.  CODE_BASE is either op_literal_1 or
   op_signature_1 depending on which it is; STATS is updated
   appropriately. */
ssize_t
_hs_push_literal_buf(hs_membuf_t * litbuf,
		      hs_write_fn_t write_fn, void *write_priv,
		      hs_stats_t * stats,
		      int kind)
{
    int ret;
    off_t amount;

    amount = hs_membuf_tell(litbuf);
    assert(amount >= 0);

    if (amount == 0) {
	 /* buffer is empty */
	return 0;
    }

     assert(kind == op_kind_literal || kind == op_kind_signature);

     _hs_trace("flush %d bytes of %s data",
	      (int) amount,
	      kind == op_kind_literal ? "literal" : "signature");

    if (_hs_emit_chunk_cmd(write_fn, write_priv, amount, kind) < 0)
	return -1;

    ret = _hs_copy_ofs(0, amount,
		       hs_membuf_read_ofs, litbuf, write_fn, write_priv);
    return_val_if_fail(ret > 0, -1);

    if (kind == op_kind_literal) {
	stats->lit_cmds++;
	stats->lit_bytes += amount;
    } else {
	assert(kind == op_kind_signature);
	stats->sig_cmds++;
	stats->sig_bytes += amount;
    }

    /* Reset the literal buffer */
    hs_membuf_truncate(litbuf);

    return 0;
}
