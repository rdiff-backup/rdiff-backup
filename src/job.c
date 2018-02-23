/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- the library for network deltas
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

                              /*=
                               | The hard, lifeless I covered up the
                               | warm, pulsing It; protecting and
                               | sheltering.
                               */

/** \file job.c Generic state-machine interface.
 *
 * The point of this is that we need to be able to suspend and resume
 * processing at any point at which the buffers may block.
 *
 * \sa \ref api_streaming \sa rs_job_iter() \sa ::rs_job */

#include "config.h"

#include <stdlib.h>
#include <assert.h>
#include <stdio.h>
#include <time.h>

#include "librsync.h"
#include "stream.h"
#include "util.h"
#include "sumset.h"
#include "job.h"
#include "trace.h"

static rs_result rs_job_work(rs_job_t *job, rs_buffers_t *buffers);

rs_job_t *rs_job_new(char const *job_name, rs_result (*statefn) (rs_job_t *))
{
    rs_job_t *job;

    job = rs_alloc_struct(rs_job_t);

    job->job_name = job_name;
    job->dogtag = RS_JOB_TAG;
    job->statefn = statefn;

    job->stats.op = job_name;
    job->stats.start = time(NULL);

    rs_trace("start %s job", job_name);

    return job;
}

rs_result rs_job_free(rs_job_t *job)
{
    free(job->scoop_buf);
    if (job->job_owns_sig)
        rs_free_sumset(job->signature);
    rs_bzero(job, sizeof *job);
    free(job);

    return RS_DONE;
}

static rs_result rs_job_complete(rs_job_t *job, rs_result result)
{
    rs_job_check(job);
    assert(result != RS_RUNNING && result != RS_BLOCKED);
    assert(rs_tube_is_idle(job) || result != RS_DONE);

    job->final_result = result;
    job->stats.end = time(NULL);
    if (result != RS_DONE) {
        rs_error("%s job failed: %s", job->job_name, rs_strerror(result));
    } else {
        rs_trace("%s job complete", job->job_name);
    }
    return result;
}

rs_result rs_job_iter(rs_job_t *job, rs_buffers_t *buffers)
{
    rs_result result;
    size_t orig_in, orig_out;

    rs_job_check(job);
    assert(buffers);

    orig_in = buffers->avail_in;
    orig_out = buffers->avail_out;
    result = rs_job_work(job, buffers);
    if (result == RS_BLOCKED || result == RS_DONE)
        if ((orig_in == buffers->avail_in) && (orig_out == buffers->avail_out)
            && orig_in && orig_out) {
            rs_error("internal error: job made no progress " "[orig_in="
                     FMT_SIZE ", orig_out=" FMT_SIZE ", final_in=" FMT_SIZE
                     ", final_out=" FMT_SIZE "]", orig_in, orig_out,
                     buffers->avail_in, buffers->avail_out);
            return RS_INTERNAL_ERROR;
        }
    return result;
}

static rs_result rs_job_work(rs_job_t *job, rs_buffers_t *buffers)
{
    rs_result result;

    rs_job_check(job);
    assert(buffers);

    job->stream = buffers;
    while (1) {
        result = rs_tube_catchup(job);
        if (result == RS_DONE && job->statefn) {
            result = job->statefn(job);
            if (result == RS_DONE) {
                /* The job is done so clear statefn. */
                job->statefn = NULL;
                /* There might be stuff in the tube, so keep running. */
                continue;
            }
        }
        if (result == RS_BLOCKED)
            return result;
        if (result != RS_RUNNING)
            return rs_job_complete(job, result);
    }
}

const rs_stats_t *rs_job_statistics(rs_job_t *job)
{
    return &job->stats;
}

int rs_job_input_is_ending(rs_job_t *job)
{
    return job->stream->eof_in;
}

rs_result rs_job_drive(rs_job_t *job, rs_buffers_t *buf, rs_driven_cb in_cb,
                       void *in_opaque, rs_driven_cb out_cb, void *out_opaque)
{
    rs_result result, iores;

    rs_bzero(buf, sizeof *buf);

    do {
        if (!buf->eof_in && in_cb) {
            iores = in_cb(job, buf, in_opaque);
            if (iores != RS_DONE)
                return iores;
        }

        result = rs_job_iter(job, buf);
        if (result != RS_DONE && result != RS_BLOCKED)
            return result;

        if (out_cb) {
            iores = (out_cb) (job, buf, out_opaque);
            if (iores != RS_DONE)
                return iores;
        }
    } while (result != RS_DONE);

    return result;
}
