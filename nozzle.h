/*=                                     -*- c-file-style: "bsd" -*-
 *
 * libhsync -- library for network deltas
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool <mbp@samba.org>
 * 
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public License
 * as published by the Free Software Foundation; either version 2.1 of
 * the License, or (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 * 
 * You should have received a copy of the GNU Lesser General Public
 * License along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */


typedef struct hs_nozzle hs_nozzle_t;

hs_nozzle_t * _hs_nozzle_new(FILE *file, hs_stream_t *stream,
			     int buf_len, char const *mode);

hs_nozzle_t * _hs_nozzle_new_fd(int fd, hs_stream_t *stream,
				int buf_len, char const *mode);
void _hs_nozzle_delete(hs_nozzle_t *iot);

int _hs_nozzle_in(hs_nozzle_t *iot);
int _hs_nozzle_out(hs_nozzle_t *iot);

void _hs_nozzle_drain(hs_nozzle_t *out_nozzle, hs_stream_t *stream);

void _hs_nozzle_siphon(hs_stream_t *stream, hs_nozzle_t *in_nozzle,
		      hs_nozzle_t *out_nozzle);
