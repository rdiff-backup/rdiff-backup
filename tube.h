/*				       	-*- c-file-style: "bsd" -*-
 *
 * libhsync -- library for network deltas
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool <mbp@samba.org>
 * 
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU Lesser General Public License as published by
 * the Free Software Foundation; either version 2.1 of the License, or
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


void _hs_tube_init(hs_stream_t *stream);

int _hs_tube_catchup(hs_stream_t *stream);
void _hs_blow_literal(hs_stream_t *stream, void const *buf, size_t len);

void _hs_blow_copy(hs_stream_t *stream, int len);

int _hs_tube_is_idle(hs_stream_t const *stream);
void _hs_check_tube(hs_stream_t *stream);
