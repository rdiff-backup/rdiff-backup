/*=                                     -*- c-file-style: "linux" -*-
 *
 * libhsync -- library for network deltas
 * $Id$
 *
 * Copyright (C) 2000 by Martin Pool <mbp@linuxcare.com.au>
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
 * readahead or readbehind to check the strong checksum.  Normally we
 * don't have to actually do anything with this data, just keep it.
 *
 * Probably a reasonable way to implement this is with a double-long
 * buffer and data scrolling through that.  When a weak match is found,
 * we check the strong checksum against the readbehind buffer.
 *
 * On each entry to the iterator, we first need to try to flush any
 * outstanding output from either the tube or a copy instruction.
 */


#include "config.h"

#include <assert.h>

#ifdef HAVE_STDINT_H
#include <stdint.h>
#endif

#include <sys/types.h>
#include <limits.h>
#include <inttypes.h>
#include <stdlib.h>
#include <stdio.h>

#include "hsync.h"
#include "emit.h"
#include "stream.h"
#include "util.h"


enum hs_delta_state {
        hs_s_header,
        hs_body
};

struct hs_delta_job {
	hs_stream_t *stream;
};


/*
 * Prepare to compute a delta on a stream.
 */
hs_delta_job_t *hs_delta_begin(hs_stream_t *stream)
{
	hs_delta_job_t *job;

	job = _hs_alloc_struct(hs_delta_job_t);
	job->stream = stream;
	
	_hs_emit_delta_header(stream);
	
	return job;
}


/*
 * Consume and produce data to generate a delta.
 */
int hs_delta_iter(hs_delta_job_t *job, int ending)
{
	int avail;
        hs_stream_t * const stream = job->stream;

	/* Find out how much input is available.  Write it out as one big
	 * command, and remove it from the input stream. */
	if (!_hs_tube_catchup(stream))
		return HS_OK;

	avail = stream->avail_in;
	_hs_emit_literal_cmd(stream, avail);
	_hs_blow_copy(stream, avail);

	if (_hs_stream_is_empty(stream))
		return HS_OK;
	else
		return HS_BLOCKED;
}



/*
 * Close of processing of a delta.  This doesn't terminate the stream,
 * it just frees up any memory that was allocated.
 */
int hs_delta_finish(hs_delta_job_t *job)
{
        _hs_bzero(job, sizeof *job);

        free(job);

        return HS_OK;
}
