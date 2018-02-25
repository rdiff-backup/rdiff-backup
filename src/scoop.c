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
                               | To walk on water you've gotta sink
                               | in the ice.
                               |   -- Shihad, `The General Electric'.
                               */

/** \file scoop.c This file deals with readahead from caller-supplied buffers.
 *
 * Many functions require a certain minimum amount of input to do their
 * processing. For example, to calculate a strong checksum of a block we need
 * at least a block of input.
 *
 * Since we put the buffers completely under the control of the caller, we
 * can't count on ever getting this much data all in one go. We can't simply
 * wait, because the caller might have a smaller buffer than we require and so
 * we'll never get it. For the same reason we must always accept all the data
 * we're given.
 *
 * So, stream input data that's required for readahead is put into a special
 * buffer, from which the caller can then read. It's essentially like an
 * internal pipe, which on any given read request may or may not be able to
 * actually supply the data.
 *
 * As a future optimization, we might try to take data directly from the input
 * buffer if there's already enough there.
 *
 * \todo We probably know a maximum amount of data that can be scooped up, so
 * we could just avoid dynamic allocation. However that can't be fixed at
 * compile time, because when generating a delta it needs to be large enough to
 * hold one full block. Perhaps we can set it up when the job is allocated? It
 * would be kind of nice to not do any memory allocation after startup, as
 * bzlib does this. */

#include "config.h"

#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#include "librsync.h"
#include "job.h"
#include "stream.h"
#include "trace.h"
#include "util.h"

/** Try to accept a from the input buffer to get LEN bytes in the scoop. */
void rs_scoop_input(rs_job_t *job, size_t len)
{
    rs_buffers_t *stream = job->stream;
    size_t tocopy;

    assert(len > job->scoop_avail);

    if (job->scoop_alloc < len) {
        /* Need to allocate a larger scoop. */
        rs_byte_t *newbuf;
        size_t newsize;
        for (newsize = 64; newsize < len; newsize <<= 1) ;
        newbuf = rs_alloc(newsize, "scoop buffer");
        if (job->scoop_avail)
            memcpy(newbuf, job->scoop_next, job->scoop_avail);
        if (job->scoop_buf)
            free(job->scoop_buf);
        job->scoop_buf = job->scoop_next = newbuf;
        rs_trace("resized scoop buffer to " FMT_SIZE " bytes from " FMT_SIZE "",
                 newsize, job->scoop_alloc);
        job->scoop_alloc = newsize;
    } else if (job->scoop_buf != job->scoop_next) {
        /* Move existing data to the front of the scoop. */
        rs_trace("moving scoop " FMT_SIZE " bytes to reuse " FMT_SIZE " bytes",
                 job->scoop_avail, (size_t)(job->scoop_next - job->scoop_buf));
        memmove(job->scoop_buf, job->scoop_next, job->scoop_avail);
        job->scoop_next = job->scoop_buf;
    }
    /* take as much input as is available, to give up to LEN bytes in the
       scoop. */
    tocopy = len - job->scoop_avail;
    if (tocopy > stream->avail_in)
        tocopy = stream->avail_in;
    assert(tocopy + job->scoop_avail <= job->scoop_alloc);

    memcpy(job->scoop_next + job->scoop_avail, stream->next_in, tocopy);
    rs_trace("accepted " FMT_SIZE " bytes from input to scoop", tocopy);
    job->scoop_avail += tocopy;
    stream->next_in += tocopy;
    stream->avail_in -= tocopy;
}

/** Advance the input cursor forward \p len bytes.
 *
 * This is used after doing readahead, when you decide you want to keep it. \p
 * len must be no more than the amount of available data, so you can't cheat.
 *
 * So when creating a delta, we require one block of readahead. But after
 * examining that block, we might decide to advance over all of it (if there is
 * a match), or just one byte (if not). */
void rs_scoop_advance(rs_job_t *job, size_t len)
{
    rs_buffers_t *stream = job->stream;

    /* It never makes sense to advance over a mixture of bytes from the scoop
       and input, because you couldn't possibly have looked at them all at the
       same time. */
    if (job->scoop_avail) {
        /* reading from the scoop buffer */
        rs_trace("advance over " FMT_SIZE " bytes from scoop", len);
        assert(len <= job->scoop_avail);
        job->scoop_avail -= len;
        job->scoop_next += len;
    } else {
        rs_trace("advance over " FMT_SIZE " bytes from input buffer", len);
        assert(len <= stream->avail_in);
        stream->avail_in -= len;
        stream->next_in += len;
    }
}

/** Read from scoop without advancing.
 *
 * Ask for LEN bytes of input from the stream. If that much data is available,
 * then return a pointer to it in PTR, advance the stream input pointer over
 * the data, and return RS_DONE. If there's not enough data, then accept
 * whatever is there into a buffer, advance over it, and return RS_BLOCKED.
 *
 * The data is not actually removed from the input, so this function lets you
 * do readahead. If you want to keep any of the data, you should also call
 * rs_scoop_advance() to skip over it. */
rs_result rs_scoop_readahead(rs_job_t *job, size_t len, void **ptr)
{
    rs_buffers_t *stream = job->stream;
    rs_job_check(job);

    if (!job->scoop_avail && stream->avail_in >= len) {
        /* The scoop is empty and there's enough data in the input. */
        *ptr = stream->next_in;
        rs_trace("got " FMT_SIZE " bytes direct from input", len);
        return RS_DONE;
    } else if (job->scoop_avail < len && stream->avail_in) {
        /* There is not enough data in the scoop. */
        rs_trace("scoop has less than " FMT_SIZE " bytes, scooping from "
                 FMT_SIZE " input bytes", len, stream->avail_in);
        rs_scoop_input(job, len);
    }
    if (job->scoop_avail >= len) {
        /* There is enough data in the scoop now. */
        rs_trace("scoop has at least " FMT_SIZE " bytes, this is enough",
                 job->scoop_avail);
        *ptr = job->scoop_next;
        return RS_DONE;
    } else if (stream->eof_in) {
        /* Not enough input data and at EOF. */
        rs_trace("reached end of input stream");
        return RS_INPUT_ENDED;
    } else {
        /* Not enough input data yet. */
        rs_trace("blocked with insufficient input data");
        return RS_BLOCKED;
    }
}

/** Read LEN bytes if possible, and remove them from the input scoop.
 *
 * \param ptr will be updated to point to a read-only buffer holding the data,
 * if enough is available.
 *
 * \return RS_DONE if there was enough data, RS_BLOCKED if there was not enough
 * data yet, or RS_INPUT_ENDED if there was not enough data and at EOF. */
rs_result rs_scoop_read(rs_job_t *job, size_t len, void **ptr)
{
    rs_result result;

    result = rs_scoop_readahead(job, len, ptr);
    if (result == RS_DONE)
        rs_scoop_advance(job, len);
    return result;
}

/** Read whatever data remains in the input stream.
 *
 * \param *len will be updated to the length of the available data.
 *
 * \param **ptr will point at the available data.
 *
 * \return RS_DONE if there was data, RS_INPUT_ENDED if there was no data and
 * at EOF, RS_BLOCKED if there was no data and not at EOF. */
rs_result rs_scoop_read_rest(rs_job_t *job, size_t *len, void **ptr)
{
    rs_buffers_t *stream = job->stream;

    *len = job->scoop_avail + stream->avail_in;
    if (*len)
        return rs_scoop_read(job, *len, ptr);
    else if (stream->eof_in)
        return RS_INPUT_ENDED;
    else
        return RS_BLOCKED;
}

/** Return the total number of bytes available including the scoop and input
 * buffer. */
size_t rs_scoop_total_avail(rs_job_t *job)
{
    return job->scoop_avail + job->stream->avail_in;
}
