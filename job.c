/*=                                     -*- c-file-style: "linux" -*-
 *
 * libhsync -- the library for network deltas
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
                               * The hard, lifeless I covered up the
                               * warm, pulsing It; protecting and
                               * sheltering.
                               */


/*
 * Generic state-machine "job" mechanism.
 */


#include <config.h>

#include <stdlib.h>
#include <assert.h>

#include "hsync.h"
#include "stream.h"
#include "util.h"
#include "job.h"
#include "trace.h"


hs_job_t * hs_job_new(hs_stream_t *stream)
{
        hs_job_t *job;

        job = hs_alloc_struct(hs_job_t);

        hs_stream_check(stream);
        job->stream = stream;

        return job;
}


hs_result hs_job_free(hs_job_t *job)
{
        hs_bzero(job, sizeof *job);
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
hs_result hs_job_iter(hs_job_t *job, int ending)
{
        enum hs_result result;

        if (ending)
                job->near_end = 1;

        while (1) {
                result = hs_tube_catchup(job->stream);
                if (result != HS_OK)
                        return result;
                
                result = job->statefn(job);
                if (result != HS_RUN_OK)
                        return result;
        } 
}


hs_result hs_job_s_complete(hs_job_t *UNUSED(job))
{
        hs_trace("job has finished");

        return HS_OK;
}


