/*			       	-*- c-file-style: "linux" -*-
 *
 * libhsync -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool <mbp@samba.org>
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


/* TODO: As an optimization, write it directly to the stream if
 * possible.  But for simplicity don't do that yet.  */


#include <config.h>

#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

#include "hsync.h"
#include "trace.h"
#include "util.h"
#include "stream.h"


const int HS_TUBE_TAG = 892138;


static void hs_tube_catchup_literal(hs_stream_t *stream)
{
        int len, remain;
        hs_simpl_t *tube = stream->impl;

        len = tube->lit_len;
        assert(len > 0);

        assert(len > 0);
        if ((size_t) len > stream->avail_out)
                len = stream->avail_out;

        if (!stream->avail_out) {
                hs_trace("no output space available");
                return;
        }

        memcpy(stream->next_out, tube->lit_buf, len);
        stream->next_out += len;
        stream->avail_out -= len;

        remain = tube->lit_len - len;
        hs_trace("transmitted %d literal bytes from tube, %d remain",
                  len, remain);

        if (remain > 0) {
                /* Still something left in the tube... */
                memmove(tube->lit_buf, tube->lit_buf + len, remain);
        } else {
                assert(remain == 0);
        }

        tube->lit_len = remain;
}


static void hs_tube_catchup_copy(hs_stream_t *stream)
{
        int copied;
        hs_simpl_t *tube = stream->impl;

        assert(tube->lit_len == 0);
        assert(tube->copy_len > 0);

        copied = hs_stream_copy(stream, tube->copy_len);

        tube->copy_len -= copied;

        hs_trace("transmitted %d copy bytes from tube, %d remain",
                  copied, tube->copy_len);
}


/*
 * Put whatever will fit from the tube into the output of the stream.
 * Return HS_OK if the tube is now empty and ready to accept another
 * command, HS_BLOCKED if there is still stuff waiting to go out.
 */
int hs_tube_catchup(hs_stream_t *stream)
{
        hs_simpl_t *tube = stream->impl;
        if (tube->lit_len)
                hs_tube_catchup_literal(stream);

        if (tube->lit_len) {
                /* there is still literal data queued, so we can't send
                 * anything else. */
                return HS_BLOCKED;
        }

        if (tube->copy_len)
                hs_tube_catchup_copy(stream);
    
        if (tube->copy_len)
                return HS_BLOCKED;

        return HS_OK;
}


/* Check whether there is data in the tube waiting to go out.  So if true
 * this basically means that the previous command has finished doing all its
 * output. */
int hs_tube_is_idle(hs_stream_t const *stream)
{
        hs_simpl_t *tube = stream->impl;
        return tube->lit_len == 0 && tube->copy_len == 0;
}


/*
 * Queue up a request to copy through LEN bytes from the input to the
 * output of the stream.  We can only accept this request if there is
 * no copy command already pending.
 */
void hs_blow_copy(hs_stream_t *stream, int len)
{
        hs_simpl_t *tube = stream->impl;
        assert(tube->copy_len == 0);

        tube->copy_len = len;
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
hs_blow_literal(hs_stream_t *stream, const void *buf, size_t len)
{
        hs_simpl_t *tube = stream->impl;
        assert(tube->copy_len == 0);

        if (len > sizeof(tube->lit_buf) - tube->lit_len) {
                hs_fatal("tube popped when trying to blow %d literal bytes!",
                          len);
        }

        memcpy(tube->lit_buf + tube->lit_len, buf, len);
        tube->lit_len += len;
}
