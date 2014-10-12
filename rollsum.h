/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * rollsum -- the librsync rolling checksum
 * $Id$
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
#define _ROLLSUM_H_

/* We should make this something other than zero to improve the
 * checksum algorithm: tridge suggests a prime number. */
#define ROLLSUM_CHAR_OFFSET 31

/* the Rollsum struct type*/
typedef struct _Rollsum {
    unsigned long count;               /* count of bytes included in sum */
    unsigned long s1;                  /* s1 part of sum */
    unsigned long s2;                  /* s2 part of sum */
} Rollsum;

void RollsumUpdate(Rollsum *sum,const unsigned char *buf,unsigned int len);
/* The following are implemented as macros.
void RollsumInit(Rollsum *sum);
void RollsumRotate(Rollsum *sum,unsigned char out, unsigned char in);
void RollsumRollin(Rollsum *sum,unsigned char c);
void RollsumRollout(Rollsum *sum,unsigned char c);
unsigned long RollsumDigest(Rollsum *sum);
*/

/* macro implementations of simple routines */
#define RollsumInit(sum) { \
    (sum)->count=(sum)->s1=(sum)->s2=0; \
}

#define RollsumRotate(sum,out,in) { \
    (sum)->s1 += (unsigned char)(in) - (unsigned char)(out); \
    (sum)->s2 += (sum)->s1 - (sum)->count*((unsigned char)(out)+ROLLSUM_CHAR_OFFSET); \
}

#define RollsumRollin(sum,c) { \
    (sum)->s1 += ((unsigned char)(c)+ROLLSUM_CHAR_OFFSET); \
    (sum)->s2 += (sum)->s1; \
    (sum)->count++; \
}

#define RollsumRollout(sum,c) { \
    (sum)->s1 -= ((unsigned char)(c)+ROLLSUM_CHAR_OFFSET); \
    (sum)->s2 -= (sum)->count*((unsigned char)(c)+ROLLSUM_CHAR_OFFSET); \
    (sum)->count--; \
}

#define RollsumDigest(sum) (((sum)->s2 << 16) | ((sum)->s1 & 0xffff))

#endif /* _ROLLSUM_H_ */
