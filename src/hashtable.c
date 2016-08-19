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

void hashtable_init(hashtable_t *t, int size, hash_f hash, cmp_f cmp)
{
    assert(t != NULL);
    /* Increase size by 25% and use next power of 2 larger than 8. */
    size += size / 4;
    t->size = 8;
    while (t->size < size)
        t->size <<= 1;
    t->table = calloc(t->size, sizeof(void *));
    t->hash = hash;
    t->cmp = cmp;
}

void hashtable_done(hashtable_t *t)
{
    assert(t != NULL);
    free(t->table);
#ifndef NDEBUG
    t->size = 0;
    t->hash = NULL;
    t->cmp = NULL;
#endif                          /* NDEBUG */
}

/* Compare function that only compares pointers. */
int pointer_cmp(void *k, const void *o)
{
    return k - o;
}

/* Find the index of the first matching or free entry. */
int hashtable_index(hashtable_t *t, cmp_f cmp, void *k)
{
    assert(k != NULL);
    int mask = t->size - 1;
    int index = t->hash(k) % mask;
    int i = index, s = 1;

    do {
        if (!t->table[i] || !cmp(k, t->table[i])) {
            return i;
        }
        i = (i + s++) & mask;
    } while (i != index);
    return -1;
}

void *hashtable_add(hashtable_t *t, void *e)
{
    assert(e != NULL);
    int i = hashtable_index(t, &pointer_cmp, e);

    if (i == -1)
        return NULL;
    t->table[i] = e;
    return e;
}

void *hashtable_find(hashtable_t *t, void *k)
{
    assert(k != NULL);
    int i = hashtable_index(t, t->cmp, k);

    if (i == -1)
        return NULL;
    return t->table[i];
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
