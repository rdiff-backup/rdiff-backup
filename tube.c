/*				       	-*- c-file-style: "bsd" -*-
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

#include "config.h"

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
#include <stdio.h>

#include "hsync.h"
#include "tube.h"
#include "trace.h"
#include "util.h"
#include "stream.h"


const int HS_TUBE_TAG = 892138;


typedef struct hs_tube {
    int		dogtag;

    /* If USED is >0, then buf contains that much literal data to be
     * sent out. */
    char        lit_buf[4096];
    int         lit_len;

    /* If COPY_LEN is >0, then that much data should be copied through
     * from the input. */
    int         copy_len;
} hs_tube_t;



void
_hs_tube_init(hs_stream_t *stream)
{
    stream->tube = _hs_alloc_struct(hs_tube_t);
    stream->tube->dogtag = HS_TUBE_TAG;
}


void
_hs_check_tube(hs_stream_t *stream)
{
    assert(stream);
    assert(stream->tube->dogtag == HS_TUBE_TAG);
}


static void
_hs_tube_catchup_literal(hs_stream_t *stream)
{
    hs_tube_t * const tube = stream->tube;
    int len, remain; 

    len = tube->lit_len;
    assert(len > 0);

    assert(len > 0);
    if ((size_t) len > stream->avail_out)
	len = stream->avail_out;

    memcpy(stream->next_out, tube->lit_buf, len);
    stream->next_out += len;
    stream->avail_out -= len;

    remain = tube->lit_len - len;
    if (remain > 0) {
	/* Still something left in the tube... */
	memmove(tube->lit_buf, tube->lit_buf + len, remain);
    } else {
	assert(remain == 0);
    }

    tube->lit_len = remain;
}


static void
_hs_tube_catchup_copy(hs_stream_t *stream)
{
    hs_tube_t * const tube = stream->tube;
    
    int copied;

    assert(tube->lit_len == 0);
    assert(tube->copy_len > 0);

    copied = _hs_stream_copy(stream, tube->copy_len);

    tube->copy_len -= copied;
}


/* Put whatever will fit from the tube into the output of the stream.
 * Return true if the tube is now empty and ready to accept another
 * command; else false. */
int
_hs_tube_catchup(hs_stream_t *stream)
{
    hs_tube_t * const tube = stream->tube;

    if (tube->lit_len)
	_hs_tube_catchup_literal(stream);

    if (tube->lit_len) {
	/* there is still literal data queued, so we can't send
	 * anything else. */
	return 0;
    }

    if (tube->copy_len)
	_hs_tube_catchup_copy(stream);

    return tube->copy_len == 0;
}


int
_hs_tube_is_idle(hs_stream_t const *stream)
{
    return stream->tube->lit_len == 0
	&& stream->tube->copy_len == 0;
}


/* Queue up a request to copy through LEN bytes from the input to the
 * output of STREAM.  We can only accept this request if there is no
 * copy command already pending. */
void
_hs_blow_copy(hs_stream_t *stream, int len)
{
    hs_tube_t * const tube = stream->tube;

    assert(tube->copy_len == 0);

    tube->copy_len = len;
}



/* Push some data into the tube for storage.  The tube's never
 * supposed to get very big, so this will just pop loudly if you do
 * that.
 *
 * We can't accept literal data if there's already a copy command in
 * the tube, because the literal data comes out first.
 *
 * TODO: As an optimization, write it directly to the stream if
 * possible.  But for simplicity don't do that yet.  */
void
_hs_blow_literal(hs_stream_t *stream, const void *buf, size_t len)
{
    hs_tube_t * const tube = stream->tube;

    assert(tube->copy_len == 0);

    if (len > sizeof(tube->lit_buf) - tube->lit_len) {
        _hs_fatal("tube popped when trying to blow %d literal bytes!", len);
    }

    memcpy(tube->lit_buf + tube->lit_len, buf, len);
    tube->lit_len += len;
}
