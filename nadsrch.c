/*=                                     -*- c-file-style: "bsd" -*-
 * rproxy -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 1999, 2000 by Martin Pool <mbp@humbug.org.au>
 * Copyright (C) 1999 by Andrew Tridgell <tridge@samba.org>
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
                               | To walk on water you've gotta sink 
                               | in the ice.
                               |   -- Shihad, `The General Electric'.
                              */



/*
 * TODO: Rolling checksums, rather than computing the weak checksum
 * from scratch every time -- at least only do this in `painful
 * honesty' mode.
 */

/*
 * XXX: Copy commands are not sent with the right length -- they
 * should be shortened when approaching EOF.
 *
 * XXX: What happens when we're searching a file that is now longer
 * than it was before?  Can we still match the short block from the
 * last one, or do we not care?
 *
 * The answer is that using the current algorithm we cannot 
 */

#include "includes.h"
#include "mapptr.h"
#include "nad_p.h"
#include "search.h"


/*
 * Check whether AVAIL bytes is enough data to do a useful search
 * operation: this means that either it is at least one full search
 * block in length, or we are approaching the end of the file.
 *
 * On returning true, SEARCH_LEN is set to the length of the search
 * block.
 */
static int
_hs_nad_can_search(hs_encode_job_t *job,
                   size_t *search_len)
{
    size_t avail = job->map_len + job->map_off - job->search_cursor;

    if (avail == 0) {
        return 0;
    } else if (avail >= job->search_block_len) {
/*          _hs_trace("plenty of data left; map_len=%d, map_off=%ld, " */
/*                    "search_cursor=%ld, avail=%ld", */
/*                    job->map_len, (long) job->map_off, (long) job->search_cursor, */
/*                    (long) avail); */
        *search_len = job->search_block_len;
        return 1;
    } else if (job->seen_eof) {
/*          _hs_trace("only %d bytes available to search near eof", */
/*                    avail); */
        *search_len = avail;
        return 1;
    } else {
/*          _hs_trace("only %d bytes left but not at eof, need to read again", */
/*                    avail); */
        return 0;
    }
}


/*
 * Try to match at the current search cursor position.  If we find
 * one, then emit an appropriate copy command.  If not, emit a minimal
 * literal command and try again next time.
 */
void
_hs_nad_search_iter(hs_encode_job_t *job)
{
    size_t              this_len; /* length of this match */
    hs_weak_sum_t       this_weak;
    off_t            match_where; /* location of match in old file */
    byte_t const       *base = job->map_p - job->map_off;

    if (job->search_cursor >= job->map_len + job->map_off)
        return;

    /* While there's enough data left to do a search: either there's a
     * whole block left, or we're approaching EOF. */
    while (_hs_nad_can_search(job, &this_len)) {
/*          _hs_trace("compare %lu byte block @%lu", (unsigned long) this_len, */
/*                    (unsigned long) job->search_cursor); */

        this_weak = _hs_calc_weak_sum(base + job->search_cursor, this_len);

        if (_hs_search_for_block(this_weak,
                                 base + job->search_cursor, this_len,
                                 job->sums, job->stats,
                                 &match_where)) {
            _hs_trace("found a strong match @%lu+%lu",
                      (unsigned long) match_where,
                      (unsigned long) this_len);
            _hs_nad_got_copy(job, match_where, this_len);
        } else {
            /* If not matched, we just allow searching to proceed.
             * The intermediate literal data will be sent out when we
             * either find another match, need to do more input, or
             * reach EOF. */
            job->search_cursor++;
        }
    }
}
