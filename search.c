/*=                                     -*- c-file-style: "linux" -*-
 * rproxy -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 1999, 2000 by Martin Pool <mbp@samba.org>
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

#include "includes.h"
#include "search.h"
#include "sum_p.h"

#define TABLESIZE (1<<16)
#define NULL_TAG (-1)


#define gettag2(s1,s2) (((s1) + (s2)) & 0xFFFF)
#define gettag(sum) gettag2((sum)&0xFFFF,(sum)>>16)

static int
hs_compare_targets(struct target const *t1, struct target const *t2)
{
    return ((int) t1->t - (int) t2->t);
}


int
hs_build_hash_table(hs_sumset_t * sums)
{
    int                     i;

    sums->tag_table = calloc(TABLESIZE, sizeof sums->tag_table[0]);
    if (sums->count > 0) {
	sums->targets = calloc(sums->count, sizeof(struct target));

	for (i = 0; i < sums->count; i++) {
	    sums->targets[i].i = i;
	    sums->targets[i].t = gettag(sums->block_sums[i].weak_sum);
	}

	/* FIXME: Perhaps if this operating system has comparison_fn_t
         * like GNU, then use it in the cast.  But really does anyone
         * care?  */
	qsort(sums->targets, sums->count,
	      sizeof(sums->targets[0]),
              (int (*)(const void *, const void *)) hs_compare_targets);
    }

    for (i = 0; i < TABLESIZE; i++)
	sums->tag_table[i] = NULL_TAG;

    for (i = sums->count - 1; i >= 0; i--) {
	sums->tag_table[sums->targets[i].t] = i;
    }

    return 0;
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
hs_search_for_block(hs_weak_sum_t weak_sum,
		     byte_t const *inbuf, size_t block_len,
		     hs_sumset_t const *sums, hs_stats_t * stats,
		     off_t * match_where)
{
    int                     hash_tag = gettag(weak_sum);
    int                     j = sums->tag_table[hash_tag];
    byte_t                  strong_sum[DEFAULT_SUM_LENGTH];
    int                     got_strong = 0;

    if (j == NULL_TAG) {
	return 0;
    }

    for (; j < sums->count && sums->targets[j].t == hash_tag; j++) {
	int                     i = sums->targets[j].i;
	int                     token;

	if (weak_sum != sums->block_sums[i].weak_sum)
	    continue;

	/* also make sure the two blocks are the same length */
	/* l = MIN(s->n,len-offset); */
	/* if (l != s->block_sums[i].len) continue;                    */

	/* if (!done_csum2) { */
	/* map = (schar *)map_ptr(buf,offset,l); */
	/* get_checksum2((char *)map,l,sum2); */
	/* done_csum2 = 1; */
	/* } */

	token = sums->block_sums[i].i;

	hs_trace("found weak match for %08x in token %d", weak_sum, token);

	if (!got_strong) {
	    hs_calc_strong_sum(inbuf, block_len, strong_sum,
				DEFAULT_SUM_LENGTH);
	    got_strong = 1;
	}

	/* FIXME: Use correct dynamic sum length! */
	if (memcmp(strong_sum, sums->block_sums[i].strong_sum,
		   DEFAULT_SUM_LENGTH) == 0) {
	    /* XXX: This is a remnant of rsync: token number 1 is the * block 
	     * at offset 0.  It would be good to clear this * up. */
	    *match_where = (token - 1) * sums->block_len;
	    return 1;
	} else {
	    hs_trace("this was a false positive, the strong sums "
		      "don't match");
	    stats->false_matches++;
	}
    }

    return 0;
}
