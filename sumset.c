/*				       	-*- c-file-style: "linux" -*-
 *
 * libhsync -- library for network deltas
 * $Id$
 * 
 * Copyright (C) 1999, 2000, 2001 by Martin Pool <mbp@linuxcare.com.au>
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

#include <config.h>

#include <assert.h>

#ifdef HAVE_STDINT_H
#include <stdint.h>
#endif

#include <sys/types.h>
#include <limits.h>
#include <inttypes.h>
#include <stdlib.h>
#include <syslog.h>

#include "hsync.h"
#include "sumset.h"
#include "util.h"
#include "trace.h"

void
hs_free_sumset(hs_sumset_t * psums)
{
        if (psums->block_sums)
                free(psums->block_sums);

        assert(psums->tag_table);
        free(psums->tag_table);

        if (psums->targets)
                free(psums->targets);

        hs_bzero(psums, sizeof *psums);
        free(psums);
}



void
hs_sumset_dump(hs_sumset_t const *sums)
{
        int i;
        char        strong_hex[HS_MD4_LENGTH * 3];
    
        hs_log(LOG_INFO, 
                "sumset info: block_len=%d, file length=%lu, "
                "number of chunks=%d, remainder=%d",
                sums->block_len,
                (unsigned long) sums->flength, sums->count,
                sums->remainder);

        for (i = 0; i < sums->count; i++) {
                hs_hexify(strong_hex, sums->block_sums[i].strong_sum,
                          sums->strong_sum_len);
                hs_log(LOG_INFO,
                        "sum %6d: weak=%08x, strong=%s",
                        i, sums->block_sums[i].weak_sum, strong_hex);
        }
}



