/*				       	-*- c-file-style: "bsd" -*-
 * rproxy -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool <mbp@humbug.org.au>
 * 
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU Lesser General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Lesser General Public License for more details.
 * 
 * You should have received a copy of the GNU Lesser General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

int _hs_send_literal(hs_write_fn_t write_fn,
		     void *write_priv,
		     int kind, byte_t const *buf, 
		     size_t amount);

/* ========================================

   emit/inhale commands */

struct hs_op_kind_name {
    char const     *name;
    int const       code;
};

extern struct hs_op_kind_name const _hs_op_kind_names[];

int             _hs_emit_signature_cmd(hs_write_fn_t write_fn,
				       void *write_priv, size_t size);

int             _hs_emit_filesum(hs_write_fn_t write_fn, void *write_priv,
				 byte_t const *buf, size_t size);

int             _hs_emit_literal_cmd(hs_write_fn_t write_fn, void *write_priv,
				     size_t size);

int             _hs_emit_checksum_cmd(hs_write_fn_t, void *, uint32_t size);

int             _hs_emit_copy(hs_write_fn_t write_fn, void *write_priv,
			      off_t offset, size_t length,

			      hs_stats_t * stats);


int             _hs_emit_eof(hs_write_fn_t write_fn, void *write_priv,
			     hs_stats_t * stats);

