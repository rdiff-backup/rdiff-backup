/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- the library for network deltas
 * $Id$
 * 
 * Copyright (C) 2000, 2001 by Martin Pool <mbp@samba.org>
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


#include <config.h>

#include <stdlib.h>
#include <assert.h>
#include <stdio.h>

#include "rsync.h"
#include "stream.h"
#include "util.h"
#include "sumset.h"
#include "job.h"
#include "trace.h"


static const int rs_job_tag = 20010225;


rs_job_t * rs_job_new(rs_stream_t *stream, char const *job_name)
{
    rs_job_t *job;

    job = rs_alloc_struct(rs_job_t);

    rs_stream_check(stream);
    job->stream = stream;
    job->job_name = job_name;
    job->dogtag = rs_job_tag;

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
    rs_bzero(job, sizeof *job);
    free(job);

    return HS_DONE;
}



static rs_result rs_job_s_complete(rs_job_t *job)
{
    rs_fatal("should not be reached");
}


static rs_result rs_job_complete(rs_job_t *job, rs_result result)
{
    rs_job_check(job);
    
    job->statefn = rs_job_s_complete;
    job->final_result = result;

    if (result != HS_DONE) {
        rs_error("%s job failed: %s", job->job_name, rs_strerror(result));
    } else {
        rs_trace("%s job complete", job->job_name);
    }

    if (result == HS_DONE && !rs_tube_is_idle(job->stream))
        return HS_BLOCKED;
    else
        return result;
}


/** 
 * \brief Run a ::rs_job_t state machine until it blocks
 * (::HS_BLOCKED), returns an error, or completes (::HS_COMPLETE).
 *
 * \return The ::rs_result that caused iteration to stop.
 *
 * \param ending True if there is no more data after what's in the
 * input buffer.  The final block checksum will run across whatever's
 * in there, without trying to accumulate anything else.
 */
rs_result rs_job_iter(rs_job_t *job)
{
    rs_result result;

    rs_job_check(job);
    while (1) {
        result = rs_tube_catchup(job->stream);
        if (result == HS_BLOCKED)
            return result;
        else if (result != HS_DONE)
            return rs_job_complete(job, result);

        if (job->statefn == rs_job_s_complete) {
            if (rs_tube_is_idle(job->stream))
                return HS_DONE;
            else
                return HS_BLOCKED;
        } else {
            result = job->statefn(job);
            if (result == HS_RUNNING)
                continue;
            else if (result == HS_BLOCKED)
                return result;
            else
                return rs_job_complete(job, result);
        }
    }
}


/**
 * Return pointer to statistics accumulated about this job.
 */
const rs_stats_t *
rs_job_statistics(rs_job_t *job)
{
    return &job->stats;
}
