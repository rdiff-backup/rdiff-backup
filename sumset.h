/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * libhsync -- the library for network deltas
 * $Id$
 * 
 * Copyright (C) 1999, 2000, 2001 by Martin Pool <mbp@samba.org>
 * Copyright (C) 1999 by Andrew Tridgell <mbp@samba.org>
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

typedef uint32_t hs_weak_sum_t;
typedef unsigned char hs_strong_sum_t[HS_MD4_LENGTH];

typedef struct hs_rollsum hs_rollsum_t;


typedef struct hs_target {
    short           t;
    int             i;
} hs_target_t;

typedef struct hs_sum_buf hs_sum_buf_t;

/*
 * This structure describes all the sums generated for an instance of
 * a file.  It incorporates some redundancy to make it easier to
 * search.
 */
struct hs_sumset {
        off_t           flength;	/* total file length */
        int             count;          /* how many chunks */
        int             remainder;	/* flength % block_length */
        int             block_len;	/* block_length */
        int             strong_sum_len;
        hs_sum_buf_t   *block_sums;     /* points to info for each chunk */
        int            *tag_table;
        hs_target_t    *targets;
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
