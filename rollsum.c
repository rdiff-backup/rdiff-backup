/*				       	-*- c-file-style: "bsd" -*-
 * rproxy -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 1999, 2000 by Martin Pool
 * Copyright (C) 1999 by Andrew Tridgell
 * 
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */


#include "includes.h"




void
_hs_roll_reset(hs_rollsum_t * rollsum)
{
    hs_bzero(rollsum, sizeof *rollsum);
}


int
_hs_stretch_sums(byte_t const *bytep, size_t full_block,
		size_t short_block, hs_rollsum_t * rollsum)
{
    /* Checksum calculations are signed */
    int8_t const     *p = (int8_t const *) bytep;
    
    if (!rollsum->havesum) {
	rollsum->weak_sum = _hs_calc_weak_sum(p, short_block);
	_hs_trace("recalculate checksum: weak=%#x", rollsum->weak_sum);
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
_hs_trim_sums(byte_t const *bytep, hs_rollsum_t * rollsum, size_t short_block)
{
    /* Checksum calculations are signed */
    int8_t const     *p = (int8_t const *) bytep;
    
    rollsum->s1 -= *p + CHAR_OFFSET;
    rollsum->s2 -= short_block * (*p + CHAR_OFFSET);

    return 0;
}
