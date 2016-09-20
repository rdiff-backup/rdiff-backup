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

hashtable_t *hashtable_new(int size, hash_f hash, cmp_f cmp)
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
    t->hash = hash;
    t->cmp = cmp;
#ifndef HASHTABLE_NSTATS
    t->find_count = t->match_count = t->keycmp_count = t->entrycmp_count = 0;
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

/* Get hash key, reserving zero as an empty bucket marker. */
static inline unsigned get_key(const hashtable_t *t, const void *e)
{
    unsigned k = t->hash(e);
    return k ? k : -1;
}

/* Prefix macro for probing table t for entry e with key k and index i. */
#define do_probe(t, e, k) \
    const unsigned k = get_key(t, e);\
    const unsigned mask = t->size - 1;\
    const unsigned index = mix32(k) & mask;\
    unsigned i = index, s = 0;\
    do

/* Suffix macro for do_probe. */
#define while_probe \
    while ((i = (i + ++s) & mask) != index)

void *hashtable_add(hashtable_t *t, void *e)
{
    assert(e != NULL);
    do_probe(t, e, k) {
        if (!t->ktable[i]) {
            t->count++;
            t->ktable[i] = k;
            return t->etable[i] = e;
        }
    } while_probe;
    return NULL;
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
    unsigned ke;

    stats_inc(t->find_count);
    do_probe(t, m, km) {
        if (!(ke = t->ktable[i]))
            return NULL;
        stats_inc(t->keycmp_count);
        if (km == ke) {
            stats_inc(t->entrycmp_count);
            if (!t->cmp(m, e = t->etable[i])) {
                stats_inc(t->match_count);
                return e;
            }
        }
    } while_probe;
    return NULL;
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
