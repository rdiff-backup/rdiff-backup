/*				       	-*- c-file-style: "linux" -*-
 *
 * libhsync -- library for network deltas
 * $Id$
 * 
 * Copyright (C) 1999, 2000 by Martin Pool <mbp@linuxcare.com.au>
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


/* 
 * Generate a checksum set, using the newstyle nonblocking
 * arrangement and mapptrs.
 */

#include "config.h"

#include <stdlib.h>
#include <stdio.h>
#include <assert.h>
#include <stdint.h>

#include "hsync.h"
#include "stream.h"
#include "util.h"
#include "protocol.h"
#include "netint.h"


const int       HS_MKSUM_TAG = 123124;

struct hs_mksum_job {
    hs_stream_t    *stream;
    int             dogtag;
    size_t          block_len;
    hs_stats_t      stats;
    size_t          strong_sum_len;

        int             (*statefn)(hs_mksum_job_t *);
};


/*
 * State of trying to send the signature header.
 */
static int _hs_mksum_s_header(hs_mksum_job_t *job)
{
        _hs_squirt_n32(job->stream, HS_SIG_MAGIC);

        return HS_OK;
}


/* Set up a new encoding job. */
hs_mksum_job_t *
hs_mksum_begin(hs_stream_t *stream,
	       size_t new_block_len, size_t strong_sum_len)
{
    hs_mksum_job_t *job;

    job = _hs_alloc_struct(hs_mksum_job_t);

    _hs_stream_check(stream);
    job->stream = stream;
    job->block_len = new_block_len;
    job->dogtag = HS_MKSUM_TAG;

    assert(strong_sum_len > 0 && strong_sum_len <= HS_MD4_LENGTH);
    job->strong_sum_len = strong_sum_len;

    job->statefn = _hs_mksum_s_header;

    return job;
}



int hs_mksum_finish(hs_mksum_job_t * job)
{
        assert(job->dogtag == HS_MKSUM_TAG);
        _hs_bzero(job, sizeof *job);
        free(job);

        return HS_OK;
}



/* 
 * Nonblocking iteration interface for making up a file sum. 
 */
int hs_mksum_iter(hs_mksum_job_t *job, int ending)
{
        int result;

        assert(job->dogtag == HS_MKSUM_TAG);

        do {
                result = _hs_tube_catchup(job->stream);
                if (result != HS_OK)
                        return result;
                
                result = job->statefn(job);
        } while (result == HS_OK);

        return result;
}
