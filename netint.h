/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * libhsync -- library for network deltas
 * $Id$
 * 
 * Copyright (C) 1999, 2000, 2001 by Martin Pool <mbp@samba.org>
 * Copyright (C) 1999 by Andrew Tridgell <mbp@samba.org>
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

void hs_squirt_n32(hs_stream_t *stream, int d);
void hs_squirt_n8(hs_stream_t *stream, int d);

hs_result hs_suck_n32(hs_stream_t *stream, int *v);
hs_result hs_suck_n8(hs_stream_t *stream, int *v);
hs_result hs_suck_netint(hs_stream_t *stream, int len, int *v);

int hs_fits_in_n8(size_t val);
int hs_fits_in_n16(size_t val);
int hs_fits_in_n32(size_t val);
int hs_int_len(off_t val);
