/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- dynamic caching and delta update in HTTP
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
                      | Programming languages should be designed not
                      | by piling feature on top of feature, but by
                      | removing the weaknesses and restrictions that
                      | make additional features appear necessary.
                      |    -- Revised^5 Report on Scheme
                      */

/** \file stream.c Manage librsync streams of IO.
 *
 * See \sa scoop.c and \sa tube.c for related code for input and output
 * respectively.
 *
 * OK, so I'll admit IO here is a little complex. The most important player
 * here is the stream, which is an object for managing filter operations. It
 * has both input and output sides, both of which is just a (pointer,len) pair
 * into a buffer provided by the client. The code controlling the stream
 * handles however much data it wants, and the client provides or accepts
 * however much is convenient.
 *
 * At the same time as being friendly to the client, we also try to be very
 * friendly to the internal code. It wants to be able to ask for arbitrary
 * amounts of input or output and get it without having to keep track of
 * partial completion. So there are functions which either complete, or queue
 * whatever was not sent and return RS_BLOCKED.
 *
 * The output buffer is a little more clever than simply a data buffer. Instead
 * it knows that we can send either literal data, or data copied through from
 * the input of the stream.
 *
 * In buf.c you will find functions that then map buffers onto stdio files.
 *
 * So on return from an encoding function, either the input or the output or
 * possibly both will have no more bytes available.
 *
 * librsync never does IO or memory allocation, but relies on the caller. This
 * is very nice for integration, but means that we have to be fairly flexible
 * as to when we can `read' or `write' stuff internally.
 *
 * librsync basically does two types of IO. It reads network integers of
 * various lengths which encode command and control information such as
 * versions and signatures. It also does bulk data transfer.
 *
 * IO of network integers is internally buffered, because higher levels of the
 * code need to see them transmitted atomically: it's no good to read half of a
 * uint32. So there is a small and fixed length internal buffer which
 * accumulates these. Unlike previous versions of the library, we don't require
 * that the caller hold the start until the whole thing has arrived, which
 * guarantees that we can always make progress.
 *
 * On each call into a stream iterator, it should begin by trying to flush
 * output. This may well use up all the remaining stream space, in which case
 * nothing else can be done.
 *
 * \todo Kill this file and move the vestigial code remaining closer to where
 * it's used. */

#include "config.h"

#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

#include "librsync.h"
#include "stream.h"
#include "util.h"
#include "trace.h"

/** Copy up to \p max_len bytes from input of \b stream to its output.
 *
 * \return the number of bytes actually copied, which may be less than LEN if
 * there is not enough space in one or the other stream.
 *
 * This always does the copy immediately. Most functions should call
 * rs_tube_copy() to cause the copy to happen gradually as space becomes
 * available. */
int rs_buffers_copy(rs_buffers_t *stream, int max_len)
{
    int len = max_len;

    assert(len > 0);

    if ((unsigned)len > stream->avail_in) {
        rs_trace("copy limited to " FMT_SIZE " available input bytes",
                 stream->avail_in);
        len = stream->avail_in;
    }

    if ((unsigned)len > stream->avail_out) {
        rs_trace("copy limited to " FMT_SIZE " available output bytes",
                 stream->avail_out);
        len = stream->avail_out;
    }

    if (!len)
        return 0;
    /* rs_trace("stream copied chunk of %d bytes", len); */

    memcpy(stream->next_out, stream->next_in, len);

    stream->next_out += len;
    stream->avail_out -= len;

    stream->next_in += len;
    stream->avail_in -= len;

    return len;
}

/** Assert input is empty or output is full.
 *
 * Whenever a stream processing function exits, it should have done so because
 * it has either consumed all the input or has filled the output buffer. This
 * function checks that simple postcondition. */
void rs_buffers_check_exit(rs_buffers_t const *stream)
{
    assert(stream->avail_in == 0 || stream->avail_out == 0);
}
