/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- library for network deltas
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


/*
 * delta.c -- Generate in streaming mode an rsync delta given a set of
 * signatures, and a new file.
 *
 * The size of blocks for signature generation is determined by the
 * block size in the incoming signature.
 *
 * To calculate a signature, we need to be able to see at least one
 * block of the new file at a time.  Once we have that, we calculate
 * its weak signature, and see if there is any block in the signature
 * hash table that has the same weak sum.  If there is one, then we
 * also compute the strong sum of the new block, and cross check that.
 * If they're the same, then we can assume we have a match.
 *
 * The final block of the file has to be handled a little differently,
 * because it may be a short match.  Short blocks in the signature
 * don't include their length -- we just allow for the final short
 * block of the file to match any block in the signature, and if they
 * have the same checksum we assume they must have the same length.
 * Therefore, when we emit a COPY command, we have to send it with a
 * length that is the same as the block matched, and not the block
 * length from the signature.
 */


#include <config.h>

#include <assert.h>
#include <stdlib.h>
#include <stdio.h>

#include "rsync.h"
#include "emit.h"
#include "stream.h"
#include "util.h"
#include "sumset.h"
#include "job.h"
#include "trace.h"


static rs_result rs_delta_s_end(rs_job_t *job)
{
    rs_emit_end_cmd(job);
    return HS_DONE;
}


/**
 * \brief State function that does a fake delta containing only
 * literal data to recreate the input.
 */
static rs_result rs_delta_s_fake(rs_job_t *job)
{
    rs_stream_t * const stream = job->stream;
    size_t avail = stream->avail_in;

    if (avail) {
        rs_trace("emit fake delta for %ld available bytes", (long) avail);
        rs_emit_literal_cmd(job, avail);
        rs_blow_copy(stream, avail);
        return HS_RUNNING;
    } else {
        if (stream->eof_in) {
            job->statefn = rs_delta_s_end;
            return HS_RUNNING;
        } else {                
            return HS_BLOCKED;
        }
    }
}


/**
 * State function for writing out the header of the encoding job.
 */
static rs_result rs_delta_s_header(rs_job_t *job)
{
    rs_emit_delta_header(job);

    job->statefn = rs_delta_s_fake;

    return HS_RUNNING;
}


/**
 * Prepare to compute a delta on a stream.
 */
rs_job_t *rs_delta_begin(rs_stream_t *stream, rs_signature_t *sig)
{
    rs_job_t *job;

    job = rs_job_new(stream, "delta");
    
    job->signature = sig;
    job->statefn = rs_delta_s_header;
	
    return job;
}


