/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * hashtable.c -- a generic hashtable implementation.
 *
 * Copyright (C) 2016 by Donovan Baarda <abo@minkirri.apana.org.au>
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
#include <assert.h>

/* If ENTRY is not defined, define non-type-dependent methods. */
#ifndef ENTRY
#include <stdlib.h>
#include <stdio.h>
#include "hashtable.h"

/* Open addressing works best if it can take advantage of memory caches using
 * locality for probes of adjacent buckets on collisions. So we pack the keys
 * tightly together in their own key table and avoid referencing the element
 * table and elements as much as possible. Key value zero is reserved as a
 * marker for an empty bucket to avoid checking for NULL in the element table.
 * If we do get a hash value of zero, we -1 to wrap it around to 0xffff. */

/* Use max 0.8 load factor to avoid bad open addressing performance. */
#define HASHTABLE_LOADFACTOR_NUM 8
#define HASHTABLE_LOADFACTOR_DEN 10

hashtable_t *hashtable_new(int size)
{
    hashtable_t *t;
    int size2;

    /* Adjust requested size to account for max load factor. */
    size = 1 + size * HASHTABLE_LOADFACTOR_DEN / HASHTABLE_LOADFACTOR_NUM;
    /* Use next power of 2 larger than the requested size. */
    for (size2 = 1; size2 < size; size2 <<= 1) ;
    if (!(t = calloc(1, sizeof(hashtable_t)+ size2 * sizeof(unsigned))))
        return NULL;
    if (!(t->etable = calloc(size2, sizeof(void *)))) {
        free(t);
        return NULL;
    }
    t->size = size2;
    t->count = 0;
#ifndef HASHTABLE_NSTATS
    t->find_count = t->match_count = t->hashcmp_count = t->entrycmp_count = 0;
#endif
    return t;
}

void hashtable_free(hashtable_t *t)
{
    if (t) {
        free(t->etable);
        free(t);
    }
}

void *hashtable_iter(hashtable_iter_t *i, hashtable_t *t)
{
    assert(i != NULL);
    assert(t != NULL);
    i->htable = t;
    i->index = 0;
    return hashtable_next(i);
}

void *hashtable_next(hashtable_iter_t *i)
{
    assert(i->htable != NULL);
    assert(i->index <= i->htable->size);
    const hashtable_t *t = i->htable;
    void *e;

    while (i->index < t->size) {
        if ((e = t->etable[i->index++]))
            return e;
    }
    return NULL;
}

/* If ENTRY is defined, define type-dependent methods. */
#else /* ENTRY */

#define JOIN2(x, y) x##y
#define JOIN(x, y) JOIN2(x, y)

#ifndef KEY
#define KEY ENTRY
#endif

#ifndef MATCH
#define MATCH KEY
#endif

#define KEY_HASH JOIN(KEY, _hash)
#define MATCH_CMP JOIN(MATCH, _cmp)

/* MurmurHash3 finalization mix function. */
static inline unsigned mix32(unsigned int h)
{
    h ^= h >> 16;
    h *= 0x85ebca6b;
    h ^= h >> 13;
    h *= 0xc2b2ae35;
    h ^= h >> 16;
    return h;
}

/* Loop macro for probing table t for key k, setting hk to the hash for k
 reserving zero for empty buckets, and iterating with index i and entry hash h,
 terminating at an empty bucket. */
#define for_probe(t, k, hk, i, h) \
    const unsigned mask = t->size - 1;\
    unsigned hk = KEY_HASH(k), i, s, h;\
    hk = hk ? hk : -1;\
    for (i = mix32(hk) & mask, s = 0; (h = t->ktable[i]); i = (i + ++s) & mask)

void *hashtable_add(hashtable_t *t, void *e)
{
    assert(e != NULL);
    if (t->count + 1 == t->size)
	return NULL;
    for_probe(t, e, he, i, h);
    t->count++;
    t->ktable[i] = he;
    return t->etable[i] = e;
}

/* Conditional macro for incrementing stats counters. */
#ifndef HASHTABLE_NSTATS
#define stats_inc(c) (c++)
#else
#define stats_inc(c)
#endif

void *hashtable_find(hashtable_t *t, void *m)
{
    assert(m != NULL);
    void *e;

    stats_inc(t->find_count);
    for_probe(t, m, hm, i, he) {
        stats_inc(t->hashcmp_count);
        if (hm == he) {
            stats_inc(t->entrycmp_count);
            if (!MATCH_CMP(m, e = t->etable[i])) {
                stats_inc(t->match_count);
                return e;
            }
        }
    }
    return NULL;
}

#undef ENTRY
#undef KEY
#undef MATCH
#undef KEY_HASH
#undef MATCH_CMP
#endif /* ENTRY */
