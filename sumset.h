/*=				       	-*- c-file-style: "linux" -*-
 * rproxy -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 1999, 2000 by Martin Pool <mbp@linuxcare.com.au>
 * Copyright (C) 1999 by Andrew Tridgell <tridge@linuxcare.com.au>
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

#define DEFAULT_SUM_LENGTH 8

/* We should make this something other than zero to improve the checksum
   algorithm: tridge suggests a prime number. */
#define CHAR_OFFSET 31

typedef uint32_t hs_weak_sum_t;
typedef unsigned char hs_strong_sum_t[HS_MD4_LENGTH];

typedef struct hs_rollsum hs_rollsum_t;


struct hs_target {
    short           t;
    int             i;
};


/* TODO: Include length of strong checksums in case it varies between
 * files. */

typedef struct hs_sum_buf hs_sum_buf_t;

/*
 * This structure describes all the sums generated for an instance of
 * a file.  It incorporates some redundancy to make it easier to
 * search.
 */
struct hs_sumset {
    off_t        flength;	/* total file length */
    int             count;	/* how many chunks */
    int             remainder;	/* flength % block_length */
    int             block_len;	/* block_length */
    hs_sum_buf_t   *block_sums; /* points to info for each chunk */
    int            *tag_table;
    struct target  *targets;
};


/*
 * All blocks are the same length in the current algorithm except for
 * the last block which may be short.
 */
struct hs_sum_buf {
    int             i;		/* index of this chunk */
    hs_weak_sum_t   weak_sum;	/* simple checksum */
    hs_strong_sum_t strong_sum;	/* checksum  */
};
