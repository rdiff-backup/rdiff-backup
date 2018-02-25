/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- the library for network deltas
 *
 * Copyright (C) 2000, 2001 by Martin Pool <mbp@sourcefrog.net>
 * Copyright (C) 1997-1999 by Andrew Tridgell
 * Copyright (C) 2002, 2003 by Donovan Baarda <abo@minkirri.apana.org.au>
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

/** \file mdfour.c MD4 message digest algorithm.
 *
 * \todo Perhaps use the MD4 routine from OpenSSL if it's installed. It's
 * probably not worth the trouble.
 *
 * This was originally written by Andrew Tridgell for use in Samba. It was then
 * modified by;
 *
 * 2002-06-xx: Robert Weber <robert.weber@Colorado.edu> optimisations and fixed
 * >512M support.
 *
 * 2002-06-27: Donovan Baarda <abo@minkirri.apana.org.au> further optimisations
 * and cleanups.
 *
 * 2004-09-09: Simon Law <sfllaw@debian.org> handle little-endian machines that
 * can't do unaligned access (e.g. ia64, pa-risc). */

#include "config.h"

#include <stdlib.h>
#include <string.h>
#include <stdio.h>

#include "librsync.h"
#include "trace.h"
#include "mdfour.h"

#define F(X,Y,Z) (((X)&(Y)) | ((~(X))&(Z)))
#define G(X,Y,Z) (((X)&(Y)) | ((X)&(Z)) | ((Y)&(Z)))
#define H(X,Y,Z) ((X)^(Y)^(Z))
#define lshift(x,s) (((x)<<(s)) | ((x)>>(32-(s))))

#define ROUND1(a,b,c,d,k,s) a = lshift(a + F(b,c,d) + X[k], s)
#define ROUND2(a,b,c,d,k,s) a = lshift(a + G(b,c,d) + X[k] + 0x5A827999,s)
#define ROUND3(a,b,c,d,k,s) a = lshift(a + H(b,c,d) + X[k] + 0x6ED9EBA1,s)

/** padding data used for finalising */
static unsigned char PADDING[64] = {
    0x80, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
};

static void rs_mdfour_block(rs_mdfour_t *md, void const *p);

/** Update an MD4 accumulator from a 64-byte chunk.
 *
 * This cannot be used for the last chunk of the file, which must be padded and
 * contain the file length. rs_mdfour_tail() is used for that.
 *
 * \todo Recode to be fast, and to use system integer types. Perhaps if we can
 * find an mdfour implementation already on the system (e.g. in OpenSSL) then
 * we should use it instead of our own?
 *
 * \param X A series of integer, read little-endian from the file. */
static void rs_mdfour64(rs_mdfour_t *m, const void *p)
{
    uint32_t AA, BB, CC, DD;
    uint32_t A, B, C, D;
    const uint32_t *X = (const uint32_t *)p;

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

/** These next routines are necessary because MD4 is specified in terms of
 * little-endian int32s, but we have a byte buffer. On little-endian platforms,
 * I think we can just use the buffer pointer directly.
 *
 * There are some nice endianness routines in glib, including assembler
 * variants. If we ever depended on glib, then it could be good to use them
 * instead. */
inline static void copy4( /* @out@ */ unsigned char *out, uint32_t const x)
{
    out[0] = x;
    out[1] = x >> 8;
    out[2] = x >> 16;
    out[3] = x >> 24;
}

/* We need this if there is a uint64 */
/* --robert.weber@Colorado.edu */
#ifdef HAVE_UINT64
inline static void copy8( /* @out@ */ unsigned char *out, uint64_t const x)
{
    out[0] = x;
    out[1] = x >> 8;
    out[2] = x >> 16;
    out[3] = x >> 24;
    out[4] = x >> 32;
    out[5] = x >> 40;
    out[6] = x >> 48;
    out[7] = x >> 56;
}
#endif                          /* HAVE_UINT64 */

/* We only need this if we are big-endian */
#ifdef WORDS_BIGENDIAN
inline static void copy64( /* @out@ */ uint32_t *M, unsigned char const *in)
{
    int i = 16;

    while (i--) {
        *M++ = (in[3] << 24) | (in[2] << 16) | (in[1] << 8) | in[0];
        in += 4;
    }
}

/** Accumulate a block, making appropriate conversions for bigendian machines.
 */
inline static void rs_mdfour_block(rs_mdfour_t *md, void const *p)
{
    uint32_t M[16];

    copy64(M, p);
    rs_mdfour64(md, M);
}

#else                           /* WORDS_BIGENDIAN */

#  ifdef __i386__

/* If we are on an IA-32 machine, we can process directly. */
inline static void rs_mdfour_block(rs_mdfour_t *md, void const *p)
{
    rs_mdfour64(md, p);
}

#  else                         /* !WORDS_BIGENDIAN && !__i386__ */

/* We are little-endian, but not on i386 and therefore may not be able to do
   unaligned access safely/quickly.

   So if the input is not already aligned correctly, copy it to an aligned
   buffer first. */
inline static void rs_mdfour_block(rs_mdfour_t *md, void const *p)
{
    unsigned long ptrval = (unsigned long)p;

    if (ptrval & 3) {
        uint32_t M[16];

        memcpy(M, p, 16 * sizeof(uint32_t));
        rs_mdfour64(md, M);
    } else {
        rs_mdfour64(md, (const uint32_t *)p);
    }
}

#  endif                        /* !__i386__ */
#endif                          /* WORDS_BIGENDIAN */

void rs_mdfour_begin(rs_mdfour_t *md)
{
    memset(md, 0, sizeof(*md));
    md->A = 0x67452301;
    md->B = 0xefcdab89;
    md->C = 0x98badcfe;
    md->D = 0x10325476;
#if HAVE_UINT64
    md->totalN = 0;
#else
    md->totalN_hi = md->totalN_lo = 0;
#endif
}

/** Handle special behaviour for processing the last block of a file when
 * calculating its MD4 checksum.
 *
 * This must be called exactly once per file.
 *
 * Modified by Robert Weber to use uint64 in order that we can sum files > 2^29
 * = 512 MB. --Robert.Weber@colorado.edu */
static void rs_mdfour_tail(rs_mdfour_t *m)
{
#ifdef HAVE_UINT64
    uint64_t b;
#else                           /* HAVE_UINT64 */
    uint32_t b[2];
#endif                          /* HAVE_UINT64 */
    unsigned char buf[8];
    size_t pad_len;

    /* convert the totalN byte count into a bit count buffer */
#ifdef HAVE_UINT64
    b = m->totalN << 3;
    copy8(buf, b);
#else                           /* HAVE_UINT64 */
    b[0] = m->totalN_lo << 3;
    b[1] = ((m->totalN_hi << 3) | (m->totalN_lo >> 29));
    copy4(buf, b[0]);
    copy4(buf + 4, b[1]);
#endif                          /* HAVE_UINT64 */

    /* calculate length and process the padding data */
    pad_len = (m->tail_len < 56) ? (56 - m->tail_len) : (120 - m->tail_len);
    rs_mdfour_update(m, PADDING, pad_len);
    /* process the bit count */
    rs_mdfour_update(m, buf, 8);
}

void rs_mdfour_update(rs_mdfour_t *md, void const *in_void, size_t n)
{
    unsigned char const *in = (unsigned char const *)in_void;

    /* increment totalN */
#ifdef HAVE_UINT64
    md->totalN += n;
#else                           /* HAVE_UINT64 */
    if ((md->totalN_lo += n) < n)
        md->totalN_hi++;
#endif                          /* HAVE_UINT64 */

    /* If there's any leftover data in the tail buffer, then first we have to
       make it up to a whole block to process it. */
    if (md->tail_len) {
        size_t tail_gap = 64 - md->tail_len;
        if (tail_gap <= n) {
            memcpy(&md->tail[md->tail_len], in, tail_gap);
            rs_mdfour_block(md, md->tail);
            in += tail_gap;
            n -= tail_gap;
            md->tail_len = 0;
        }
    }
    /* process complete blocks of input */
    while (n >= 64) {
        rs_mdfour_block(md, in);
        in += 64;
        n -= 64;
    }
    /* Put remaining bytes onto tail */
    if (n) {
        memcpy(&md->tail[md->tail_len], in, n);
        md->tail_len += n;
    }
}

void rs_mdfour_result(rs_mdfour_t *md, unsigned char *out)
{
    rs_mdfour_tail(md);

    copy4(out, md->A);
    copy4(out + 4, md->B);
    copy4(out + 8, md->C);
    copy4(out + 12, md->D);
}

void rs_mdfour(unsigned char *out, void const *in, size_t n)
{
    rs_mdfour_t md;

    rs_mdfour_begin(&md);
    rs_mdfour_update(&md, in, n);
    rs_mdfour_result(&md, out);
}
