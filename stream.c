/*=                                     -*- c-file-style: "linux" -*-
 *
 * libhsync -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool <mbp@linuxcare.com.au>
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

                                   /*
                                    * Pick a window, Jimmy, you're leaving.
                                    */


/*
 * OK, so I'll admit IO here is a little complex.  The most important
 * player here is the stream, which is an object for managing filter
 * operations.  It has both input and output sides, both of which is
 * just a (pointer,len) pair into a buffer provided by the client.
 * The code controlling the stream handles however much data it wants,
 * and the client provides or accepts however much is convenient.
 *
 * At the same time as being friendly to the client, we also try to be
 * very friendly to the internal code.  It wants to be able to ask for
 * arbitrary amounts of input or output and get it without having to
 * keep track of partial completion.  So there are functions which
 * either complete, or queue whatever was not sent and return
 * HS_BLOCKED.
 *
 * The output buffer is a little more clever than simply a data
 * buffer.  Instead it knows that we can send either literal data, or
 * data copied through from the input of the stream.
 *
 * In streamfile.c you will find functions that then map buffers onto
 * stdio files.
 *
 * So on return from an encoding function, either the input or the
 * output or possibly both will have no more bytes available.
 */

/*
 * Manage libhsync streams of IO.
 *
 * libhsync never does IO or memory allocation, but relies on the
 * caller.  This is very nice for integration, but means that we have
 * to be fairly flexible as to when we can `read' or `write' stuff
 * internally.
 *
 * libhsync basically does two types of IO.  It reads network integers
 * of various lengths which encode command and control information
 * such as versions and signatures.  It also does bulk data transfer.
 *
 * IO of network integers is internally buffered, because higher
 * levels of the code need to see them transmitted atomically: it's no
 * good to read half of a uint32.  So there is a small and fixed
 * length internal buffer which accumulates these.  Unlike previous
 * versions of the library, we don't require that the caller hold the
 * start until the whole thing has arrived, which guarantees that we
 * can always make progress.
 *
 * On each call into a stream iterator, it should begin by trying to
 * flush output.  This may well use up all the remaining stream space,
 * in which case nothing else can be done.
 */

/* TODO: Return errors rather than aborting if something goes wrong.  */


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
#include "stream.h"
#include "util.h"
#include "trace.h"

static const int HS_STREAM_DOGTAG = 2001125;


void hs_stream_init(hs_stream_t *stream)
{
        hs_simpl_t *impl;
        
        assert(stream);
        _hs_bzero(stream, sizeof *stream);
        stream->dogtag = HS_STREAM_DOGTAG;

        impl = stream->impl = _hs_alloc_struct(hs_simpl_t);

        /* because scoop_alloc == 0, the scoop buffer will be
         * allocated when required. */
}


/*
 * Make sure everything is basically OK with STREAM.
 */
void
_hs_stream_check(hs_stream_t *stream)
{
        assert(stream);
        assert(stream->dogtag == HS_STREAM_DOGTAG);
}


/*
 * Copy up to MAX_LEN bytes from input of STREAM to its output.  Return
 * the number of bytes actually copied, which may be less than LEN if
 * there is not enough space in one or the other stream.
 *
 * This always does the copy immediately.  Most functions should call
 * _hs_blow_copy to cause the copy to happen gradually as space
 * becomes available.
 */
int _hs_stream_copy(hs_stream_t *stream, int max_len)
{
        int len = max_len;
    
        _hs_stream_check(stream);
        assert(len > 0);

        if ((unsigned) len > stream->avail_in) {
                _hs_trace("copy limited to %d available input bytes",
                          stream->avail_in);
                len = stream->avail_in;
        }

        if ((unsigned) len > stream->avail_out) {
                _hs_trace("copy limited to %d available output bytes",
                          stream->avail_out);
                len = stream->avail_out;
        }

        _hs_trace("stream copied chunk of %d bytes", len);

        memcpy(stream->next_out, stream->next_in, len);
    
        stream->next_out += len;
        stream->avail_out -= len;

        stream->next_in += len;
        stream->avail_in -= len;

        return len;
}


/*
 * Check whether the stream is empty.  This means that there is no
 * more data in either the internal or external buffers.  If you know
 * that you don't have any more data to send in, then this basically
 * means you're done.
 */
int
_hs_stream_is_empty(hs_stream_t *stream)
{
        int ret = stream->avail_in == 0  &&  _hs_tube_is_idle(stream);

        if (ret)
                _hs_trace("stream now has no input and no tube output");
    
        return ret;
}



/*
 * Whenever a stream processing function exits, it should have done so
 * because it has either consumed all the input or has filled the
 * output buffer.  This function checks that simple postcondition.
 */
void _hs_stream_check_exit(hs_stream_t const *stream)
{
        assert(stream->avail_in == 0  ||  stream->avail_out == 0);
}
