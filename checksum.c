/*				       	-*- c-file-style: "linux" -*-
 *
 * $Id$
 * 
 * Copyright (C) 1999, 2000 by Martin Pool <mbp@linuxcare.com.au>
 * Copyright (C) 1996 by Andrew Tridgell
 * Copyright (C) 1996 by Paul Mackerras
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

#include "includes.h"

/* XXX: I think this is obsolete. */
int checksum_seed = 0;

/*
 * A simple 32 bit checksum that can be updated from either end
 * (inspired by Mark Adler's Adler-32 checksum)
 */
uint32_t _hs_calc_weak_sum(byte_t const *buf1, int len)
{
     int i;
     uint32_t s1, s2;
     int8_t const *buf = (int8_t const *) buf1;	/* this is signed */

     s1 = s2 = 0;
     for (i = 0; i < (len - 4); i += 4) {
	  s2 += 4 * (s1 + buf[i]) + 3 * buf[i + 1] +
	       2 * buf[i + 2] + buf[i + 3] + 10 * CHAR_OFFSET;
	  s1 += (buf[i + 0] + buf[i + 1] + buf[i + 2] + buf[i + 3] +
		 4 * CHAR_OFFSET);
     }
     for (; i < len; i++) {
	  s1 += (buf[i] + CHAR_OFFSET);
	  s2 += s1;
     }
     return (s1 & 0xffff) + (s2 << 16);
}


/*
 * Calculate and store into SUM a strong MD4 checksum of the file
 * blocks seen so far.
 *
 * The checksum is perturbed by a seed value.  This is used when
 * retrying a failed transmission: we've discovered that the hashes
 * collided at some point, so we're going to try again with different
 * hashes to see if we can get it right.  (Check tridge's thesis for
 * details and to see if that's correct.)
 *
 * Since we can't retry a web transaction I'm not sure if it's very
 * useful in rproxy.
 */
uint32_t
_hs_calc_strong_sum(byte_t const *buf,
                    size_t len,
		    byte_t *sum,
                    size_t sum_len)
{
     hs_mdfour_t m;
     byte_t tsum[MD4_LENGTH];

     hs_mdfour_begin(&m);
     hs_mdfour_update(&m, buf, len);
     hs_mdfour_result(&m, tsum);

     memcpy(sum, tsum, sum_len);

     return 0;
}



