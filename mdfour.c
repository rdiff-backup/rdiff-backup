/*				       	-*- c-file-style: "linux" -*-
 * libhsync -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool <mbp@linuxcare.com.au>
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

/* NOTE: This code makes no attempt to be fast!

   It assumes that a int is at least 32 bits long

   TODO: Recode to be fast, and to use system integer types.  Perhaps if we
   can find an mdfour implementation already on the system (e.g. in OpenSSL)
   then we should use it instead of our own? */

#include "config.h"


#include <stdlib.h>
#include <stdio.h>
#include <stdint.h>

#include "hsync.h"




#define F(X,Y,Z) (((X)&(Y)) | ((~(X))&(Z)))
#define G(X,Y,Z) (((X)&(Y)) | ((X)&(Z)) | ((Y)&(Z)))
#define H(X,Y,Z) ((X)^(Y)^(Z))
#ifdef LARGE_INT32
#define lshift(x,s) ((((x)<<(s))&0xFFFFFFFF) | (((x)>>(32-(s)))&0xFFFFFFFF))
#else
#define lshift(x,s) (((x)<<(s)) | ((x)>>(32-(s))))
#endif

#define ROUND1(a,b,c,d,k,s) a = lshift(a + F(b,c,d) + X[k], s)
#define ROUND2(a,b,c,d,k,s) a = lshift(a + G(b,c,d) + X[k] + 0x5A827999,s)
#define ROUND3(a,b,c,d,k,s) a = lshift(a + H(b,c,d) + X[k] + 0x6ED9EBA1,s)

/* this applies md4 to 64 byte chunks */
static void
hs_mdfour64(hs_mdfour_t * m, uint32_t * M)
{
    int             j;
    uint32_t        AA, BB, CC, DD;
    uint32_t        X[16];
    uint32_t        A, B, C, D;

    for (j = 0; j < 16; j++)
	X[j] = M[j];

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

#ifdef LARGE_INT32
    A &= 0xFFFFFFFF;
    B &= 0xFFFFFFFF;
    C &= 0xFFFFFFFF;
    D &= 0xFFFFFFFF;
#endif

    for (j = 0; j < 16; j++)
	X[j] = 0;

    m->A = A;
    m->B = B;
    m->C = C;
    m->D = D;
}

static void
copy64( /* @out@ */ uint32_t * M, unsigned char const *in)
{
    int             i;

    for (i = 0; i < 16; i++)
	M[i] = (in[i * 4 + 3] << 24) | (in[i * 4 + 2] << 16) |
	    (in[i * 4 + 1] << 8) | (in[i * 4 + 0] << 0);
}

static void
copy4( /* @out@ */ unsigned char *out, uint32_t const x)
{
    out[0] = x & 0xFF;
    out[1] = (x >> 8) & 0xFF;
    out[2] = (x >> 16) & 0xFF;
    out[3] = (x >> 24) & 0xFF;
}



void
hs_mdfour_begin(hs_mdfour_t * md)
{
    memset(md, 0, sizeof(*md));
    md->A = 0x67452301;
    md->B = 0xefcdab89;
    md->C = 0x98badcfe;
    md->D = 0x10325476;
    md->totalN = 0;
}


static void
hs_mdfour_tail(hs_mdfour_t * m, unsigned char const *in, int n)
{
    unsigned char   buf[128];
    uint32_t        M[16];
    uint32_t        b;

    m->totalN += n;

    b = m->totalN * 8;

    memset(buf, 0, 128);
    if (n)
	memcpy(buf, in, n);
    buf[n] = 0x80;

    if (n <= 55) {
	copy4(buf + 56, b);
	copy64(M, buf);
	hs_mdfour64(m, M);
    } else {
	copy4(buf + 120, b);
	copy64(M, buf);
	hs_mdfour64(m, M);
	copy64(M, buf + 64);
	hs_mdfour64(m, M);
    }
}



void
hs_mdfour_update(hs_mdfour_t * md, void const *in_void, size_t n)
{
    uint32_t        M[16];
    size_t          n2 = 64 - md->tail_len;
    unsigned char const        *in = (unsigned char const *) in_void;

    if (n == 0)
	return;

    if (n2 > n)
	n2 = n;
    memcpy(&md->tail[md->tail_len], in, n2);
    md->tail_len += n2;
    in += n2;
    n -= n2;

    if (md->tail_len != 64)
	return;

    copy64(M, md->tail);
    hs_mdfour64(md, M);
    md->tail_len = 0;
    md->totalN += 64;

    while (n >= 64) {
	copy64(M, in);
	hs_mdfour64(md, M);
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
hs_mdfour_result(hs_mdfour_t * md, unsigned char *out)
{
    hs_mdfour_tail(md, md->tail, md->tail_len);

    copy4(out, md->A);
    copy4(out + 4, md->B);
    copy4(out + 8, md->C);
    copy4(out + 12, md->D);
}


void
hs_mdfour(unsigned char *out, void const *in, int n)
{
    hs_mdfour_t     md;

    hs_mdfour_begin(&md);
    hs_mdfour_update(&md, in, n);
    hs_mdfour_result(&md, out);
}
