/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- library for network deltas
 * $Id$
 * 
 * Copyright (C) 1999, 2000, 2001 by Martin Pool <mbp@samba.org>
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
 * Generating checksums is pretty easy, since we can always just
 * process whatever data is available.  When a whole block has
 * arrived, or we've reached the end of the file, we write the
 * checksum out.
 */

#include <config.h>

#include <stdlib.h>
#include <stdio.h>
#include <assert.h>

#include "rsync.h"
#include "stream.h"
#include "util.h"
#include "sumset.h"
#include "job.h"
#include "protocol.h"
#include "netint.h"
#include "trace.h"
#include "checksum.h"


/* Possible state functions for signature generation. */
static rs_result rs_sig_s_header(rs_job_t *);
static rs_result rs_sig_s_generate(rs_job_t *);


                                           
/**
 * State of trying to send the signature header.
 */
static rs_result rs_sig_s_header(rs_job_t *job)
{
    rs_squirt_n4(job->stream, HS_SIG_MAGIC);
    rs_squirt_n4(job->stream, job->block_len);
    rs_squirt_n4(job->stream, job->strong_sum_len);
    rs_trace("sent header (magic %#x, block len = %d, strong sum len = %d)",
             HS_SIG_MAGIC, (int) job->block_len, (int) job->strong_sum_len);
    
    job->statefn = rs_sig_s_generate;
    return HS_RUNNING;
}


static rs_result
rs_sig_do_block(rs_job_t *job, const void *block, size_t len)
{
    unsigned int        weak_sum;
    rs_strong_sum_t     strong_sum;
    char strong_sum_hex[HS_MD4_LENGTH * 2 + 1];

    weak_sum = rs_calc_weak_sum(block, len);

    rs_calc_strong_sum(block, len, &strong_sum);
    rs_hexify(strong_sum_hex, strong_sum, job->strong_sum_len);

    rs_squirt_n4(job->stream, weak_sum);
    rs_blow_literal(job->stream, strong_sum, job->strong_sum_len);

    rs_trace("sent weak sum 0x%08x and strong sum %s", weak_sum,
             strong_sum_hex);

    return HS_RUNNING;
}


/*
 * State of reading a block and trying to generate its sum.
 */
static rs_result rs_sig_s_generate(rs_job_t *job)
{
    rs_result           result;
    size_t              len;
    void                *block;
        
    /* must get a whole block, otherwise try again */
    len = job->block_len;
    result = rs_scoop_read(job->stream, len, &block);
        
    /* unless we're near eof, in which case we'll accept
         * whatever's in there */
    if ((result == HS_BLOCKED && job->stream->eof_in)) {
        result = rs_scoop_read_rest(job->stream, &len, &block);
    } else if (result == HS_INPUT_ENDED) {
        return HS_DONE;
    } else if (result != HS_DONE) {
        rs_trace("generate stopped: %s", rs_strerror(result));
        return result;
    }

    rs_trace("got %d byte block", len);

    return rs_sig_do_block(job, block, len);
}


/** \brief Set up a new encoding job.
 *
 * \sa rs_sig_file()
 */
rs_job_t * rs_sig_begin(rs_stream_t *stream,
                        size_t new_block_len, size_t strong_sum_len)
{
    rs_job_t *job;

    job = rs_job_new(stream, "signature");

    job->block_len = new_block_len;

    assert(strong_sum_len > 0 && strong_sum_len <= HS_MD4_LENGTH);
    job->strong_sum_len = strong_sum_len;

    job->statefn = rs_sig_s_header;

    return job;
}


