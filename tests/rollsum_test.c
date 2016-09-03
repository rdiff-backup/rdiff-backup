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
#include "rollsum.h"

/*
 * Test driver for rollsum.
 */
int main(int argc, char **argv)
{
    Rollsum r;
    int i;
    unsigned char buf[256];

    /* Test RollsumInit() */
    RollsumInit(&r);
    assert(r.count == 0);
    assert(r.s1 == 0);
    assert(r.s2 == 0);
    assert(RollsumDigest(&r) == 0x00000000);

    /* Test RollsumRollin() */
    RollsumRollin(&r, 0);       /* [0] */
    assert(r.count == 1);
    assert(RollsumDigest(&r) == 0x001f001f);
    RollsumRollin(&r, 1);
    RollsumRollin(&r, 2);
    RollsumRollin(&r, 3);       /* [0,1,2,3] */
    assert(r.count == 4);
    assert(RollsumDigest(&r) == 0x01400082);

    /* Test RollsumRotate() */
    RollsumRotate(&r, 0, 4);    /* [1,2,3,4] */
    assert(r.count == 4);
    assert(RollsumDigest(&r) == 0x014a0086);
    RollsumRotate(&r, 1, 5);
    RollsumRotate(&r, 2, 6);
    RollsumRotate(&r, 3, 7);    /* [4,5,6,7] */
    assert(r.count == 4);
    assert(RollsumDigest(&r) == 0x01680092);

    /* Test RollsumRollout() */
    RollsumRollout(&r, 4);      /* [5,6,7] */
    assert(r.count == 3);
    assert(RollsumDigest(&r) == 0x00dc006f);
    RollsumRollout(&r, 5);
    RollsumRollout(&r, 6);
    RollsumRollout(&r, 7);      /* [] */
    assert(r.count == 0);
    assert(RollsumDigest(&r) == 0x00000000);

    /* Test RollsumUpdate() */
    for (i = 0; i < 256; i++)
        buf[i] = i;
    RollsumUpdate(&r, buf, 256);
    assert(RollsumDigest(&r) == 0x3a009e80);
    return 0;
}
