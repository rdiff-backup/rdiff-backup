/*=                                     -*- c-file-style: "linux" -*-
 *
 * libhsync -- library for network deltas
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool <mbp@linuxcare.com.au>
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


/*
 * Stream private data
 */
typedef struct hs_simpl {
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
} hs_simpl_t;




int _hs_stream_is_empty(hs_stream_t *stream);
int _hs_stream_copy(hs_stream_t *stream, int len);
void _hs_stream_check(hs_stream_t *stream);
void _hs_stream_check_exit(hs_stream_t const *stream);


int _hs_tube_catchup(hs_stream_t *);
void _hs_blow_literal(hs_stream_t *, void const *buf, size_t len);

void _hs_blow_copy(hs_stream_t *, int len);

int _hs_tube_is_idle(hs_stream_t const *);
void _hs_check_tube(hs_stream_t *);

void _hs_scoop_advance(hs_stream_t *stream, size_t len);
enum hs_result _hs_scoop_readahead(hs_stream_t *stream, size_t len, void **ptr);
enum hs_result _hs_scoop_read(hs_stream_t *stream, size_t len, void **ptr);
enum hs_result _hs_scoop_read_rest(hs_stream_t *stream, size_t *len, void **ptr);
