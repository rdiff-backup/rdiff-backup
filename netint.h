/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * libhsync -- library for network deltas
 * $Id$
 * 
 * Copyright (C) 1999, 2000, 2001 by Martin Pool <mbp@samba.org>
 * Copyright (C) 1999 by Andrew Tridgell <tridge@samba.org>
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

hs_result hs_squirt_byte(hs_stream_t *stream, unsigned char d);
hs_result hs_squirt_netint(hs_stream_t *stream, hs_long_t d, int len);
hs_result hs_squirt_n4(hs_stream_t *stream, int val);

hs_result hs_suck_netint(hs_stream_t *stream, hs_long_t *v, int len);
hs_result hs_suck_byte(hs_stream_t *stream, unsigned char *);
hs_result hs_suck_n4(hs_stream_t *stream, int *);

int hs_fits_in_n1(size_t val);
int hs_fits_in_n2(size_t val);
int hs_fits_in_n4(size_t val);
int hs_int_len(off_t val);
