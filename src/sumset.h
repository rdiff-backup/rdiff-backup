/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- the library for network deltas
 *
 * Copyright (C) 1999, 2000, 2001 by Martin Pool <mbp@sourcefrog.net>
 * Copyright (C) 1999 by Andrew Tridgell <tridge@samba.org>
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

#include <assert.h>
#include "hashtable.h"
#include "checksum.h"

/** Signature of a single block. */
typedef struct rs_block_sig {
    rs_weak_sum_t weak_sum;     /**< Block's weak checksum. */
    rs_strong_sum_t strong_sum; /**< Block's strong checksum. */
} rs_block_sig_t;

/** Signature of a whole file.
 *
 * This includes the all the block sums generated for a file and datastructures
 * for fast matching against them. */
struct rs_signature {
    int magic;                  /**< The signature magic value. */
    int block_len;              /**< The block length. */
    int strong_sum_len;         /**< The block strong sum length. */
    int count;                  /**< Total number of blocks. */
    int size;                   /**< Total number of blocks allocated. */
    void *block_sigs;           /**< The packed block_sigs for all blocks. */
    hashtable_t *hashtable;     /**< The hashtable for finding matches. */
    /* The is extra stats not included in the hashtable stats. */
#ifndef HASHTABLE_NSTATS
    long calc_strong_count;     /**< The count of strongsum calcs done. */
#endif
};

/** Initialize an rs_signature instance.
 *
 * \param *sig the signature to initialize.
 *
 * \param magic the signature magic value. Must be set to a valid magic value.
 *
 * \param block_len the block size to use. Must be > 0.
 *
 * \param strong_len the strongsum size to use. Must be <= the max strongsum
 * size for the strongsum type indicated by the magic value. Use 0 to use the
 * recommended size for the provided magic value.
 *
 * \param sig_fsize signature file size to preallocate required storage for.
 * Use 0 if size is unknown. */
rs_result rs_signature_init(rs_signature_t *sig, int magic, int block_len,
                            int strong_len, rs_long_t sig_fsize);

/** Destroy an rs_signature instance. */
void rs_signature_done(rs_signature_t *sig);

/** Add a block to an rs_signature instance. */
rs_block_sig_t *rs_signature_add_block(rs_signature_t *sig,
                                       rs_weak_sum_t weak_sum,
                                       rs_strong_sum_t *strong_sum);

/** Find a matching block offset in a signature. */
rs_long_t rs_signature_find_match(rs_signature_t *sig, rs_weak_sum_t weak_sum,
                                  void const *buf, size_t len);

/** Log the rs_signature_find_match() stats. */
void rs_signature_log_stats(rs_signature_t const *sig);

/** Assert that a signature is valid.
 *
 * We don't use a static inline function here so that assert failure output
 * points at where rs_signature_check() was called from. */
#define rs_signature_check(sig) do {\
    assert(((sig)->magic == RS_BLAKE2_SIG_MAGIC && (sig)->strong_sum_len <= RS_BLAKE2_SUM_LENGTH)\
           || ((sig)->magic == RS_MD4_SIG_MAGIC && (sig)->strong_sum_len <= RS_MD4_SUM_LENGTH));\
    assert(0 < (sig)->block_len);\
    assert(0 < (sig)->strong_sum_len && (sig)->strong_sum_len <= RS_MAX_STRONG_SUM_LENGTH);\
    assert(0 <= (sig)->count && (sig)->count <= (sig)->size);\
    assert(!(sig)->hashtable || (sig)->hashtable->count <= (sig)->count);\
} while (0)

/** Calculate the strong sum of a buffer. */
static inline void rs_signature_calc_strong_sum(rs_signature_t const *sig,
                                                void const *buf, size_t len,
                                                rs_strong_sum_t *sum)
{
    if (sig->magic == RS_BLAKE2_SIG_MAGIC) {
        rs_calc_blake2_sum(buf, len, sum);
    } else {
        rs_calc_md4_sum(buf, len, sum);
    }
}
