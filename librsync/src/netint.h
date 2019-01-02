/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- library for network deltas
 *
 * Copyright (C) 1999, 2000, 2001 by Martin Pool <mbp@sourcefrog.net>
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

rs_result rs_squirt_byte(rs_job_t *, unsigned char d);
rs_result rs_squirt_netint(rs_job_t *, rs_long_t d, int len);
rs_result rs_squirt_n4(rs_job_t *, int val);

rs_result rs_suck_netint(rs_job_t *, rs_long_t *v, int len);
rs_result rs_suck_byte(rs_job_t *, unsigned char *);
rs_result rs_suck_n4(rs_job_t *, int *);

int rs_int_len(rs_long_t val);
