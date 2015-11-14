/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- the library for network deltas
 * $Id$
 * 
 * Copyright (C) 2000, 2001 by Martin Pool <mbp@sourcefrog.net>
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


                              /*
                               | The hard, lifeless I covered up the
                               | warm, pulsing It; protecting and
                               | sheltering.
                               */

/*
 * job.c -- Generic state-machine interface.  The point of this is
 * that we need to be able to suspend and resume processing at any
 * point at which the buffers may block.  We could do that using
 * setjmp or similar tricks, but this is probably simpler.
 *
 * TODO: We have a few functions to do with reading a netint, stashing
 * it somewhere, then moving into a different state.  Is it worth
 * writing generic functions fo r that, or would it be too confusing?
 */


#include "config.h"

#include <stdlib.h>
#include <assert.h>
#include <stdio.h>

#include "librsync.h"
#include "stream.h"
#include "util.h"
#include "sumset.h"
#include "job.h"
#include "trace.h"


static const int rs_job_tag = 20010225;

static rs_result rs_job_work(rs_job_t *job, rs_buffers_t *buffers);


rs_job_t * rs_job_new(char const *job_name, rs_result (*statefn)(rs_job_t *))
{
    rs_job_t *job;

    job = rs_alloc_struct(rs_job_t);

    job->job_name = job_name;
    job->dogtag = rs_job_tag;
    job->statefn = statefn;

    job->stats.op = job_name;

    rs_trace("start %s job", job_name);

    return job;
}


void rs_job_check(rs_job_t *job)
{
    assert(job->dogtag == rs_job_tag);
}


rs_result rs_job_free(rs_job_t *job)
{
    if (job->scoop_buf)
            free(job->scoop_buf);

    rs_bzero(job, sizeof *job);
    free(job);

    return RS_DONE;
}



static rs_result rs_job_s_complete(rs_job_t *job)
{
    rs_fatal("should not be reached");
    return RS_INTERNAL_ERROR;
}


static rs_result rs_job_complete(rs_job_t *job, rs_result result)
{
    rs_job_check(job);
    
    job->statefn = rs_job_s_complete;
    job->final_result = result;

    if (result != RS_DONE) {
        rs_error("%s job failed: %s", job->job_name, rs_strerror(result));
    } else {
        rs_trace("%s job complete", job->job_name);
    }

    if (result == RS_DONE && !rs_tube_is_idle(job))
        /* Processing is finished, but there is still some data
         * waiting to get into the output buffer. */
        return RS_BLOCKED;
    else
        return result;
}


/** 
 * \brief Run a ::rs_job_t state machine until it blocks
 * (::RS_BLOCKED), returns an error, or completes (::RS_COMPLETE).
 *
 * \return The ::rs_result that caused iteration to stop.
 *
 * \param ending True if there is no more data after what's in the
 * input buffer.  The final block checksum will run across whatever's
 * in there, without trying to accumulate anything else.
 */
rs_result rs_job_iter(rs_job_t *job, rs_buffers_t *buffers)
{
    rs_result       result;
    rs_long_t       orig_in, orig_out;

    orig_in  = buffers->avail_in;
    orig_out = buffers->avail_out;

    result = rs_job_work(job, buffers);

    if (result == RS_BLOCKED  ||  result == RS_DONE) 
        if ((orig_in == buffers->avail_in)  &&  (orig_out == buffers->avail_out)
            && orig_in && orig_out) {
            rs_log(RS_LOG_ERR, "internal error: job made no progress "
                   "[orig_in=" PRINTF_FORMAT_U64 ", orig_out=" PRINTF_FORMAT_U64 ", final_in=" PRINTF_FORMAT_U64 ", final_out=" PRINTF_FORMAT_U64 "]",
                   PRINTF_CAST_U64(orig_in), PRINTF_CAST_U64(orig_out), PRINTF_CAST_U64(buffers->avail_in),
                   PRINTF_CAST_U64(buffers->avail_out));
            return RS_INTERNAL_ERROR;
        }

    return result;
}


static rs_result
rs_job_work(rs_job_t *job, rs_buffers_t *buffers)
{
    rs_result result;

    rs_job_check(job);

    if (!buffers) {
        rs_error("NULL buffer passed to rs_job_iter");
        return RS_PARAM_ERROR;
    }
    job->stream = buffers;
    
    while (1) {
        result = rs_tube_catchup(job);
        if (result == RS_BLOCKED)
            return result;
        else if (result != RS_DONE)
            return rs_job_complete(job, result);

        if (job->statefn == rs_job_s_complete) {
            if (rs_tube_is_idle(job))
                return RS_DONE;
            else
                return RS_BLOCKED;
        } else {
            result = job->statefn(job);
            if (result == RS_RUNNING)
                continue;
            else if (result == RS_BLOCKED)
                return result;
            else
                return rs_job_complete(job, result);
        }
    }

    /* TODO: Before returning, check that we actually made some
     * progress.  If not, and we're not returning an error, this is a
     * bug. */
}


/**
 * \brief Return pointer to statistics accumulated about this job.
 */
const rs_stats_t *
rs_job_statistics(rs_job_t *job)
{
    return &job->stats;
}


int
rs_job_input_is_ending(rs_job_t *job)
{
    return job->stream->eof_in;
}



/**
 * Actively process a job, by making callbacks to fill and empty the
 * buffers until the job is done.
 */
rs_result
rs_job_drive(rs_job_t *job, rs_buffers_t *buf,
             rs_driven_cb in_cb, void *in_opaque,
             rs_driven_cb out_cb, void *out_opaque)
{
    rs_result       result, iores;

    rs_bzero(buf, sizeof *buf);

    do {
        if (!buf->eof_in && in_cb) {
            iores = in_cb(job, buf, in_opaque);
            if (iores != RS_DONE)
                return iores;
        }

        result = rs_job_iter(job, buf);
        if (result != RS_DONE  &&  result != RS_BLOCKED)
            return result;

        if (out_cb) {
            iores = (out_cb)(job, buf, out_opaque);
            if (iores != RS_DONE)
                return iores;
        }
    } while (result != RS_DONE);

    return result;
}

