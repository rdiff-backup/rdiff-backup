/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 * rproxy -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool <mbp@samba.org>
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



/* ROLLSUM_T contains the checksums that roll through the new version of the
   file as we see it.  We use this for two different things: searching for
   matches in the old version of the file, and also generating new-signature
   information to send down to the client.  */
struct hs_rollsum {
    int             havesum;	/* false if we've skipped & need to
				   recalculate */
    uint32_t        weak_sum, s1, s2;	/* weak checksum */
};

/* Define this to check all weak checksums the slow way.  As a debuggging
   assertion, calculate the weak checksum *in full* at every byte, and make
   sure it is the same.  This will be really slow, but it will catch problems 
   with rolling. */
#define HS_PAINFUL_HONESTY


int hs_trim_sums(byte_t const *p, hs_rollsum_t * rollsum,
                  size_t short_block);

int hs_stretch_sums(byte_t const *p, size_t full_block,
                     size_t short_block, hs_rollsum_t * rollsum);

void hs_roll_reset(hs_rollsum_t * rollsum);
