/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- the library for network deltas
 * $Id$
 * 
 * Copyright (C) 1999, 2000, 2001 by Martin Pool <mbp@samba.org>
 * Copyright (C) 1999 by Andrew Tridgell
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


#include "config.h"

#include <assert.h>
#include <stdlib.h>
#include <stdio.h>

#include "rsync.h"





void
rs_roll_reset(rs_rollsum_t * rollsum)
{
    rs_bzero(rollsum, sizeof *rollsum);
}


int
rs_stretch_sums(byte_t const *bytep, size_t full_block,
		size_t short_block, rs_rollsum_t * rollsum)
{
    /* Checksum calculations are signed */
    int8_t const     *p = (int8_t const *) bytep;
    
    if (!rollsum->havesum) {
	rollsum->weak_sum = rs_calc_weak_sum(p, short_block);
	rs_trace("recalculate checksum: weak=%#x", rollsum->weak_sum);
	rollsum->s1 = rollsum->weak_sum & 0xFFFF;
	rollsum->s2 = rollsum->weak_sum >> 16;
    } else {
	/* Add into the checksum the value of the byte one block hence.
	   However, if that byte doesn't exist because we're approaching the
	   end of the file, don't add it. */
	if (short_block == full_block) {
	    int             pos = short_block - 1;

	    assert(pos >= 0);
	    rollsum->s1 += (p[pos] + CHAR_OFFSET);
	    rollsum->s2 += rollsum->s1;
	}

	rollsum->weak_sum = (rollsum->s1 & 0xffff) | (rollsum->s2 << 16);
    }

    rollsum->havesum = 1;

    return 0;
}


/* One byte rolls off the checksum. */
int
rs_trim_sums(byte_t const *bytep, rs_rollsum_t * rollsum, size_t short_block)
{
    /* Checksum calculations are signed */
    int8_t const     *p = (int8_t const *) bytep;
    
    rollsum->s1 -= *p + CHAR_OFFSET;
    rollsum->s2 -= short_block * (*p + CHAR_OFFSET);

    return 0;
}
