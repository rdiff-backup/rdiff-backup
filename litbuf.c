/*				       	-*- c-file-style: "bsd" -*-
 * rproxy -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool
 * 
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

/* TODO: You know, queueing things up to the size of either the
 * typical TCP output buffer (32kb) or the typical packet limit (~1500
 * or ~1300) might be good.  I wonder if we can what the buffer size
 * is? */

#include "includes.h"


/* Queue byte VALUE into the literal-data buffer. */
int
_hs_append_literal(hs_membuf_t * litbuf, byte_t value)
{
    hs_membuf_write(litbuf, &value, sizeof value);	/* LEAK HERE! */

    return 0;
}


/* Write out accumulated data.  We've built up some literal or signature data 
   waiting to go out in LITBUF, and we're ready to write it to WRITE_FN.
   CODE_BASE is either op_literal_1 or op_signature_1 depending on which it
   is; STATS is updated appropriately. */
ssize_t
_hs_push_literal_buf(hs_membuf_t * litbuf,
		     hs_write_fn_t write_fn, void *write_priv,
		     hs_stats_t * stats, int kind)
{
    size_t        amount;

    amount = hs_membuf_tell(litbuf);
    assert(amount >= 0);

    if (amount == 0) {
	/* buffer is empty */
	return 0;
    }

    assert(kind == op_kind_literal || kind == op_kind_signature);

    if (_hs_send_literal(write_fn, write_priv, kind, litbuf->buf, amount) < 0)
	return -1;

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
