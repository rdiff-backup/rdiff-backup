/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * libhsync -- library for network deltas
 * $Id$
 *
 * Copyright (C) 2000, 2001 by Martin Pool <mbp@samba.org>
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
                                 | Let's climb to the TOP of that
                                 | MOUNTAIN and think about STRIP
                                 | MINING!!
                                 */



#include <config.h>

#include <assert.h>

#include <sys/types.h>
#include <limits.h>
#include <inttypes.h>
#include <stdlib.h>
#include <stdio.h>

#include "hsync.h"
#include "emit.h"
#include "stream.h"
#include "util.h"
#include "sumset.h"
#include "job.h"
#include "trace.h"


static hs_result hs_delta_s_end(hs_job_t *job)
{
    hs_emit_end_cmd(job);
    return HS_DONE;
}


/**
 * \brief State function that does a fake delta containing only
 * literal data to recreate the input.
 */
static hs_result hs_delta_s_fake(hs_job_t *job)
{
    hs_stream_t * const stream = job->stream;
    size_t avail = stream->avail_in;

    if (avail) {
        hs_trace("emit fake delta for %d available bytes", avail);
        hs_emit_literal_cmd(job, avail);
        hs_blow_copy(stream, avail);
        return HS_RUNNING;
    } else {
        if (stream->eof_in) {
            job->statefn = hs_delta_s_end;
            return HS_RUNNING;
        } else {                
            return HS_BLOCKED;
        }
    }
}


/**
 * State function for writing out the header of the encoding job.
 */
static hs_result hs_delta_s_header(hs_job_t *job)
{
    hs_emit_delta_header(job);

    job->statefn = hs_delta_s_fake;

    return HS_RUNNING;
}


/**
 * Prepare to compute a delta on a stream.
 */
hs_job_t *hs_delta_begin(hs_stream_t *stream, hs_signature_t *sig)
{
    hs_job_t *job;

    job = hs_job_new(stream, "delta");
    
    job->signature = sig;
    job->statefn = hs_delta_s_header;
	
    return job;
}


