/*				       	-*- c-file-style: "linux" -*-
 *
 * libhsync -- library for network deltas
 * $Id$
 * 
 * Copyright (C) 1999, 2000 by Martin Pool <mbp@linuxcare.com.au>
 * Copyright (C) 1999 by Andrew Tridgell <tridge@samba.org>
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
 * mksum: Generate and write out checksums using the stream interface.
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
#include "trace.h"
#include "checksum.h"

const int       HS_MKSUM_TAG = 123124;

struct hs_mksum_job {
        int          dogtag;
	hs_stream_t *stream;
        enum hs_result (*statefn)(hs_mksum_job_t *);
        size_t          block_len;
        size_t          strong_sum_len;
        int             near_end;
};


/* Possible state functions for signature generation. */
static enum hs_result _hs_mksum_s_header(hs_mksum_job_t *);
static enum hs_result _hs_mksum_s_complete(hs_mksum_job_t *);
static enum hs_result _hs_mksum_s_generate(hs_mksum_job_t *);


                                           
/*
 * State of trying to send the signature header.
 */
static enum hs_result _hs_mksum_s_header(hs_mksum_job_t *job)
{
        _hs_squirt_n32(job->stream, HS_SIG_MAGIC);
        job->statefn = _hs_mksum_s_generate;

        return HS_RUN_OK;
}


static enum hs_result
_hs_mksum_do_block(hs_mksum_job_t *job, const void *block, size_t len)
{
        uint32_t weak_sum;

        weak_sum = _hs_calc_weak_sum(block, len);
        _hs_trace("got weak sum 0x%08x", weak_sum);

        _hs_squirt_n32(job->stream, weak_sum);

        return HS_RUN_OK;
}


/*
 * State of reading a block and trying to generate its sum.
 */
static enum hs_result _hs_mksum_s_generate(hs_mksum_job_t *job)
{
        enum hs_result result;
        int len;
        void *block;
        
        /* must get a whole block, otherwise try again */
        len = job->block_len;
        result = _hs_scoop_read(job->stream, len, &block);
        
        /* unless we're near eof, in which case we'll accept
         * whatever's in there */
        if (result == HS_BLOCKED && job->near_end) {
                result = _hs_scoop_read_rest(job->stream, &len, &block);
                job->statefn = _hs_mksum_s_complete;
        } else if (result != HS_OK) {
                _hs_trace("generate stopped: %s", hs_strerror(result));
                return result;
        }

        _hs_trace("got %d byte block", len);
        fwrite(block, 1, len, stdout);

        return _hs_mksum_do_block(job, block, len);
}


static enum hs_result _hs_mksum_s_complete(hs_mksum_job_t *UNUSED(job))
{
        _hs_trace("signature generation has already finished");

        return HS_OK;
}


/* Set up a new encoding job. */
hs_mksum_job_t * hs_mksum_begin(hs_stream_t *stream,
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
 *
 * ENDING should be true if there is no more data after what's in the
 * input buffer.  The final block checksum will run across whatever's
 * in there, without trying to accumulate anything else.
 */
int hs_mksum_iter(hs_mksum_job_t *job, int ending)
{
        enum hs_result result;

        assert(job->dogtag == HS_MKSUM_TAG);

        if (ending)
                job->near_end = 1;

        while (1) {
                result = _hs_tube_catchup(job->stream);
                if (result != HS_OK)
                        return result;
                
                result = job->statefn(job);
                if (result != HS_RUN_OK)
                        return result;
        } 
}
