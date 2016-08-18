/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * rollsum_test -- tests for the librsync rolling checksum.
 *
 * Copyright (C) 2003 by Donovan Baarda <abo@minkirri.apana.org.au>
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

#include <stdio.h>
#include <stdint.h>
#include <assert.h>
#include "hashtable.h"

/* Entry type for values in hashtable. */
typedef struct entry {
    int key;
    int value;
} entry_t;

void entry_init(entry_t *e, int i)
{
    e->key = (i / 2) * (i / 2);
    e->value = i;
}

int entry_hash(const entry_t *e)
{
    return e->key;
}

/* Match type for finding matching entries in hashtable. */
typedef struct match {
    entry_t entry;
    int source;
} match_t;

void match_init(match_t *e, int i)
{
    entry_init(&e->entry, i);
    e->entry.value = 0;
    e->source = i;
}

int entry_cmp(const entry_t *e, match_t *o)
{
    int ans = e->key - o->entry.key;
    if (ans == 0) {
        if (o->entry.value != o->source)
            o->entry.value = o->source;
        ans = e->value - o->entry.value;
    }
    return ans;
}

/* Test driver for hashtable. */
int main(int argc, char **argv)
{
    hashtable_t t;
    entry_t entry[256];
    entry_t e;
    match_t m;
    int i;

    entry_init(&e, 0);
    for (i = 0; i < 256; i++)
        entry_init(&entry[i], i);

    /* Test hashtable_init() */
    hashtable_init(&t, 256, (hash_f) & entry_hash, (cmp_f) & entry_cmp);
    assert(t.size == 512);
    assert(t.table != NULL);
    assert(t.hash == (hash_f) & entry_hash);
    assert(t.cmp == (cmp_f) & entry_cmp);

    /* Test hashtable_add() */
    assert(hashtable_add(&t, &e) == &e);        /* added duplicated copy */
    assert(hashtable_add(&t, &entry[0]) == &entry[0]);  /* ignored duplicated instance */
    for (i = 0; i < 256; i++)
        assert(hashtable_add(&t, &entry[i]) == &entry[i]);
    assert((void *) &e == t.table[0]);
    assert((void *) &entry[0] == t.table[1]);
    assert((void *) &entry[1] == t.table[3]);
    assert((void *) &entry[2] == t.table[2]);
    assert((void *) &entry[3] == t.table[4]);

    /* Test hashtable_find() */
    match_init(&m, 0);
    assert(hashtable_find(&t, &m) == &e);       /* finds first duplicate added */
    assert(m.entry.value == m.source);  /* cmp() updated m.entry.value */
    for (i = 1; i < 256; i++) {
        match_init(&m, i);
        assert(hashtable_find(&t, &m) == &entry[i]);
        assert(m.entry.value == m.source);      /* cmp() updated m.entry.value */
    }
    match_init(&m, 256);
    assert(hashtable_find(&t, &m) == NULL);     /* find missing entry */
    assert(m.entry.value == 0); /* cmp() didn't update m.entry.value */

    /* Test hashtable iterators */
    entry_t *p;
    hashtable_iter_t it;
    int count = 0;
    for (p = hashtable_iter(&it, &t); p != NULL; p = hashtable_next(&it)) {
        assert(p == &e || (&entry[0] <= p && p <= &entry[255]));
        count++;
    }
    assert(count == 257);

    return 0;
}
