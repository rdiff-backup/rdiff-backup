/*				       	-*- c-file-style: "bsd" -*-
 * libhsync -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool <mbp@humbug.org.au>
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


/*
 * tube: a somewhat elastic but fairly small buffer for data passing
 * through a stream.
 *
 * In most cases the iter can adjust to send just as much data will
 * fit.  In some cases that would be too complicated, because it has
 * to transmit an integer or something similar.  So in that case we
 * stick whatever won't fit into a small buffer.
 */


#include <config.h>

#include <assert.h>

#ifdef HAVE_STDINT_H
#include <stdint.h>
#endif

#include <sys/types.h>
#include <limits.h>
#include <inttypes.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>

#include "hsync.h"
#include "tube.h"
#include "trace.h"


const int HS_TUBE_TAG = 892138;



void
_hs_check_tube(hs_stream_t *stream)
{
    assert(stream);
    assert(stream->tube->dogtag == HS_TUBE_TAG);
}


/*
 * Put whatever will fit from the tube into the output of the stream.
 */
void
_hs_tube_drain(hs_stream_t *stream)
{
    hs_tube_t * const tube = stream->tube;
    int len, remain;

    len = tube->used;
    if (!len)
        return;

    assert(len > 0);
    if ((size_t) len > stream->avail_out)
        len = stream->avail_out;

    memcpy(stream->next_out, tube->buf, len);
    stream->next_out += len;
    stream->avail_out -= len;

    remain = tube->used - len;
    if (remain > 0) {
        /* Still something left in the tube... */
        memmove(tube->buf, tube->buf + len, remain);
    } else {
        assert(remain == 0);
    }

    tube->used = remain;
}


int
_hs_tube_empty(hs_stream_t const *stream)
{
    return !stream->tube->used;
}



/*
 * Push some data into the tube for storage.  The tube's never
 * supposed to get very big, so this will just pop loudly if you do
 * that.
 *
 * TODO: As an optimization, write it directly to the stream if
 * possible.  But for simplicity don't do that yet.
 */
void
_hs_tube_blow(hs_stream_t *stream, byte_t const *buf, size_t len)
{
    hs_tube_t * const tube = stream->tube;

    if (len > sizeof(tube->buf) - tube->used) {
        _hs_fatal("tube popped when trying to blow %d bytes!", len);
    }

    memcpy(tube->buf + tube->used, buf, len);
    tube->used += len;
}
