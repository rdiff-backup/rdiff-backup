/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- the library for network deltas
 * $Id$
 * 
 * Copyright (C) 1999, 2000, 2001 by Martin Pool <mbp@sourcefrog.net>
 * Copyright (C) 1999 by Andrew Tridgell
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

/* 
 * This file contains code for searching the sumset for matching
 * values.
 */

/* 
 * TODO: The common case is that the next block in both streams
 * match. Can we make that a bit faster at all?  We'd need to perhaps
 * add a link forward between blocks in the sum_struct corresponding
 * to the order they're found in the input; then before doing a search
 * we can just check that pointer.
 */

#include <config.h>

#include <string.h>
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>

#include "librsync.h"
#include "trace.h"
#include "util.h"
#include "sumset.h"
#include "search.h"
#include "checksum.h"
#include "protocol.h"


#define TABLESIZE (1<<16)
#define NULL_TAG (-1)


#define gettag2(s1,s2) (((s1) + (s2)) & 0xFFFF)
#define gettag(sum) gettag2((sum)&0xFFFF,(sum)>>16)


static int
rs_compare_targets(rs_target_t const *t1, rs_target_t const *t2)
{
    return ((int) t1->t - (int) t2->t);
}


rs_result
rs_build_hash_table(rs_signature_t * sums)
{
    int                     i;

    sums->tag_table = calloc(TABLESIZE, sizeof sums->tag_table[0]);
    if (!sums->tag_table)
        return RS_MEM_ERROR;
    
    if (sums->count > 0) {
	sums->targets = calloc(sums->count, sizeof(rs_target_t));
        if (!sums->targets)
            return RS_MEM_ERROR;

	for (i = 0; i < sums->count; i++) {
	    sums->targets[i].i = i;
	    sums->targets[i].t = gettag(sums->block_sigs[i].weak_sum);
	}

	/* FIXME: Perhaps if this operating system has comparison_fn_t
         * like GNU, then use it in the cast.  But really does anyone
         * care?  */
	qsort(sums->targets, sums->count,
	      sizeof(sums->targets[0]),
              (int (*)(const void *, const void *)) rs_compare_targets);
    }

    for (i = 0; i < TABLESIZE; i++)
	sums->tag_table[i] = NULL_TAG;

    for (i = sums->count - 1; i >= 0; i--) {
	sums->tag_table[sums->targets[i].t] = i;
    }

    rs_trace("done");
    return RS_DONE;
}



/* 
 * See if there is a match for the specified block INBUF..BLOCK_LEN in
 * the checksum set, using precalculated WEAK_SUM.
 *
 * If we don't find a match on the weak checksum, then we just give
 * up.  If we do find a weak match, then we proceed to calculate the
 * strong checksum for the current block, and see if it will match
 * anything.
 */
int
rs_search_for_block(rs_weak_sum_t weak_sum,
                    char const *inbuf, size_t block_len,
                    rs_signature_t const *sig, rs_stats_t * stats,
                    rs_long_t * match_where)
{
    int                     hash_tag = gettag(weak_sum);
    int                     j = sig->tag_table[hash_tag];
    rs_strong_sum_t         strong_sum;
    int                     got_strong = 0;

    if (j == NULL_TAG) {
	return 0;
    }

    for (; j < sig->count && sig->targets[j].t == hash_tag; j++) {
	int                     i = sig->targets[j].i;
	int                     token;

	if (weak_sum != sig->block_sigs[i].weak_sum)
	    continue;

	token = sig->block_sigs[i].i;

	rs_trace("found weak match for %08x in token %d", weak_sum, token);

	if (!got_strong) {
            if(sig->magic == RS_BLAKE2_SIG_MAGIC) {
	        rs_calc_blake2_sum(inbuf, block_len, &strong_sum);
	    } else if (sig->magic == RS_MD4_SIG_MAGIC) {
                rs_calc_md4_sum(inbuf, block_len, &strong_sum);
	    } else {
	        rs_error("Unknown signature algorithm - this is a BUG");
		return 0; /* FIXME: Is this the best way to handle this? */
	    }
	    got_strong = 1;
	}

	/* FIXME: Use correct dynamic sum length! */
	if (memcmp(strong_sum, sig->block_sigs[i].strong_sum,
                   sig->strong_sum_len) == 0) {
	    /* XXX: This is a remnant of rsync: token number 1 is the
	     * block at offset 0.  It would be good to clear this
	     * up. */
	    *match_where = (rs_long_t)(token - 1) * sig->block_len;
	    return 1;
	} else {
	    rs_trace("this was a false positive, the strong sig doesn't match");
	    stats->false_matches++;
	}
    }

    return 0;
}
