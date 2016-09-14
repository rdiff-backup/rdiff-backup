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

#include "config.h"
#include <string.h>
#include <assert.h>
#include "librsync.h"
#include "sumset.h"

/* Test driver for sumset.c. */
int main(int argc, char **argv)
{
    rs_signature_t sig;
    rs_result res;
    rs_weak_sum_t weak = 0x12345678;
    rs_strong_sum_t strong = "ABCDEF";
    int i;
    unsigned char buf[256];

    /* Initialize test buffer. */
    for (i = 0; i < 256; i++)
        buf[i] = i;

    /* Test rs_signature_init() */
    /* Default zero magic. */
    res = rs_signature_init(&sig, 0, 16, 6, 0);
    assert(res == RS_DONE);
    assert(sig.magic == RS_BLAKE2_SIG_MAGIC);
    assert(sig.block_len == 16);
    assert(sig.strong_sum_len == 6);
    assert(sig.count == 0);
    assert(sig.size == 0);
    assert(sig.block_sigs == NULL);
    assert(sig.hashtable == NULL);
    assert(sig.find_count == 0);
    assert(sig.match_count == 0);
    assert(sig.cmp_weak_count == 0);
    assert(sig.cmp_strong_count == 0);
    assert(sig.calc_strong_count == 0);

    /* Blake2 magic. */
    res = rs_signature_init(&sig, RS_BLAKE2_SIG_MAGIC, 16, 6, 0);
    assert(res == RS_DONE);
    assert(sig.magic == RS_BLAKE2_SIG_MAGIC);

    /* MD4 magic. */
    res = rs_signature_init(&sig, RS_MD4_SIG_MAGIC, 16, 6, 0);
    assert(res == RS_DONE);
    assert(sig.magic == RS_MD4_SIG_MAGIC);

    /* Bad magic. */
    res = rs_signature_init(&sig, 1, 16, 6, 0);
    assert(res == RS_BAD_MAGIC);

    /* Bad strong_sum_len. */
    res = rs_signature_init(&sig, RS_MD4_SIG_MAGIC, 16, 17, 0);
    assert(res == RS_PARAM_ERROR);

    /* With sig_fsize provided. */
    res = rs_signature_init(&sig, 0, 16, 6, 92);
    assert(res == RS_DONE);
    assert(sig.magic == RS_BLAKE2_SIG_MAGIC);
    assert(sig.block_len == 16);
    assert(sig.strong_sum_len == 6);
    assert(sig.count == 0);
    assert(sig.size == 8);
    assert(sig.block_sigs != NULL);

    /* Test rs_signature_done(). */
    rs_signature_done(&sig);
    assert(sig.size == 0);
    assert(sig.block_sigs == NULL);

    /* Test rs_signature_calc_strong_sum(). */
    res = rs_signature_init(&sig, RS_MD4_SIG_MAGIC, 16, 6, 0);
    rs_signature_calc_strong_sum(&sig, &buf, 256, &strong);
    assert(memcmp(&strong, "\x29\x8a\x05\xbc\x50\x6e", 6) == 0);

    res = rs_signature_init(&sig, RS_BLAKE2_SIG_MAGIC, 16, 6, 0);
    rs_signature_calc_strong_sum(&sig, &buf, 256, &strong);
    assert(memcmp(&strong, "\x39\xa7\xeb\x9f\xed\xc1", 6) == 0);

    /* Test rs_signature_add_block(). */
    res = rs_signature_init(&sig, 0, 16, 6, 0);
    rs_signature_add_block(&sig, weak, &strong);
    assert(sig.count == 1);
    assert(sig.size == 16);
    assert(sig.block_sigs != NULL);
    assert(sig.block_sigs[0].weak_sum == 0x12345678);
    assert(memcmp(sig.block_sigs[0].strong_sum, &strong, 6) == 0);
    rs_signature_done(&sig);

    /* Prepare rs_build_hash_table() and rs_signature_find_match() tests. */
    res = rs_signature_init(&sig, 0, 16, 6, 0);
    for (i = 0; i < 256; i+=16) {
        weak = rs_calc_weak_sum(&buf[i], 16);
	rs_signature_calc_strong_sum(&sig, &buf[i], 16, &strong);
	rs_signature_add_block(&sig, weak, &strong);
    }

    /* Test rs_build_hash_table(). */
    rs_build_hash_table(&sig);
    assert(sig.hashtable->count == 16);

    /* Test rs_signature_find_match(). */
    /* different weak, different block. */
    assert(rs_signature_find_match(&sig, 0x12345678, &buf[2], 16) == -1);
    /* Matching weak, different block. */
    assert(rs_signature_find_match(&sig, weak, &buf[2], 16) == -1);
    /* Matching weak, matching block. */
    assert(rs_signature_find_match(&sig, weak, &buf[15*16], 16) == 15*16);
    assert(sig.find_count == 3);
    assert(sig.match_count == 1);
    assert(sig.cmp_weak_count >= 2);
    assert(sig.cmp_strong_count == 2);
    assert(sig.calc_strong_count == 2);
    rs_signature_done(&sig);

    return 0;
}
