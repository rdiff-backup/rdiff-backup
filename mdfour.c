/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- the library for network deltas
 * $Id$
 * 
 * Copyright (C) 2000, 2001 by Martin Pool <mbp@samba.org>
 * Copyright (C) 1997-1999 by Andrew Tridgell
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

/* MD4 message digest algorithm.
 *
 * TODO: Perhaps use the MD4 routine from OpenSSL if it's installed.
 * It's probably not worth the trouble.
 *
 * This was originally written by Andrew Tridgell for use in Samba. */

#include <config.h>

#include <stdlib.h>
#include <string.h>
#include <stdio.h>

#include "rsync.h"
#include "trace.h"
#include "types.h"


static void (*rs_mdfour_block)(rs_mdfour_t *md, void const *p) = NULL;

     
#define F(X,Y,Z) (((X)&(Y)) | ((~(X))&(Z)))
#define G(X,Y,Z) (((X)&(Y)) | ((X)&(Z)) | ((Y)&(Z)))
#define H(X,Y,Z) ((X)^(Y)^(Z))
#define lshift(x,s) (((x)<<(s)) | ((x)>>(32-(s))))

#define ROUND1(a,b,c,d,k,s) a = lshift(a + F(b,c,d) + X[k], s)
#define ROUND2(a,b,c,d,k,s) a = lshift(a + G(b,c,d) + X[k] + 0x5A827999,s)
#define ROUND3(a,b,c,d,k,s) a = lshift(a + H(b,c,d) + X[k] + 0x6ED9EBA1,s)

/**
 * Update an MD4 accumulator from a 64-byte chunk.
 *
 * This cannot be used for the last chunk of the file, which must be
 * padded and contain the file length.  rs_mdfour_tail() is used for
 * that.
 *
 * \todo Recode to be fast, and to use system integer types.  Perhaps
 * if we can find an mdfour implementation already on the system
 * (e.g. in OpenSSL) then we should use it instead of our own?
 *
 * \param X A series of integer, read little-endian from the file.
 */
static void
rs_mdfour64(rs_mdfour_t * m, const void *p)
{
    uint32_t        AA, BB, CC, DD;
    uint32_t        A, B, C, D;
    const uint32_t *X = (const uint32_t *) p;

    A = m->A;
    B = m->B;
    C = m->C;
    D = m->D;
    AA = A;
    BB = B;
    CC = C;
    DD = D;

    ROUND1(A, B, C, D, 0, 3);
    ROUND1(D, A, B, C, 1, 7);
    ROUND1(C, D, A, B, 2, 11);
    ROUND1(B, C, D, A, 3, 19);
    ROUND1(A, B, C, D, 4, 3);
    ROUND1(D, A, B, C, 5, 7);
    ROUND1(C, D, A, B, 6, 11);
    ROUND1(B, C, D, A, 7, 19);
    ROUND1(A, B, C, D, 8, 3);
    ROUND1(D, A, B, C, 9, 7);
    ROUND1(C, D, A, B, 10, 11);
    ROUND1(B, C, D, A, 11, 19);
    ROUND1(A, B, C, D, 12, 3);
    ROUND1(D, A, B, C, 13, 7);
    ROUND1(C, D, A, B, 14, 11);
    ROUND1(B, C, D, A, 15, 19);

    ROUND2(A, B, C, D, 0, 3);
    ROUND2(D, A, B, C, 4, 5);
    ROUND2(C, D, A, B, 8, 9);
    ROUND2(B, C, D, A, 12, 13);
    ROUND2(A, B, C, D, 1, 3);
    ROUND2(D, A, B, C, 5, 5);
    ROUND2(C, D, A, B, 9, 9);
    ROUND2(B, C, D, A, 13, 13);
    ROUND2(A, B, C, D, 2, 3);
    ROUND2(D, A, B, C, 6, 5);
    ROUND2(C, D, A, B, 10, 9);
    ROUND2(B, C, D, A, 14, 13);
    ROUND2(A, B, C, D, 3, 3);
    ROUND2(D, A, B, C, 7, 5);
    ROUND2(C, D, A, B, 11, 9);
    ROUND2(B, C, D, A, 15, 13);

    ROUND3(A, B, C, D, 0, 3);
    ROUND3(D, A, B, C, 8, 9);
    ROUND3(C, D, A, B, 4, 11);
    ROUND3(B, C, D, A, 12, 15);
    ROUND3(A, B, C, D, 2, 3);
    ROUND3(D, A, B, C, 10, 9);
    ROUND3(C, D, A, B, 6, 11);
    ROUND3(B, C, D, A, 14, 15);
    ROUND3(A, B, C, D, 1, 3);
    ROUND3(D, A, B, C, 9, 9);
    ROUND3(C, D, A, B, 5, 11);
    ROUND3(B, C, D, A, 13, 15);
    ROUND3(A, B, C, D, 3, 3);
    ROUND3(D, A, B, C, 11, 9);
    ROUND3(C, D, A, B, 7, 11);
    ROUND3(B, C, D, A, 15, 15);

    A += AA;
    B += BB;
    C += CC;
    D += DD;

    m->A = A;
    m->B = B;
    m->C = C;
    m->D = D;
}


/* These next two routines are necessary because MD4 is specified in
 * terms of little-endian int32s, but we have a byte buffer.  On
 * little-endian platforms, I think we can just use the buffer pointer
 * directly.
 *
 * There are some nice endianness routines in glib, including
 * assembler variants.  If we ever depended on glib, then it could be
 * good to use them instead. */
static void
copy64( /* @out@ */ uint32_t * M, unsigned char const *in)
{
    int i=16;

    while (i--) {
        *M++ = (in[3] << 24) | (in[2] << 16) | (in[1] << 8) | in[0];
        in += 4;
    }
}

static void
copy4( /* @out@ */ unsigned char *out, uint32_t const x)
{
    out[0] = x & 0xFF;
    out[1] = (x >> 8) & 0xFF;
    out[2] = (x >> 16) & 0xFF;
    out[3] = (x >> 24) & 0xFF;
}



/**
 * Accumulate a block, making appropriate conversions for bigendian
 * machines.
 */
static void
rs_mdfour_block_slow(rs_mdfour_t *md, void const *p)
{
    uint32_t        M[16];

    copy64(M, p);
    rs_mdfour64(md, M);
}


static void
rs_mdfour_choose_packer(void)
{
    const uint32_t foo = 0x01020304;
    char *p = (char *)&foo;
    
    if (sizeof(uint32_t) != 4)
        rs_fatal("internal error: uint32_t is not really 32 bits!");
    if (sizeof(foo) != 4)
        rs_fatal("internal error: something wierd about char arrays");

    if (*p == 0x1) {
        rs_trace("big-endian machine");
        rs_mdfour_block = rs_mdfour_block_slow;
    } else if (*p == 0x4) {
        rs_trace("little-endian machine");
        rs_mdfour_block = rs_mdfour64;
    } else {
        rs_fatal("world is broken - can't determine endianness from %#x", *p);
    }
}


void
rs_mdfour_begin(rs_mdfour_t * md)
{
    if (!rs_mdfour_block)
        rs_mdfour_choose_packer();

    memset(md, 0, sizeof(*md));
    md->A = 0x67452301;
    md->B = 0xefcdab89;
    md->C = 0x98badcfe;
    md->D = 0x10325476;
    md->totalN = 0;
}


/**
 * Handle special behaviour for processing the last block of a file
 * when calculating its MD4 checksum.
 *
 * This must be called exactly once per file.
 */
static void
rs_mdfour_tail(rs_mdfour_t * m, unsigned char const *in, int n)
{
    unsigned char   buf[128];
    uint32_t        b;

    m->totalN += n;

    b = m->totalN * 8;

    memset(buf, 0, 128);
    if (n)
        memcpy(buf, in, n);
    buf[n] = 0x80;

    if (n <= 55) {
        copy4(buf + 56, b);
        rs_mdfour_block(m, buf);
    } else {
        copy4(buf + 120, b);
        rs_mdfour_block(m, buf);
        rs_mdfour_block(m, buf + 64);
    }
}


/**
 * Feed some data into the MD4 accumulator.
 *
 * \param n Number of bytes fed in.
 */
void
rs_mdfour_update(rs_mdfour_t * md, void const *in_void, size_t n)
{
    unsigned char const        *in = (unsigned char const *) in_void;

    if (n == 0)
        return;

    if (md->tail_len) {
        size_t                     tail_gap = 64 - md->tail_len;

        /* If there's any leftover data in the tail buffer, then first
         * we have to make it up to a whole block and process it. */
        if (tail_gap > n)
            tail_gap = n;
        memcpy(&md->tail[md->tail_len], in, tail_gap);
        md->tail_len += tail_gap;
        in += tail_gap;
        n -= tail_gap;

        if (md->tail_len != 64)
            return;

        rs_mdfour_block(md, md->tail);
        md->tail_len = 0;
        md->totalN += 64;
    }

    while (n >= 64) {
        rs_mdfour_block(md, in);
        in += 64;
        n -= 64;
        md->totalN += 64;
    }

    if (n) {
        memcpy(md->tail, in, n);
        md->tail_len = n;
    }
}


void
rs_mdfour_result(rs_mdfour_t * md, unsigned char *out)
{
    rs_mdfour_tail(md, md->tail, md->tail_len);

    copy4(out, md->A);
    copy4(out + 4, md->B);
    copy4(out + 8, md->C);
    copy4(out + 12, md->D);
}


void
rs_mdfour(unsigned char *out, void const *in, size_t n)
{
    rs_mdfour_t     md;

    rs_mdfour_begin(&md);
    rs_mdfour_update(&md, in, n);
    rs_mdfour_result(&md, out);
}
