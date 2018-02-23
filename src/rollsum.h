/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * rollsum -- the librsync rolling checksum
 *
 * Copyright (C) 2003 by Donovan Baarda <abo@minkirri.apana.org.au>
 * based on work, Copyright (C) 2000, 2001 by Martin Pool <mbp@sourcefrog.net>
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
#ifndef _ROLLSUM_H_
#  define _ROLLSUM_H_

#  include <stddef.h>
#  include <stdint.h>

/* We should make this something other than zero to improve the checksum
   algorithm: tridge suggests a prime number. */
#  define ROLLSUM_CHAR_OFFSET 31

/** The Rollsum struct type \private. */
typedef struct _Rollsum {
    size_t count;               /* count of bytes included in sum */
    uint_fast16_t s1;           /* s1 part of sum */
    uint_fast16_t s2;           /* s2 part of sum */
} Rollsum;

void RollsumUpdate(Rollsum *sum, const unsigned char *buf, size_t len);

/* static inline implementations of simple routines */

static inline void RollsumInit(Rollsum *sum)
{
    sum->count = sum->s1 = sum->s2 = 0;
}

static inline void RollsumRotate(Rollsum *sum, unsigned char out,
                                 unsigned char in)
{
    sum->s1 += in - out;
    sum->s2 += sum->s1 - sum->count * (out + ROLLSUM_CHAR_OFFSET);
}

static inline void RollsumRollin(Rollsum *sum, unsigned char in)
{
    sum->s1 += in + ROLLSUM_CHAR_OFFSET;
    sum->s2 += sum->s1;
    sum->count++;
}

static inline void RollsumRollout(Rollsum *sum, unsigned char out)
{
    sum->s1 -= out + ROLLSUM_CHAR_OFFSET;
    sum->s2 -= sum->count * (out + ROLLSUM_CHAR_OFFSET);
    sum->count--;
}

static inline uint32_t RollsumDigest(Rollsum *sum)
{
    return ((uint32_t)sum->s2 << 16) | ((uint32_t)sum->s1 & 0xffff);
}

#endif                          /* _ROLLSUM_H_ */
