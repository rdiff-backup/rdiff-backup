/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- the library for network deltas
 *
 * Copyright (C) 2000, 2001 by Martin Pool <mbp@sourcefrog.net>
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

typedef struct rs_filebuf rs_filebuf_t;

rs_filebuf_t *rs_filebuf_new(FILE *f, size_t buf_len);

void rs_filebuf_free(rs_filebuf_t *fb);

rs_result rs_infilebuf_fill(rs_job_t *, rs_buffers_t *buf, void *fb);

rs_result rs_outfilebuf_drain(rs_job_t *, rs_buffers_t *, void *fb);
