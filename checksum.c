/* -*- mode: c; c-file-style: "k&r" -*-  */

/* checksum.c -- calculate and search table of checksums
   
   Copyright (C) 2000 by Martin Pool
   Copyright (C) Andrew Tridgell 1996
   Copyright (C) Paul Mackerras 1996

   This program is free software; you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation; either version 2 of the License, or
   (at your option) any later version.
   
   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.
   
   You should have received a copy of the GNU General Public License
   along with this program; if not, write to the Free Software
   Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
*/

#include "includes.h"
#include "hsync.h"
#include "private.h"

int checksum_seed = 0;

/*
  a simple 32 bit checksum that can be upadted from either end
  (inspired by Mark Adler's Adler-32 checksum)
  */
uint32_t _hs_calc_weak_sum(char const *buf1, int len)
{
     int i;
     uint32_t s1, s2;
     int8_t *buf = (uint8_t *) buf1;	/* this is signed */

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


/* Calculate and store into SUM a strong MD4 checksum of the file
   blocks seen so far. 

   The checksum is perturbed by a seed value.  This is used when
   retrying a failed transmission: we've discovered that the hashes
   collided at some point, so we're going to try again with different
   hashes to see if we can get it right.  (Check tridge's thesis for
   details and to see if that's correct.)

   Since we can't retry a web transaction I'm not sure if it's very
   useful in rproxy. */
uint32_t
_hs_calc_strong_sum(char const *buf, int len, char *sum)
{
     hs_mdfour_t m;
     char tsum[MD4_LENGTH];

     hs_mdfour_begin(&m);
     hs_mdfour_update(&m, (char *) buf, len);
     hs_mdfour_result(&m, (char *) tsum);

     memcpy(sum, tsum, SUM_LENGTH);

     return 0;
}



/* Read all signatures into a newly-allocated sum_struct.

   The signature stream contains pair of short (4-byte) weak checksums, and
   long (SUM_LENGTH) strong checksums. */
int
_hs_make_sum_struct(struct sum_struct **signatures,
		    hs_read_fn_t sigread_fn, void *sigreadprivate,
		    int block_len)
{
     struct sum_buf *asignature;
     int index = 0;
     int ret = 0;
     int checksum1;
     struct sum_struct *sumbuf;

     sumbuf = *signatures = calloc(1, sizeof(struct sum_struct));
     if (!sumbuf) {
	  errno = ENOMEM;
	  return -1;
     }
     sumbuf->n = block_len;

     sumbuf->sums = NULL;
     /* XXX: It's perhaps a bit inefficient to realloc each time.
	We could prealloc, but for now we'll give realloc the
	benefit of the doubt. */

     while (1) {
	  ret = _hs_read_netint(sigread_fn, sigreadprivate, &checksum1);

	  if (ret == 0)
	       break;
	  if (ret < 0) {
	       _hs_error("IO error while reading in signatures");
	       return -1;
	  }
	  assert(ret == 4);
	 
	  sumbuf->sums =
	       realloc(sumbuf->sums, (index + 1) * sizeof(struct sum_buf));
	  if (sumbuf->sums == NULL) {
	       errno = ENOMEM;
	       ret = -1;
	       break;
	  }
	  asignature = &(sumbuf->sums[index]);
	 
	  asignature->sum1 = checksum1;
	  asignature->i = ++index;
	 
	  /* read in the long sum */
	  ret = _hs_must_read(sigread_fn, sigreadprivate, asignature->strong_sum, SUM_LENGTH);
	  if (ret != SUM_LENGTH) {
	       _hs_error("IO error while reading strong signature %d",
			 index);
	       break;
	  }
     }
     if (ret < 0) {
	  /* error reading */
	  return ret;
     }

     sumbuf->count = index;
     _hs_trace("Read %d sigs", index);

     ret = _hs_build_hash_table(*signatures) < 0;

     return ret;
}


void _hs_free_sum_struct(struct sum_struct **psums)
{
     struct sum_struct *sums = *psums;

     free(sums->sums);
     /* XXX: I don't understand why we *don't* have to free this --
	wasn't it allocated in make_sum_struct? -- mbp/20000125 */
     //_hs_free(s, sums);
     *psums = 0;
}
