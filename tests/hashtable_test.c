/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * hashtable_test -- tests for the hashtable.
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

/* Force DEBUG on so that tests can use assert(). */
#undef NDEBUG
#include <stdio.h>
#include <stdint.h>
#include <assert.h>
#include "hashtable.h"

/* Key type for the hashtable. */
typedef int mykey_t;
void mykey_init(mykey_t *k, int i)
{
    /* This is chosen to cause bad key collisions and clustering. */
    *k = (i / 2) * (i / 2);
}

int mykey_hash(const mykey_t *k)
{
    return *k;
}

int mykey_cmp(mykey_t *k, const mykey_t *o)
{
    return *k - *o;
}

/* Entry type for values in hashtable. */
typedef struct myentry {
    mykey_t key;                  /* Inherit from mykey_t. */
    int value;
} myentry_t;

void myentry_init(myentry_t *e, int i)
{
    mykey_init(&e->key, i);
    e->value = i;
}

/* Match type for finding matching entries in hashtable.
 *
 * This demonstrates using deferred calculation and comparison of the
 * expected value only when the key matches. */
typedef struct mymatch {
    mykey_t key;                  /* Inherit from mykey_t. */
    int value;
    int source;
} mymatch_t;

void mymatch_init(mymatch_t *m, int i)
{
    mykey_init(&m->key, i);
    m->value = 0;
    m->source = i;
}

int mymatch_cmp(mymatch_t *m, const myentry_t *e)
{
    int ans = mykey_cmp(&m->key, &e->key);
    /* Calculate and compare value if key matches */
    if (ans == 0) {
        if (m->value != m->source)
            m->value = m->source;
        ans = m->value - e->value;
    }
    return ans;
}


/* Instantiate a simple mykey_hashtable of keys. */
#define ENTRY mykey
#include "hashtable.h"

/* Instantiate a fancy myhashtable of myentrys using a custom match. */
#define ENTRY myentry
#define KEY mykey
#define MATCH mymatch
#define NAME myhashtable
#include "hashtable.h"

/* Test driver for hashtable. */
int main(int argc, char **argv)
{
    /* Test mykey_hashtable instance. */
    hashtable_t *kt;
    hashtable_iter_t ki;
    mykey_t k1, k2;

    mykey_init(&k1, 1);
    mykey_init(&k2, 2);
    assert((kt = mykey_hashtable_new(16)) != NULL);
    assert(mykey_hashtable_add(kt, &k1) == &k1);
    assert(mykey_hashtable_find(kt, &k1) == &k1);
    assert(mykey_hashtable_find(kt, &k2) == NULL);
    assert(mykey_hashtable_iter(&ki, kt) == &k1);
    assert(mykey_hashtable_next(&ki) == NULL);

    /* Test myhashtable instance. */
    hashtable_t *t;
    myentry_t entry[256];
    myentry_t e;
    mymatch_t m;
    int i;

    myentry_init(&e, 0);
    for (i = 0; i < 256; i++)
        myentry_init(&entry[i], i);

    /* Test myhashtable_new() */
    t = myhashtable_new(256);
    assert(t->size == 512);
    assert(t->count == 0);
    assert(t->etable != NULL);
    assert(t->ktable != NULL);

    /* Test myhashtable_add() */
    assert(myhashtable_add(t, &e) == &e); /* Added duplicated copy. */
    assert(myhashtable_add(t, &entry[0]) == &entry[0]);   /* Added duplicated instance. */
    for (i = 0; i < 256; i++)
        assert(myhashtable_add(t, &entry[i]) == &entry[i]);
    assert(t->count == 258);

    /* Test myhashtable_find() */
    mymatch_init(&m, 0);
    assert(myhashtable_find(t, &m) == &e);        /* Finds first duplicate added. */
    assert(m.value == m.source);        /* mymatch_cmp() updated m.value. */
    for (i = 1; i < 256; i++) {
        mymatch_init(&m, i);
        assert(myhashtable_find(t, &m) == &entry[i]);
        assert(m.value == m.source);    /* mymatch_cmp() updated m.value. */
    }
    mymatch_init(&m, 256);
    assert(myhashtable_find(t, &m) == NULL);      /* Find missing myentry. */
    assert(m.value == 0);       /* mymatch_cmp() didn't update m.value. */
#ifndef HASHTABLE_NSTATS
    assert(t->find_count == 257);
    assert(t->match_count == 256);
    assert(t->hashcmp_count >= 256);
    assert(t->entrycmp_count >= 256);
    myhashtable_stats_init(t);
    assert(t->find_count == 0);
    assert(t->match_count == 0);
    assert(t->hashcmp_count == 0);
    assert(t->entrycmp_count == 0);
#endif

    /* Test hashtable iterators */
    myentry_t *p;
    hashtable_iter_t iter;
    int count = 0;
    for (p = myhashtable_iter(&iter, t); p != NULL; p = myhashtable_next(&iter)) {
        assert(p == &e || (&entry[0] <= p && p <= &entry[255]));
        count++;
    }
    assert(count == 258);
    myhashtable_free(t);

    return 0;
}
