/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- the library for network deltas
 *
 * Copyright (C) 1999, 2000, 2001 by Martin Pool <mbp@sourcefrog.net>
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

#include "config.h"

#include <assert.h>
#include <stdlib.h>
#include <stdio.h>

#include "librsync.h"
#include "checksum.h"
#include "rollsum.h"
#include "blake2.h"

/** A simple 32bit checksum that can be incrementally updated. */
rs_weak_sum_t rs_calc_weak_sum(void const *buf, size_t len)
{
    Rollsum sum;

    RollsumInit(&sum);
    RollsumUpdate(&sum, buf, len);
    return RollsumDigest(&sum);
}

/** Calculate and store into SUM a strong MD4 checksum of the file blocks seen
 * so far.
 *
 * In plain rsync, the checksum is perturbed by a seed value. This is used when
 * retrying a failed transmission: we've discovered that the hashes collided at
 * some point, so we're going to try again with different hashes to see if we
 * can get it right. (Check tridge's thesis for details and to see if that's
 * correct.)
 *
 * Since we can't retry a web transaction I'm not sure if it's very useful in
 * rproxy. */
void rs_calc_md4_sum(void const *buf, size_t len, rs_strong_sum_t *sum)
{
    rs_mdfour((unsigned char *)sum, buf, len);
}

void rs_calc_blake2_sum(void const *buf, size_t len, rs_strong_sum_t *sum)
{
    blake2b_state ctx;
    blake2b_init(&ctx, RS_MAX_STRONG_SUM_LENGTH);
    blake2b_update(&ctx, (const uint8_t *)buf, len);
    blake2b_final(&ctx, (uint8_t *)sum, RS_MAX_STRONG_SUM_LENGTH);
}
