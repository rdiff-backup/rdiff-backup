/*=                                     -*- c-file-style: "linux" -*-
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



/*
 * Generate a delta from a set of signatures and a new file.
 */

/*
 * Eventually, the delta algorithm has to maintain one block of
 * readahead or readbehind to check the strong checksum.
 *
 * On each entry to the iterator, we first need to try to flush any
 * outstanding output from either the tube or a copy instruction.
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
#include "job.h"


static hs_result hs_delta_s_fake(hs_job_t *job)
{
        hs_stream_t * const stream = job->stream;
        size_t avail = stream->avail_in;
        
	hs_emit_literal_cmd(stream, avail);
	hs_blow_copy(stream, avail);

	if (hs_stream_is_empty(stream))
		return HS_OK;
	else
		return HS_BLOCKED;
}


static hs_result hs_delta_s_header(hs_job_t *job)
{
	hs_emit_delta_header(job->stream);

        job->statefn = hs_delta_s_fake;

        return HS_OK;
}


/*
 * Prepare to compute a delta on a stream.
 */
hs_job_t *hs_delta_begin(hs_stream_t *stream)
{
	hs_job_t *job;

	job = hs_job_new(stream);

        job->statefn = hs_delta_s_header;
	
	return job;
}


