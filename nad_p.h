/*                                      -*- c-file-style: "bsd" -*-
 * rproxy -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 1999, 2000 by Martin Pool
 * Copyright (C) 1999 by Andrew Tridgell
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

/* private header file for nad-encoding */

extern const int hs_encode_job_magic;

struct hs_encode_job {
    int                 dogtag;

    int                 in_fd;

    /* mapptr input: MAP_P points to available data, located at
     * MAP_OFF in the file, and there are MAP_LEN of valid bytes
     * there.  They are updated at the start of each iteration. */
    hs_map_t           *in_map;
    byte_t const       *map_p;
    size_t              map_len;
    hs_off_t            map_off;

    /* On the next iteration, we'll try to generate the checksum for a
     * block at this location. */
    hs_sumset_t        *sums;
    hs_stats_t         *stats;

    /* Accumulates a sum of the whole file as we see it.  Never
     * reset. */
    hs_mdfour_t         filesum;
    size_t              filesum_cursor;

    /* Things for the new checksum. */
    hs_off_t            sum_cursor;
    size_t              new_block_len;
    size_t              new_strong_len;

    /* This points to the rolling sums used for searching. */
    hs_off_t            search_cursor;
    size_t              search_block_len;
    hs_rollsum_t       *rollsum;

    /* This looks after literal data which has been scanned but not
     * yet transmitted.  Everything between LITERAL_CURSOR (incl) and
     * SEARCH_CURSOR (excl) needs to be sent out.  If they're the
     * same, there is no literal data at the moment.  This must also
     * be flushed before we allow it to move out of the window. */
    hs_off_t            literal_cursor;

    int                 seen_eof;

    hs_membuf_t        *sig_tmpbuf;
    _hs_copyq_t         copyq;

    hs_write_fn_t       write_fn;
    void               *write_priv;
};


void _hs_nad_search_iter(hs_encode_job_t *);

void _hs_nad_got_copy(hs_encode_job_t *job, hs_off_t off, size_t len);

void _hs_nad_flush_literal(hs_encode_job_t *);
