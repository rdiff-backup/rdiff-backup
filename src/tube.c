/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 2000, 2001 by Martin Pool <mbp@sourcefrog.net>
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


#include "config.h"

#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

#include "librsync.h"
#include "trace.h"
#include "util.h"
#include "job.h"
#include "stream.h"


static void rs_tube_catchup_write(rs_job_t *job)
{
    rs_buffers_t *stream = job->stream;
    int len, remain;

    len = job->write_len;
    assert(len > 0);

    assert(len > 0);
    if ((size_t) len > stream->avail_out)
        len = stream->avail_out;

    if (!stream->avail_out) {
        rs_trace("no output space available");
        return;
    }

    memcpy(stream->next_out, job->write_buf, len);
    stream->next_out += len;
    stream->avail_out -= len;

    remain = job->write_len - len;
    rs_trace("transmitted %d write bytes from tube, "
             "%d remain to be sent",
             len, remain);

    if (remain > 0) {
        /* Still something left in the tube... */
        memmove(job->write_buf, job->write_buf + len, remain);
    } else {
        assert(remain == 0);
    }

    job->write_len = remain;
}


/**
 * Execute a copy command, taking data from the scoop.
 *
 * \sa rs_tube_catchup_copy()
 */
static void
rs_tube_copy_from_scoop(rs_job_t *job)
{
    size_t       this_len;
    rs_buffers_t *stream = job->stream;

    this_len = job->copy_len;
    if (this_len > job->scoop_avail) {
        this_len = job->scoop_avail;
    }
    if (this_len > stream->avail_out) {
        this_len = stream->avail_out;
    }

    memcpy(stream->next_out, job->scoop_next, this_len);

    stream->next_out += this_len;
    stream->avail_out -= this_len;
        
    job->scoop_avail -= this_len;
    job->scoop_next += this_len;

    job->copy_len -= this_len;

    rs_trace("caught up on %ld copied bytes from scoop, %ld remain there, "
             "%ld remain to be copied", 
             (long) this_len, (long) job->scoop_avail, (long) job->copy_len);
}



/**
 * Catch up on an outstanding copy command.
 *
 * Takes data from the scoop, and the input (in that order), and
 * writes as much as will fit to the output, up to the limit of the
 * outstanding copy.
 */
static void rs_tube_catchup_copy(rs_job_t *job)
{
    rs_buffers_t *stream = job->stream;

    assert(job->write_len == 0);
    assert(job->copy_len > 0);

    if (job->scoop_avail  && job->copy_len) {
        /* there's still some data in the scoop, so we should use that. */
        rs_tube_copy_from_scoop(job);
    }
    
    if (job->copy_len) {
        size_t  this_copy;

        this_copy = rs_buffers_copy(stream, job->copy_len);

        job->copy_len -= this_copy;

        rs_trace("copied " PRINTF_FORMAT_U64 " bytes from input buffer, " PRINTF_FORMAT_U64 " remain to be copied",
                 PRINTF_CAST_U64(this_copy), PRINTF_CAST_U64(job->copy_len));
    }
}


/*
 * Put whatever will fit from the tube into the output of the stream.
 * Return RS_DONE if the tube is now empty and ready to accept another
 * command, RS_BLOCKED if there is still stuff waiting to go out.
 */
int rs_tube_catchup(rs_job_t *job)
{
    if (job->write_len)
        rs_tube_catchup_write(job);

    if (job->write_len) {
        /* there is still write data queued, so we can't send
         * anything else. */
        return RS_BLOCKED;
    }

    if (job->copy_len)
        rs_tube_catchup_copy(job);
    
    if (job->copy_len) {
        if (job->stream->eof_in && !job->stream->avail_in && !job->scoop_avail) {
            rs_log(RS_LOG_ERR,
                   "reached end of file while copying literal data through buffers");
            return RS_INPUT_ENDED;
        }

        return RS_BLOCKED;
    }

    return RS_DONE;
}


/* Check whether there is data in the tube waiting to go out.  So if true
 * this basically means that the previous command has finished doing all its
 * output. */
int rs_tube_is_idle(rs_job_t const *job)
{
    return job->write_len == 0 && job->copy_len == 0;
}


/**
 * Queue up a request to copy through \p len bytes from the input to
 * the output of the stream.
 *
 * The data is copied from the scoop (if there is anything there) or
 * from the input, on the next call to rs_tube_write().
 *
 * We can only accept this request if there is no copy command already
 * pending.
 */
/* TODO: Try to do the copy immediately, and return a result.  Then,
 * people can try to continue if possible.  Is this really required?
 * Callers can just go out and back in again after flushing the
 * tube. */
void rs_tube_copy(rs_job_t *job, int len)
{
    assert(job->copy_len == 0);

    job->copy_len = len;
}



/*
 * Push some data into the tube for storage.  The tube's never
 * supposed to get very big, so this will just pop loudly if you do
 * that.
 *
 * We can't accept write data if there's already a copy command in the
 * tube, because the write data comes out first.
 */
void
rs_tube_write(rs_job_t *job, const void *buf, size_t len)
{
    assert(job->copy_len == 0);

    if (len > sizeof(job->write_buf) - job->write_len) {
        rs_fatal("tube popped when trying to write %ld bytes!",
                 (long) len);
    }

    memcpy(job->write_buf + job->write_len, buf, len);
    job->write_len += len;
}
