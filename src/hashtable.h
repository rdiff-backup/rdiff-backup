/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * hashtable.h -- a generic open addressing hashtable.
 *
 * Copyright (C) 2003 by Donovan Baarda <abo@minkirri.apana.org.au>
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
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA. */
#ifndef _HASHTABLE_H_
#  define _HASHTABLE_H_

#  include <assert.h>
#  include <stdlib.h>

/** \file hashtable.h A generic open addressing hashtable.
 *
 * This is a minimal hashtable containing pointers to arbitrary entries with
 * configurable hashtable size and support for custom hash() and cmp() methods.
 * The cmp() method can either be a simple comparison between two keys, or can
 * be against a special match object containing additional mutable state. This
 * allows for things like deferred and cached evaluation of costly comparison
 * data. The hash() function doesn't need to avoid clustering behaviour.
 *
 * It uses open addressing with quadratic probing for collisions. The
 * MurmurHash3 finalization function is used on the hash() output to avoid
 * clustering. There is no support for removing entries, only adding them.
 * Multiple entries with the same key can be added, and you can use a fancy
 * cmp() function to find particular entries by more than just their key. There
 * is an iterator for iterating through all entries in the hashtable. There are
 * optional hashtable_find() find/match/hashcmp/entrycmp stats counters that
 * can be disabled by defining HASHTABLE_NSTATS.
 *
 * The types and methods of the hashtable and its contents are specified by
 * using \#define parameters set to their basenames (the prefixes for the *_t
 * type and *_func() methods) before doing \#include "hashtable.h". This
 * produces static inline type-safe methods that are either application
 * optimized for speed or wrappers around void* implementation methods for
 * compactness.
 *
 * \param ENTRY - the entry type basename.
 *
 * \param KEY - optional key type basename (default: ENTRY).
 *
 * \param MATCH - optional match type basename (default: KEY).
 *
 * \param NAME - optional hashtable type basename (default: ENTRY_hashtable).
 *
 * Example: \code
 *   typedef ... mykey_t;
 *   int mykey_hash(const mykey_t *e);
 *   int mykey_cmp(mykey_t *e, const mykey_t *o);
 *
 *   typedef struct myentry {
 *     mykey_t key;  // Inherit from mykey_t.
 *     ...extra entry value data...
 *   } myentry_t;
 *   void myentry_init(myentry_t *e, ...);
 *
 *   #define ENTRY myentry
 *   #define KEY mykey
 *   #include "hashtable.h"
 *
 *   hashtable_t *t;
 *   myentry_t entries[300];
 *   mykey_t k;
 *   myentry_t *e;
 *
 *   t = myentry_hashtable_new(300);
 *   myentry_init(&entries[5], ...);
 *   myentry_hashtable_add(t, &entries[5]);
 *   k = ...;
 *   e = myentry_hashtable_find(t, &k);
 *
 *   hashtable_iter_t i;
 *   for (e = myentry_hashtable_iter(&i, t); e != NULL;
 *        e = myentry_hashtable_next(&i))
 *     ...
 *
 *   myentry_hashtable_free(t);
 * \endcode
 *
 * The mykey_hash() and mykey_cmp() fuctions will typically take pointers to
 * mykey/myentry instances the same as the pointers stored in the hashtable.
 * However it is also possible for them to take "match objects" that are a
 * "subclass" of the entry type that contain additional state for complicated
 * comparision operations.
 *
 * Example: \code
 *   typedef struct mymatch {
 *     mykey_t key;  // Inherit from mykey_t;
 *     ...extra match criteria and state data...
 *   } mymatch_t;
 *   int mymatch_cmp(mymatch_t *m, const myentry_t *e);
 *
 *   #define ENTRY myentry
 *   #define KEY mykey
 *   #define MATCH mymatch
 *   #include "hashtable.h"
 *
 *   ...
 *   mymatch_t m;
 *
 *   t = myentry_hashtable_new(300);
 *   ...
 *   m = ...;
 *   e = myentry_hashtable_find(t, &m);
 * \endcode
 *
 * The mymatch_cmp() function is only called for finding hashtable entries and
 * can mutate the mymatch_t object for doing things like deferred and cached
 * evaluation of expensive match data. It can also access the whole myentry_t
 * object to match against more than just the key. */

/** The hashtable type. */
typedef struct hashtable {
    int size;                   /**< Size of allocated hashtable. */
    int count;                  /**< Number of entries in hashtable. */
#  ifndef HASHTABLE_NSTATS
    /* The following are for accumulating hashtable_find() stats. */
    long find_count;            /**< The count of finds tried. */
    long match_count;           /**< The count of matches found. */
    long hashcmp_count;         /**< The count of hash compares done. */
    long entrycmp_count;        /**< The count of entry compares done. */
#  endif
    void **etable;              /**< Table of pointers to entries. */
    unsigned ktable[];          /**< Table of hash keys. */
} hashtable_t;

/** The hashtable iterator type. */
typedef struct hashtable_iter {
    hashtable_t *htable;        /**< The hashtable to iterate over. */
    int index;                  /**< The index to scan from next. */
} hashtable_iter_t;

/* void* implementations for the type-safe static inline wrappers below. */
hashtable_t *_hashtable_new(int size);
void _hashtable_free(hashtable_t *t);
void *_hashtable_iter(hashtable_iter_t *i, hashtable_t *t);
void *_hashtable_next(hashtable_iter_t *i);

/** MurmurHash3 finalization mix function. */
static inline unsigned mix32(unsigned int h)
{
    h ^= h >> 16;
    h *= 0x85ebca6b;
    h ^= h >> 13;
    h *= 0xc2b2ae35;
    h ^= h >> 16;
    return h;
}

#endif                          /* _HASHTABLE_H_ */

/* If ENTRY is defined, define type-dependent static inline methods. */
#ifdef ENTRY

#  define _JOIN2(x, y) x##y
#  define _JOIN(x, y) _JOIN2(x, y)

#  ifndef KEY
#    define KEY ENTRY
#  endif

#  ifndef MATCH
#    define MATCH KEY
#  endif

#  ifndef NAME
#    define NAME _JOIN(ENTRY, _hashtable)
#  endif

#  define ENTRY_T _JOIN(ENTRY, _t)      /**< The entry type. */
#  define KEY_T _JOIN(KEY, _t)  /**< The key type. */
#  define MATCH_T _JOIN(MATCH, _t)      /**< The match type. */
/** The key hash(k) method. */
#  define KEY_HASH(k) _JOIN(KEY, _hash)(k)
/** The match cmp(m, e) method. */
#  define MATCH_CMP(m, e) _JOIN(MATCH, _cmp)(m, e)
#  define _FUNC(f) _JOIN(NAME, f)

/* Loop macro for probing table t for key k, setting hk to the hash for k
   reserving zero for empty buckets, and iterating with index i and entry hash
   h, terminating at an empty bucket. */
#  define _for_probe(t, k, hk, i, h) \
    const unsigned mask = t->size - 1;\
    unsigned hk = KEY_HASH((KEY_T *)k), i, s, h;\
    hk = hk ? hk : -1;\
    for (i = mix32(hk) & mask, s = 0; (h = t->ktable[i]); i = (i + ++s) & mask)

/* Conditional macro for incrementing stats counters. */
#  ifndef HASHTABLE_NSTATS
#    define _stats_inc(c) (c++)
#  else
#    define _stats_inc(c)
#  endif

/** Allocate and initialize a hashtable instance.
 *
 * The provided size is used as an indication of the number of entries you wish
 * to add, but the allocated size will probably be larger depending on the
 * implementation to enable optimisations or avoid degraded performance. It may
 * be possible to fill the table beyond the requested size, but performance can
 * start to degrade badly if it is over filled.
 *
 * \param size - The desired minimum size of the hash table.
 *
 * \return The initialized hashtable instance or NULL if it failed. */
static inline hashtable_t *_FUNC(_new) (int size) {
    return _hashtable_new(size);
}

/** Destroy and free a hashtable instance.
 *
 * This will free the hashtable, but will not free the entries in the
 * hashtable. If you want to free the entries too, use a hashtable iterator to
 * free the the entries first.
 *
 * \param *t - The hashtable to destroy and free. */
static inline void _FUNC(_free) (hashtable_t *t) {
    _hashtable_free(t);
}

/** Initialize hashtable stats counters.
 *
 * This will reset all the stats counters for the hashtable,
 *
 * \param *t - The hashtable to initializ stats for. */
static inline void _FUNC(_stats_init) (hashtable_t *t) {
#  ifndef HASHTABLE_NSTATS
    t->find_count = t->match_count = t->hashcmp_count = t->entrycmp_count = 0;
#  endif
}

/** Add an entry to a hashtable.
 *
 * This doesn't use MATCH_CMP() or do any checks for existing copies or
 * instances, so it will add duplicates. If you want to avoid adding
 * duplicates, use hashtable_find() to check for existing entries first.
 *
 * \param *t - The hashtable to add to.
 *
 * \param *e - The entry object to add.
 *
 * \return The added entry, or NULL if the table is full. */
static inline ENTRY_T *_FUNC(_add) (hashtable_t *t, ENTRY_T * e) {
    assert(e != NULL);
    if (t->count + 1 == t->size)
        return NULL;
    _for_probe(t, e, he, i, h);
    t->count++;
    t->ktable[i] = he;
    return t->etable[i] = e;
}

/** Find an entry in a hashtable.
 *
 * Uses MATCH_CMP() to find the first matching entry in the table in the same
 * hash() bucket.
 *
 * \param *t - The hashtable to search.
 *
 * \param *m - The key or match object to search for.
 *
 * \return The first found entry, or NULL if nothing was found. */
static inline ENTRY_T *_FUNC(_find) (hashtable_t *t, MATCH_T * m) {
    assert(m != NULL);
    ENTRY_T *e;

    _stats_inc(t->find_count);
    _for_probe(t, m, hm, i, he) {
        _stats_inc(t->hashcmp_count);
        if (hm == he) {
            _stats_inc(t->entrycmp_count);
            if (!MATCH_CMP(m, e = t->etable[i])) {
                _stats_inc(t->match_count);
                return e;
            }
        }
    }
    return NULL;
}

/** Initialize a hashtable_iter_t and return the first entry.
 *
 * This works together with hashtable_next() for iterating through all entries
 * in a hashtable.
 *
 * Example: \code
 *   for (e = hashtable_iter(&i, t); e != NULL; e = hashtable_next(&i))
 *     ...
 * \endcode
 *
 * \param *i - the hashtable iterator to initialize.
 *
 * \param *t - the hashtable to iterate over.
 *
 * \return The first entry or NULL if the hashtable is empty. */
static inline ENTRY_T *_FUNC(_iter) (hashtable_iter_t *i, hashtable_t *t) {
    return _hashtable_iter(i, t);
}

/** Get the next entry from a hashtable iterator or NULL when finished.
 *
 * \param *i - the hashtable iterator to use.
 *
 * \return The next entry or NULL if the iterator is finished. */
static inline ENTRY_T *_FUNC(_next) (hashtable_iter_t *i) {
    return _hashtable_next(i);
}

#  undef ENTRY
#  undef KEY
#  undef MATCH
#  undef NAME
#  undef ENTRY_T
#  undef KEY_T
#  undef MATCH_T
#  undef KEY_HASH
#  undef MATCH_CMP
#  undef _FUNC
#endif                          /* ENTRY */
