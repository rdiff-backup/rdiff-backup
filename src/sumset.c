/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- library for network deltas
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

#include "config.h"

#include <assert.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#include "librsync.h"
#include "sumset.h"
#include "util.h"
#include "trace.h"

const int RS_MD4_SUM_LENGTH = 16;
const int RS_BLAKE2_SUM_LENGTH = 32;

static void rs_block_sig_init(rs_block_sig_t *sig, rs_weak_sum_t weak_sum,
                              rs_strong_sum_t *strong_sum, int strong_len)
{
    sig->weak_sum = weak_sum;
    if (strong_sum)
        memcpy(sig->strong_sum, strong_sum, strong_len);
}

static inline unsigned rs_block_sig_hash(const rs_block_sig_t *sig)
{
    return (unsigned)sig->weak_sum;
}

typedef struct rs_block_match {
    rs_block_sig_t block_sig;
    rs_signature_t *signature;
    const void *buf;
    size_t len;
} rs_block_match_t;

static void rs_block_match_init(rs_block_match_t *match, rs_signature_t *sig,
                                rs_weak_sum_t weak_sum,
                                rs_strong_sum_t *strong_sum, const void *buf,
                                size_t len)
{
    rs_block_sig_init(&match->block_sig, weak_sum, strong_sum,
                      sig->strong_sum_len);
    match->signature = sig;
    match->buf = buf;
    match->len = len;
}

static inline int rs_block_match_cmp(rs_block_match_t *match,
                                     const rs_block_sig_t *block_sig)
{
    /* If buf is not NULL, the strong sum is yet to be calculated. */
    if (match->buf) {
#ifndef HASHTABLE_NSTATS
        match->signature->calc_strong_count++;
#endif
        rs_signature_calc_strong_sum(match->signature, match->buf, match->len,
                                     &(match->block_sig.strong_sum));
        match->buf = NULL;
    }
    return memcmp(&match->block_sig.strong_sum, &block_sig->strong_sum,
                  match->signature->strong_sum_len);
}

/* Instantiate hashtable for rs_block_sig and rs_block_match. */
#define ENTRY rs_block_sig
#define MATCH rs_block_match
#define NAME hashtable
#include "hashtable.h"

/* Get the size of a packed rs_block_sig_t. */
static inline size_t rs_block_sig_size(const rs_signature_t *sig)
{
    /* Round up to next multiple of sizeof(weak_sum) to align memory correctly.
     */
    return offsetof(rs_block_sig_t,
                    strong_sum) + ((sig->strong_sum_len +
                                    sizeof(rs_weak_sum_t)-
                                    1) / sizeof(rs_weak_sum_t)) *
        sizeof(rs_weak_sum_t);
}

/* Get the pointer to the block_sig_t from a block index. */
static inline rs_block_sig_t *rs_block_sig_ptr(const rs_signature_t *sig,
                                               int block_idx)
{
    return (rs_block_sig_t *)((char *)sig->block_sigs +
                               block_idx * rs_block_sig_size(sig));
}

/* Get the index of a block from a block_sig_t pointer. */
static inline int rs_block_sig_idx(const rs_signature_t *sig,
                                   rs_block_sig_t *block_sig)
{
    return ((char *)block_sig -
            (char *)sig->block_sigs) / rs_block_sig_size(sig);
}

rs_result rs_signature_init(rs_signature_t *sig, int magic, int block_len,
                            int strong_len, rs_long_t sig_fsize)
{
    int max_strong_len;

    /* Check and set default arguments. */
    magic = magic ? magic : RS_BLAKE2_SIG_MAGIC;
    switch (magic) {
    case RS_BLAKE2_SIG_MAGIC:
        max_strong_len = RS_BLAKE2_SUM_LENGTH;
        break;
    case RS_MD4_SIG_MAGIC:
        max_strong_len = RS_MD4_SUM_LENGTH;
        break;
    default:
        rs_error("invalid magic %#x", magic);
        return RS_BAD_MAGIC;
    }
    strong_len = strong_len ? strong_len : max_strong_len;
    if (strong_len < 1 || max_strong_len < strong_len) {
        rs_error("invalid strong_sum_len %d for magic %#x", strong_len, magic);
        return RS_PARAM_ERROR;
    }
    /* Set attributes from args. */
    sig->magic = magic;
    sig->block_len = block_len;
    sig->strong_sum_len = strong_len;
    sig->count = 0;
    /* Calculate the number of blocks if we have the signature file size. */
    /* Magic+header is 12 bytes, each block thereafter is 4 bytes
       weak_sum+strong_sum_len bytes */
    sig->size = (int)(sig_fsize ? (sig_fsize - 12) / (4 + strong_len) : 0);
    if (sig->size)
        sig->block_sigs =
            rs_alloc(sig->size * rs_block_sig_size(sig),
                     "signature->block_sigs");
    else
        sig->block_sigs = NULL;
    sig->hashtable = NULL;
#ifndef HASHTABLE_NSTATS
    sig->calc_strong_count = 0;
#endif
    rs_signature_check(sig);
    return RS_DONE;
}

void rs_signature_done(rs_signature_t *sig)
{
    hashtable_free(sig->hashtable);
    rs_bzero(sig, sizeof(*sig));
}

rs_block_sig_t *rs_signature_add_block(rs_signature_t *sig,
                                       rs_weak_sum_t weak_sum,
                                       rs_strong_sum_t *strong_sum)
{
    rs_signature_check(sig);
    /* If block_sigs is full, allocate more space. */
    if (sig->count == sig->size) {
        sig->size = sig->size ? sig->size * 2 : 16;
        sig->block_sigs =
            rs_realloc(sig->block_sigs, sig->size * rs_block_sig_size(sig),
                       "signature->block_sigs");
    }
    rs_block_sig_t *b = rs_block_sig_ptr(sig, sig->count++);
    rs_block_sig_init(b, weak_sum, strong_sum, sig->strong_sum_len);
    return b;
}

rs_long_t rs_signature_find_match(rs_signature_t *sig, rs_weak_sum_t weak_sum,
                                  void const *buf, size_t len)
{
    rs_block_match_t m;
    rs_block_sig_t *b;

    rs_signature_check(sig);
    rs_block_match_init(&m, sig, weak_sum, NULL, buf, len);
    if ((b = hashtable_find(sig->hashtable, &m))) {
        return (rs_long_t)rs_block_sig_idx(sig, b) * sig->block_len;
    }
    return -1;
}

void rs_signature_log_stats(rs_signature_t const *sig)
{
#ifndef HASHTABLE_NSTATS
    hashtable_t *t = sig->hashtable;

    rs_log(RS_LOG_INFO | RS_LOG_NONAME,
           "match statistics: signature[%ld searches, %ld (%.3f%%) matches, "
           "%ld (%.3fx) weak sum compares, %ld (%.3f%%) strong sum compares, "
           "%ld (%.3f%%) strong sum calcs]", t->find_count, t->match_count,
           100.0 * (double)t->match_count / t->find_count, t->hashcmp_count,
           (double)t->hashcmp_count / t->find_count, t->entrycmp_count,
           100.0 * (double)t->entrycmp_count / t->find_count,
           sig->calc_strong_count,
           100.0 * (double)sig->calc_strong_count / t->find_count);
#endif
}

rs_result rs_build_hash_table(rs_signature_t *sig)
{
    rs_block_match_t m;
    rs_block_sig_t *b;
    int i;

    rs_signature_check(sig);
    sig->hashtable = hashtable_new(sig->count);
    if (!sig->hashtable)
        return RS_MEM_ERROR;
    for (i = 0; i < sig->count; i++) {
        b = rs_block_sig_ptr(sig, i);
        rs_block_match_init(&m, sig, b->weak_sum, &b->strong_sum, NULL, 0);
        if (!hashtable_find(sig->hashtable, &m))
            hashtable_add(sig->hashtable, b);
    }
    hashtable_stats_init(sig->hashtable);
    return RS_DONE;
}

void rs_free_sumset(rs_signature_t *psums)
{
    rs_signature_done(psums);
    free(psums);
}

void rs_sumset_dump(rs_signature_t const *sums)
{
    int i;
    rs_block_sig_t *b;
    char strong_hex[RS_MAX_STRONG_SUM_LENGTH * 3];

    rs_log(RS_LOG_INFO | RS_LOG_NONAME,
           "sumset info: magic=%#x, block_len=%d, block_num=%d", sums->magic,
           sums->block_len, sums->count);

    for (i = 0; i < sums->count; i++) {
        b = rs_block_sig_ptr(sums, i);
        rs_hexify(strong_hex, b->strong_sum, sums->strong_sum_len);
        rs_log(RS_LOG_INFO | RS_LOG_NONAME,
               "sum %6d: weak=" FMT_WEAKSUM ", strong=%s", i, b->weak_sum,
               strong_hex);
    }
}
