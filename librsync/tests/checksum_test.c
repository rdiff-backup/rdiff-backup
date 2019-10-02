/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * checksum_test -- tests for the checksum wrappers.
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
#include <string.h>
#include "checksum.h"

/* Test driver for rollsum. */
int main(int argc, char **argv)
{
    weaksum_t r;
    unsigned char buf[256];

    /* Initialize buf for use by tests. */
    for (int i = 0; i < 256; i++)
        buf[i] = i;

    /* RS_ROLLSUM weaksum tests. */

    /* Test weaksum_init(). */
    weaksum_init(&r, RS_ROLLSUM);
    assert(r.kind == RS_ROLLSUM);
    assert(weaksum_count(&r) == 0);
    assert(weaksum_digest(&r) == mix32(0x00000000));

    /* Test weaksum_rollin() */
    weaksum_rollin(&r, 0);      /* [0] */
    assert(weaksum_count(&r) == 1);
    assert(weaksum_digest(&r) == mix32(0x001f001f));
    weaksum_rollin(&r, 1);
    weaksum_rollin(&r, 2);
    weaksum_rollin(&r, 3);      /* [0,1,2,3] */
    assert(weaksum_count(&r) == 4);
    assert(weaksum_digest(&r) == mix32(0x01400082));

    /* Test weaksum_rotate() */
    weaksum_rotate(&r, 0, 4);   /* [1,2,3,4] */
    assert(weaksum_count(&r) == 4);
    assert(weaksum_digest(&r) == mix32(0x014a0086));
    weaksum_rotate(&r, 1, 5);
    weaksum_rotate(&r, 2, 6);
    weaksum_rotate(&r, 3, 7);   /* [4,5,6,7] */
    assert(weaksum_count(&r) == 4);
    assert(weaksum_digest(&r) == mix32(0x01680092));

    /* Test weaksum_rollout() */
    weaksum_rollout(&r, 4);     /* [5,6,7] */
    assert(weaksum_count(&r) == 3);
    assert(weaksum_digest(&r) == mix32(0x00dc006f));
    weaksum_rollout(&r, 5);
    weaksum_rollout(&r, 6);
    weaksum_rollout(&r, 7);     /* [] */
    assert(weaksum_count(&r) == 0);
    assert(weaksum_digest(&r) == mix32(0x00000000));

    /* Test weaksum_update() */
    weaksum_update(&r, buf, 256);
    assert(weaksum_digest(&r) == mix32(0x3a009e80));

    /* Test weaksum_reset() */
    weaksum_reset(&r);
    assert(r.kind == RS_ROLLSUM);
    assert(weaksum_count(&r) == 0);
    assert(weaksum_digest(&r) == mix32(0x00000000));

    /* RS_RABINKARP weaksum tests. */

    /* Test weaksum_init(). */
    weaksum_init(&r, RS_RABINKARP);
    assert(r.kind == RS_RABINKARP);
    assert(weaksum_count(&r) == 0);
    assert(weaksum_digest(&r) == 0x00000001);

    /* Test weaksum_rollin() */
    weaksum_rollin(&r, 0);      /* [0] */
    assert(weaksum_count(&r) == 1);
    assert(weaksum_digest(&r) == 0x08104225);
    weaksum_rollin(&r, 1);
    weaksum_rollin(&r, 2);
    weaksum_rollin(&r, 3);      /* [0,1,2,3] */
    assert(weaksum_count(&r) == 4);
    assert(weaksum_digest(&r) == 0xaf981e97);

    /* Test weaksum_rotate() */
    weaksum_rotate(&r, 0, 4);   /* [1,2,3,4] */
    assert(weaksum_count(&r) == 4);
    assert(weaksum_digest(&r) == 0xe2ef15f3);
    weaksum_rotate(&r, 1, 5);
    weaksum_rotate(&r, 2, 6);
    weaksum_rotate(&r, 3, 7);   /* [4,5,6,7] */
    assert(weaksum_count(&r) == 4);
    assert(weaksum_digest(&r) == 0x7cf3fc07);

    /* Test weaksum_rollout() */
    weaksum_rollout(&r, 4);     /* [5,6,7] */
    assert(weaksum_count(&r) == 3);
    assert(weaksum_digest(&r) == 0xf284a77f);
    weaksum_rollout(&r, 5);
    weaksum_rollout(&r, 6);
    weaksum_rollout(&r, 7);     /* [] */
    assert(weaksum_count(&r) == 0);
    assert(weaksum_digest(&r) == 0x00000001);

    /* Test weaksum_update() */
    weaksum_update(&r, buf, 256);
    assert(weaksum_digest(&r) == 0xc1972381);

    /* Test weaksum_reset() */
    weaksum_reset(&r);
    assert(r.kind == RS_RABINKARP);
    assert(weaksum_count(&r) == 0);
    assert(weaksum_digest(&r) == 0x00000001);

    /* Test rs_calc_weaksum() */
    assert(rs_calc_weak_sum(RS_ROLLSUM, buf, 256) == 0x3a009e80);
    assert(rs_calc_weak_sum(RS_RABINKARP, buf, 256) == 0xc1972381);

    /* Test rs_calc_strongsum() */
    rs_strong_sum_t sum;
    const unsigned char md4[16] = {
        0x29, 0x8a, 0x05, 0xbc, 0x50, 0x6e, 0x1e, 0xcd,
        0x5a, 0x47, 0xfd, 0x41, 0xf8, 0x74, 0xf1, 0xd2,
    };
    const unsigned char bk2[32] = {
        0x39, 0xa7, 0xeb, 0x9f, 0xed, 0xc1, 0x9a, 0xab,
        0xc8, 0x34, 0x25, 0xc6, 0x75, 0x5d, 0xd9, 0x0e,
        0x6f, 0x9d, 0x0c, 0x80, 0x49, 0x64, 0xa1, 0xf4,
        0xaa, 0xee, 0xa3, 0xb9, 0xfb, 0x59, 0x98, 0x35,
    };

    rs_calc_strong_sum(RS_MD4, buf, 256, &sum);
    assert(!memcmp(sum, md4, RS_MD4_SUM_LENGTH));
    rs_calc_strong_sum(RS_BLAKE2, buf, 256, &sum);
    assert(!memcmp(sum, bk2, RS_BLAKE2_SUM_LENGTH));
    return 0;
}
