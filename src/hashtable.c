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

hashtable_t *hashtable_new(int size, hash_f hash, cmp_f cmp)
{
    hashtable_t *t;
    int size2;

    /* Use next power of 2 larger than 2x the requested size. */
    for (size2 = 1; size2 < 2 * size; size2 <<= 1) ;
    if (!(t = calloc(1, sizeof(hashtable_t)+ size2 * sizeof(void *))))
        return NULL;
    t->size = size2;
    t->count = 0;
    t->hash = hash;
    t->cmp = cmp;
    return t;
}

void hashtable_free(hashtable_t *t)
{
    free(t);
}

static inline unsigned mix32(unsigned int h)
{
    /* MurmurHash3 finalization mix function. */
    h ^= h >> 16;
    h *= 0x85ebca6b;
    h ^= h >> 13;
    h *= 0xc2b2ae35;
    h ^= h >> 16;
    return h;
}

/* Prefix macro for probing table t for key k with index i. */
#define do_probe(t, k) \
    unsigned mask = t->size - 1;\
    unsigned index = mix32(t->hash(k)) & mask;\
    unsigned i = index, s = 0;\
    do

/* Suffix macro for do_probe. */
#define while_probe \
    while ((i = (i + ++s) & mask) != index)

void *hashtable_add(hashtable_t *t, void *e)
{
    assert(e != NULL);
    do_probe(t, e) {
        if (!t->table[i]) {
            t->count++;
            return t->table[i] = e;
        }
    } while_probe;
    return NULL;
}

void *hashtable_find(hashtable_t *t, void *k)
{
    assert(k != NULL);
    void *e;

    do_probe(t, k) {
        if (!(e = t->table[i]) || !t->cmp(k, e))
            return e;
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
    hashtable_t *t = i->htable;

    while (i->index < t->size) {
        if (t->table[i->index])
            return t->table[i->index++];
        i->index++;
    }
    return NULL;
}
