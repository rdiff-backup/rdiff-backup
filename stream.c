/*=                                     -*- c-file-style: "bsd" -*-
 * libhsync -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool <mbp@humbug.org.au>
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
                                    | Pick a window, Jimmy, you're leaving.
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
 * Streaming IO (e.g. copying literal data or from the basis file) is
 * never internally buffered, because there is simply no reason.  If
 * there is sufficient output space, we copy the whole thing.
 * Otherwise we copy only part, and remember internally how much
 * remains to be copied.  When copying literal data from input to
 * output, this means that the one with the smallest space available
 * will be the limiting factor.  Again, we can always make progress so
 * long as there is space in one buffer or the other.
 *
 * The result is that the top level of code can simply loop with a
 * condition like
 *
 *     while (output_avail && (buffered_output || input_avail))
 *
 * On each call into a stream iterator, it should begin by trying to
 * flush output.  This may well use up all the remaining stream space,
 * in which case nothing else can be done.
 *
 * TODO: Return errors rather than aborting if something goes wrong.
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

#include "hsync.h"
#include "stream.h"
#include "tube.h"
#include "util.h"

static const int STREAM_DOGTAG = 2001125;


void hs_stream_init(hs_stream_t *stream)
{
    extern int HS_TUBE_TAG;
    
    assert(stream);
    _hs_bzero(stream, sizeof *stream);
    stream->dogtag = STREAM_DOGTAG;
    stream->tube = _hs_alloc_struct(hs_tube_t);
    stream->tube->dogtag = HS_TUBE_TAG;
}


/*
 * Make sure everything is basically OK with STREAM.
 */
void
_hs_stream_check(hs_stream_t *stream)
{
    assert(stream);
    assert(stream->dogtag == STREAM_DOGTAG);
    assert(stream->next_in);
    assert(stream->next_out);
}


/*
 * Copy up to MAX_LEN bytes from input of STREAM to its output.  Return
 * the number of bytes actually copied, which may be less than LEN if
 * there is not enough space in one or the other stream.
 */
int
_hs_stream_copy(hs_stream_t *stream, int max_len)
{
    int len = max_len;
    
    _hs_stream_check(stream);
    assert(len > 0);

    if ((unsigned) len > stream->avail_in)
        len = stream->avail_in;

    if ((unsigned) len > stream->avail_out)
        len = stream->avail_out;

    memcpy(stream->next_out, stream->next_in, len);
    
    stream->next_out += len;
    stream->avail_out -= len;

    stream->next_in += len;
    stream->avail_in -= len;

    return len;
}


