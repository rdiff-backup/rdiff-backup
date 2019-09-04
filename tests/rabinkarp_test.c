/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * rabinkarp_test -- tests for the rabinkarp_t rolling checksum.
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
#include "rabinkarp.h"

int main(int argc, char **argv)
{
    rabinkarp_t r;
    int i;
    unsigned char buf[256];

    /* Test rabinkarp_init() */
    rabinkarp_init(&r);
    assert(r.count == 0);
    assert(r.hash == 1);
    assert(rabinkarp_digest(&r) == 0x00000001);

    /* Test rabinkarp_rollin() */
    rabinkarp_rollin(&r, 0);    /* [0] */
    assert(r.count == 1);
    assert(rabinkarp_digest(&r) == 0x08104225);
    rabinkarp_rollin(&r, 1);
    rabinkarp_rollin(&r, 2);
    rabinkarp_rollin(&r, 3);    /* [0,1,2,3] */
    assert(r.count == 4);
    assert(rabinkarp_digest(&r) == 0xaf981e97);

    /* Test rabinkarp_rotate() */
    rabinkarp_rotate(&r, 0, 4); /* [1,2,3,4] */
    assert(r.count == 4);
    assert(rabinkarp_digest(&r) == 0xe2ef15f3);
    rabinkarp_rotate(&r, 1, 5);
    rabinkarp_rotate(&r, 2, 6);
    rabinkarp_rotate(&r, 3, 7); /* [4,5,6,7] */
    assert(r.count == 4);
    assert(rabinkarp_digest(&r) == 0x7cf3fc07);

    /* Test rabinkarp_rollout() */
    rabinkarp_rollout(&r, 4);   /* [5,6,7] */
    assert(r.count == 3);
    assert(rabinkarp_digest(&r) == 0xf284a77f);
    rabinkarp_rollout(&r, 5);
    rabinkarp_rollout(&r, 6);
    rabinkarp_rollout(&r, 7);   /* [] */
    assert(r.count == 0);
    assert(rabinkarp_digest(&r) == 0x00000001);

    /* Test rabinkarp_update() */
    for (i = 0; i < 256; i++)
        buf[i] = i;
    rabinkarp_update(&r, buf, 256);
    assert(rabinkarp_digest(&r) == 0xc1972381);
    return 0;
}
