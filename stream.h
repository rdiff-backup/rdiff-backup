/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- library for network deltas
 * $Id$
 * 
 * Copyright (C) 2000, 2001 by Martin Pool <mbp@samba.org>
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

                /* Two wars in a lifetime bear hard on the little places.
                 * In winter when storms come rushing out of the dark,
                 * And the bay boils like a cauldron of sharks,
                 * The old remember the trenches at Paschendale
                 * And sons who died on the Burma Railway. */


/*
 * Stream private data
 */
typedef struct rs_simpl {
        /* Buffer of data left over in the scoop.  Allocation is
         * scoop_buf..scoop_alloc, and scoop_next[0..scoop_avail]
         * contains valid data. */
        char       *scoop_buf;
        char       *scoop_next;
        size_t      scoop_alloc;
        size_t      scoop_avail;
        
        /* If USED is >0, then buf contains that much literal data to
         * be sent out. */
        char        lit_buf[16];
        int         lit_len;

        /* If COPY_LEN is >0, then that much data should be copied
         * through from the input. */
        int         copy_len;
} rs_simpl_t;




int rs_stream_is_empty(rs_stream_t *stream);
int rs_stream_copy(rs_stream_t *stream, int len);
void rs_stream_check(rs_stream_t *stream);
void rs_stream_check_exit(rs_stream_t const *stream);


int rs_tube_catchup(rs_stream_t *);
void rs_blow_literal(rs_stream_t *, void const *buf, size_t len);

void rs_blow_copy(rs_stream_t *, int len);

int rs_tube_is_idle(rs_stream_t const *);
void rs_check_tube(rs_stream_t *);

void rs_scoop_advance(rs_stream_t *stream, size_t len);
rs_result rs_scoop_readahead(rs_stream_t *stream, size_t len, void **ptr);
rs_result rs_scoop_read(rs_stream_t *stream, size_t len, void **ptr);
rs_result rs_scoop_read_rest(rs_stream_t *stream, size_t *len, void **ptr);
