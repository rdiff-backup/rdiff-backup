/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- the library for network deltas
 *
 * Copyright (C) 2000 by Martin Pool <mbp@sourcefrog.net>
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
#include <stdlib.h>
#include <stdio.h>

#include "librsync.h"

/** Decode a base64 string in-place - simple and slow algorithm.
 *
 * See RFC1521 for the specification of base64. */
size_t rs_unbase64(char *s)
{
    char const *b64 =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    int bit_offset, byte_offset, idx, i, n;
    unsigned char *d = (unsigned char *)s;
    char *p;

    n = i = 0;

    while (*s && (p = strchr(b64, *s))) {
        idx = (int)(p - b64);
        byte_offset = (i * 6) / 8;
        bit_offset = (i * 6) % 8;
        d[byte_offset] &= ~((1 << (8 - bit_offset)) - 1);
        if (bit_offset < 3) {
            d[byte_offset] |= (idx << (2 - bit_offset));
            n = byte_offset + 1;
        } else {
            d[byte_offset] |= (idx >> (bit_offset - 2));
            d[byte_offset + 1] = 0;
            d[byte_offset + 1] |= (idx << (8 - (bit_offset - 2))) & 0xFF;
            n = byte_offset + 2;
        }
        s++;
        i++;
    }

    return n;
}

/** Encode a buffer as base64 - simple and slow algorithm. */
void rs_base64(unsigned char const *buf, int n, char *out)
{
    char const *b64 =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    int bytes, i;

    /* work out how many bytes of output there are */
    bytes = ((n * 8) + 5) / 6;

    for (i = 0; i < bytes; i++) {
        int byte = (i * 6) / 8;
        int bit = (i * 6) % 8;

        if (bit < 3) {
            if (byte >= n)
                abort();
            *out = b64[(buf[byte] >> (2 - bit)) & 0x3F];
        } else {
            if (byte + 1 == n) {
                *out = b64[(buf[byte] << (bit - 2)) & 0x3F];
            } else {
                *out =
                    b64[(buf[byte] << (bit - 2) | buf[byte + 1] >> (10 - bit)) &
                        0x3F];
            }
        }
        out++;
    }
    *out = 0;
}
