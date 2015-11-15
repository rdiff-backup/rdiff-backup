/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- the library for network deltas
 * 
 * Copyright (C) 1999, 2000, 2001, 2014 by Martin Pool <mbp@sourcefrog.net>
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

#include "config.h"

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

#define TABLE_SIZE (1<<16)
#define NULL_TAG (-1)

#define gettag2(s1,s2) (((s1) + (s2)) & 0xFFFF)
#define gettag(sum) gettag2((sum)&0xFFFF,(sum)>>16)

static void swap(rs_target_t *t1, rs_target_t *t2) {
    unsigned short ts = t1->t;
    t1->t = t2->t;
    t2->t = ts;

    int ti = t1->i;
    t1->i = t2->i;
    t2->i = ti;
}

static int rs_compare_targets(rs_target_t const *t1, rs_target_t const *t2, rs_signature_t * sums) {
    int v = (int) t1->t - (int) t2->t;
    if (v != 0)
	return v;

    rs_weak_sum_t w1 = sums->block_sigs[t1->i].weak_sum;
    rs_weak_sum_t w2 = sums->block_sigs[t2->i].weak_sum;

    v = (w1 > w2) - (w1 < w2);
    if (v != 0)
	return v;

    return memcmp(sums->block_sigs[t1->i].strong_sum,
	    sums->block_sigs[t2->i].strong_sum,
	    sums->strong_sum_len);
}

static void heap_sort(rs_signature_t * sums) {
    unsigned int i, j, n, k, p;
    for (i = 1; i < sums->count; ++i) {
	for (j = i; j > 0;) {
	    p = (j - 1) >> 1;
	    if (rs_compare_targets(&sums->targets[j], &sums->targets[p], sums) > 0)
		swap(&sums->targets[j], &sums->targets[p]);
	    else
		break;
	    j = p;
	}
    }

    for (n = sums->count - 1; n > 0;) {
	swap(&sums->targets[0], &sums->targets[n]);
	--n;
	for (i = 0; ((i << 1) + 1) <= n;) {
	    k = (i << 1) + 1;
	    if ((k + 1 <= n) && (rs_compare_targets(&sums->targets[k], &sums->targets[k + 1], sums) < 0))
		k = k + 1;
	    if (rs_compare_targets(&sums->targets[k], &sums->targets[i], sums) > 0)
		swap(&sums->targets[k], &sums->targets[i]);
	    else
		break;
	    i = k;
	}
    }
}

rs_result
rs_build_hash_table(rs_signature_t * sums)
{
    int i;

    sums->tag_table = calloc(TABLE_SIZE, sizeof(sums->tag_table[0]));
    if (!sums->tag_table)
        return RS_MEM_ERROR;

    if (sums->count > 0) {
	sums->targets = calloc(sums->count, sizeof(rs_target_t));
        if (!sums->targets) {
	    free(sums->tag_table);
	    sums->tag_table = NULL;
            return RS_MEM_ERROR;
	}

	for (i = 0; i < sums->count; i++) {
	    sums->targets[i].i = i;
	    sums->targets[i].t = gettag(sums->block_sigs[i].weak_sum);
	}

	heap_sort(sums);
    }

    for (i = 0; i < TABLE_SIZE; i++) {
	sums->tag_table[i].l = NULL_TAG;
	sums->tag_table[i].r = NULL_TAG;
    }

    for (i = sums->count - 1; i >= 0; i--) {
	sums->tag_table[sums->targets[i].t].l = i;
    }

    for (i = 0; i < sums->count; i++) {
	sums->tag_table[sums->targets[i].t].r = i;
    }

    rs_trace("rs_build_hash_table done");
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
                    const rs_byte_t *inbuf,
                    size_t block_len,
                    rs_signature_t const *sig, rs_stats_t * stats,
                    rs_long_t * match_where)
{
    /* Caller must have called rs_build_hash_table() by now */
    if (!sig->tag_table)
        rs_fatal("Must have called rs_build_hash_table() by now");

    rs_strong_sum_t strong_sum;
    int got_strong = 0;
    int hash_tag = gettag(weak_sum);
    rs_tag_table_entry_t *bucket = &(sig->tag_table[hash_tag]);
    int l = bucket->l;
    int r = bucket->r + 1;
    int v = 1;

    if (l == NULL_TAG)
	return 0;

    while (l < r) {
	int m = (l + r) >> 1;
	int i = sig->targets[m].i;
	rs_block_sig_t *b = &(sig->block_sigs[i]);
	v = (weak_sum > b->weak_sum) - (weak_sum < b->weak_sum); // v < 0  - weak_sum <  b->weak_sum
								 // v == 0 - weak_sum == b->weak_sum
								 // v > 0  - weak_sum >  b->weak_sum
	if (v == 0) {
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
	    v = memcmp(strong_sum, b->strong_sum, sig->strong_sum_len);

	    if (v == 0) {
		l = m;
		r = m;
		break;
	    }
	}

	if (v > 0)
	    l = m + 1;
	else
	    r = m;
    }

    if (l == r) {
	int i = sig->targets[l].i;
	rs_block_sig_t *b = &(sig->block_sigs[i]);
	if (weak_sum != b->weak_sum)
	    return 0;
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
	v = memcmp(strong_sum, b->strong_sum, sig->strong_sum_len);
	int token = b->i;
	*match_where = (rs_long_t)(token - 1) * sig->block_len;
    }

    return !v;
}
