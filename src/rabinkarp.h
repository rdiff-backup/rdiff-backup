/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * rabinkarp -- The RabinKarp rolling checksum.
 *
 * Copyright (C) 2019 by Donovan Baarda <abo@minkirri.apana.org.au>
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
#ifndef _RABINKARP_H_
#  define _RABINKARP_H_

#  include <stddef.h>
#  include <stdint.h>

/** The RabinKarp seed value.
 *
 * The seed ensures different length zero blocks have different hashes. It
 * effectively encodes the length into the hash. */
#  define RABINKARP_SEED 1

/** The RabinKarp multiplier.
 *
 * This multiplier has a bit pattern of 1's getting sparser with significance,
 * is the product of 2 large primes, and matches the characterstics for a good
 * LCG multiplier. */
#  define RABINKARP_MULT 0x08104225

/** The RabinKarp inverse multiplier.
 *
 * This is the inverse of RABINKARP_MULT modular 2^32. Multiplying by this is
 * equivalent to dividing by RABINKARP_MULT. */
#  define RABINKARP_INVM 0x98f009ad

/** The RabinKarp seed adjustment.
 *
 * This is a factor used to adjust for the seed when rolling out values. It's
 * equal to; (RABINKARP_MULT - 1) * RABINKARP_SEED */
#  define RABINKARP_ADJ 0x08104224

/** The rabinkarp_t state type. */
typedef struct _rabinkarp {
    size_t count;               /**< Count of bytes included in sum. */
    uint32_t hash;              /**< The accumulated hash value. */
    uint32_t mult;              /**< The value of RABINKARP_MULT^count. */
} rabinkarp_t;

static inline uint32_t uint32_pow(uint32_t m, size_t p)
{
    uint32_t ans = 1;
    while (p) {
        if (p & 1) {
            ans *= m;
        }
        m *= m;
        p >>= 1;
    }
    return ans;
}

static inline void rabinkarp_init(rabinkarp_t *sum)
{
    sum->count = 0;
    sum->hash = RABINKARP_SEED;
    sum->mult = 1;
}

static inline void rabinkarp_update(rabinkarp_t *sum, const unsigned char *buf,
                                    size_t len)
{
    for (size_t i = len; i; i--) {
        sum->hash = sum->hash * RABINKARP_MULT + *buf++;
    }
    sum->count += len;
    sum->mult *= uint32_pow(RABINKARP_MULT, len);
}

static inline void rabinkarp_rotate(rabinkarp_t *sum, unsigned char out,
                                    unsigned char in)
{
    sum->hash =
        sum->hash * RABINKARP_MULT + in - sum->mult * (out + RABINKARP_ADJ);
}

static inline void rabinkarp_rollin(rabinkarp_t *sum, unsigned char in)
{
    sum->hash = sum->hash * RABINKARP_MULT + in;
    sum->count++;
    sum->mult *= RABINKARP_MULT;
}

static inline void rabinkarp_rollout(rabinkarp_t *sum, unsigned char out)
{
    sum->count--;
    sum->mult *= RABINKARP_INVM;
    sum->hash -= sum->mult * (out + RABINKARP_ADJ);
}

static inline uint32_t rabinkarp_digest(rabinkarp_t *sum)
{
    return sum->hash;
}

#endif                          /* _RABINKARP_H_ */
