/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- dynamic caching and delta update in HTTP
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
                               | Where a calculator on the ENIAC is
                               | equpped with 18,000 vaccuum tubes and
                               | weighs 30 tons, computers in the
                               | future may have only 1,000 vaccuum
                               | tubes and perhaps weigh 1 1/2
                               | tons.
                               |   -- Popular Mechanics, March 1949
                               */


/* tube: a somewhat elastic but fairly small buffer for data passing
 * through a stream.
 *
 * In most cases the iter can adjust to send just as much data will
 * fit.  In some cases that would be too complicated, because it has
 * to transmit an integer or something similar.  So in that case we
 * stick whatever won't fit into a small buffer.
 *
 * A tube can contain some literal data to go out (typically command
 * bytes), and also an instruction to copy data from the stream's
 * input or from some other location.  Both literal data and a copy
 * command can be queued at the same time, but only in that order and
 * at most one of each. */


/*
 * TODO: As an optimization, write it directly to the stream if
 * possible.  But for simplicity don't do that yet.
 *
 * TODO: I think our current copy code will lock up if the application
 * only ever calls us with either input or output buffers, and not
 * both.  So I guess in that case we might need to copy into some
 * temporary buffer space, and then back out again later.
 */


#include <config.h>

#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

#include "rsync.h"
#include "trace.h"
#include "util.h"
#include "job.h"
#include "stream.h"


static void rs_tube_catchup_literal(rs_job_t *job)
{
    rs_buffers_t *stream = job->stream;
    int len, remain;

    len = job->lit_len;
    assert(len > 0);

    assert(len > 0);
    if ((size_t) len > stream->avail_out)
        len = stream->avail_out;

    if (!stream->avail_out) {
        rs_trace("no output space available");
        return;
    }

    memcpy(stream->next_out, job->lit_buf, len);
    stream->next_out += len;
    stream->avail_out -= len;

    remain = job->lit_len - len;
    rs_trace("transmitted %d literal bytes from tube, %d remain",
             len, remain);

    if (remain > 0) {
        /* Still something left in the tube... */
        memmove(job->lit_buf, job->lit_buf + len, remain);
    } else {
        assert(remain == 0);
    }

    job->lit_len = remain;
}


static void rs_tube_catchup_copy(rs_job_t *job)
{
    int copied;
    rs_buffers_t *stream = job->stream;

    assert(job->lit_len == 0);
    assert(job->copy_len > 0);

    copied = rs_buffers_copy(stream, job->copy_len);

    job->copy_len -= copied;

    rs_trace("transmitted %d copy bytes from tube, %d remain",
             copied, job->copy_len);
}


/*
 * Put whatever will fit from the tube into the output of the stream.
 * Return RS_DONE if the tube is now empty and ready to accept another
 * command, RS_BLOCKED if there is still stuff waiting to go out.
 */
int rs_tube_catchup(rs_job_t *job)
{
    if (job->lit_len)
        rs_tube_catchup_literal(job);

    if (job->lit_len) {
        /* there is still literal data queued, so we can't send
         * anything else. */
        return RS_BLOCKED;
    }

    if (job->copy_len)
        rs_tube_catchup_copy(job);
    
    if (job->copy_len)
        return RS_BLOCKED;

    return RS_DONE;
}


/* Check whether there is data in the tube waiting to go out.  So if true
 * this basically means that the previous command has finished doing all its
 * output. */
int rs_tube_is_idle(rs_job_t const *job)
{
    return job->lit_len == 0 && job->copy_len == 0;
}


/*
 * Queue up a request to copy through LEN bytes from the input to the
 * output of the stream.  We can only accept this request if there is
 * no copy command already pending.
 */
void rs_blow_copy(rs_job_t *job, int len)
{
    assert(job->copy_len == 0);

    job->copy_len = len;
}



/*
 * Push some data into the tube for storage.  The tube's never
 * supposed to get very big, so this will just pop loudly if you do
 * that.
 *
 * We can't accept literal data if there's already a copy command in the
 * tube, because the literal data comes out first.
 */
void
rs_blow_literal(rs_job_t *job, const void *buf, size_t len)
{
    assert(job->copy_len == 0);

    if (len > sizeof(job->lit_buf) - job->lit_len) {
        rs_fatal("tube popped when trying to blow %ld literal bytes!",
                 (long) len);
    }

    memcpy(job->lit_buf + job->lit_len, buf, len);
    job->lit_len += len;
}
