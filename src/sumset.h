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

/** Description of the match described by a signature. */
typedef struct rs_target {
    unsigned short t;
    int i;
} rs_target_t;

/** Hashtable entry pointing at a range of rs_targets. */
typedef struct rs_tag_table_entry {
    /* All tags between l and r inclusively are the same. */
    int l;                      /**> Left bound of the hash tag in sorted array of targets. */
    int r;                      /**> right bound of the hash tag in sorted array of targets. */
} rs_tag_table_entry_t;

/** Signature of a single block. */
typedef struct rs_block_sig {
    int i;                      /**> Index of this block. */
    rs_weak_sum_t weak_sum;     /**> Block's weak checksum. */
    rs_strong_sum_t strong_sum; /**> Block's strong checksum.  */
} rs_block_sig_t;

void rs_block_sig_init(rs_block_sig_t *sig, int i, rs_weak_sum_t weak_sum, rs_strong_sum_t *strong_sum,
                       int strong_len);

/** Signature of a whole file.
 *
 * This includes the all the block sums generated for a file and
 * datastructures for fast matching against them.
 */
struct rs_signature {
    int magic;                  /**> The signature magic value. */
    int block_len;              /**> The block length. */
    int strong_sum_len;         /**> The block strong sum length. */
    int count;                  /**> Total number of blocks. */
    int size;                   /**> Total number of blocks allocated. */
    rs_block_sig_t *block_sigs; /**> The block signatures for all blocks. */
    rs_tag_table_entry_t *tag_table;
    rs_target_t *targets;
};

/** Initialize an rs_signature instance. */
rs_result rs_signature_init(rs_signature_t *sig, int magic, int block_len, int strong_len, int block_num);

/** Destroy an rs_signature instance. */
void rs_signature_done(rs_signature_t *sig);

/** Add a block to an rs_signature instance. */
rs_block_sig_t *rs_signature_add_block(rs_signature_t *sig, rs_weak_sum_t weak_sum, rs_strong_sum_t *strong_sum);
