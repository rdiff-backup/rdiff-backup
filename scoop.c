/*=                                     -*- c-file-style: "linux" -*-
 *
 * libhsync -- the library for network deltas
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
 * ahead.c -- This file deals with readahead from caller-supplied buffers.
 *
 * Many functions require a certain minimum amount of input to do their
 * processing.  For example, to calculate a strong checksum of a block
 * we need at least a block of input.
 *
 * Since we put the buffers completely under the control of the caller,
 * we can't count on ever getting this much data all in one go.  We
 * can't simply wait, because the caller might have a smaller buffer
 * than we require and so we'll never get it.  For the same reason we
 * must always accept all the data we're given.
 *
 * So, stream input data that's required for readahead is put into a
 * special buffer, from which the caller can then read.  It's
 * essentially like an internal pipe, which on any given read request
 * may or may not be able to actually supply the data.
 *
 * As a future optimization, we might try to take data directly from the
 * input buffer if there's already enough there.
 */

/*
 * TODO: We probably know a maximum amount of data that can be scooped
 * up, so we could just avoid dynamic allocation.  However that can't
 * be fixed at compile time, because when generating a delta it needs
 * to be large enough to hold one full block.  Perhaps we can set it
 * up when the job is allocated?  It would be kind of nice to not do
 * any memory allocation after startup, as bzlib does this.
 */


                              /*
                               | To walk on water you've gotta sink 
                               | in the ice.
                               |   -- Shihad, `The General Electric'.
                               */

#include "config.h"

#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#include "hsync.h"
#include "stream.h"
#include "trace.h"
#include "util.h"


/*
 * Try to accept from the input buffer to get LEN bytes in the scoop. 
 */
static void _hs_scoop_input(hs_stream_t *stream, size_t len)
{
        hs_simpl_t *impl = stream->impl;
        size_t tocopy;

        assert(len > impl->scoop_avail);

        if (impl->scoop_alloc < len) {
                /* need to allocate a new buffer, too */
                char *newbuf;
                newbuf = _hs_alloc(len, "scoop buffer");
                if (impl->scoop_avail)
                        memcpy(newbuf, impl->scoop_next, impl->scoop_avail);
                if (impl->scoop_buf)
                        free(impl->scoop_buf);
                impl->scoop_buf = impl->scoop_next = newbuf;
                impl->scoop_alloc = len;
                _hs_trace("resized scoop buffer to %d bytes",
                          impl->scoop_alloc);
        } else {
                /* this buffer size is fine, but move the existing
                 * data down to the front. */
                memmove(impl->scoop_buf, impl->scoop_next, impl->scoop_avail);
                impl->scoop_next = impl->scoop_buf;
        }

        /* take as much input as is available, to give up to LEN bytes
         * in the scoop. */
        tocopy = len - impl->scoop_avail;
        if (tocopy > stream->avail_in)
                tocopy = stream->avail_in;
        assert(tocopy + impl->scoop_avail <= impl->scoop_alloc);

        memcpy(impl->scoop_next + impl->scoop_avail, stream->next_in, tocopy);
        _hs_trace("accepted %d bytes from input to scoop", tocopy);
        impl->scoop_avail += tocopy;
        stream->next_in += tocopy;
        stream->avail_in -= tocopy;
}



/*
 * Ask for LEN bytes of input from the stream.  If that much data is
 * available, then return a pointer to it in PTR, advance the stream
 * input pointer over the data, and return HS_OK.  If there's not
 * enough data, then accept whatever is there into a buffer, advance over it,
 * and return HS_BLOCKED.
 *
 * Once data has been scooped up it cannot be put back.
 */
int _hs_stream_require(hs_stream_t *stream, size_t len, void **ptr)
{
        hs_simpl_t *impl = stream->impl;
        
        _hs_stream_check(stream);
        if (impl->scoop_avail >= len) {
                /* We have enough data queued to satisfy the request,
                 * so go straight from the scoop buffer. */
                _hs_trace("got %d bytes direct from scoop", len);
                *ptr = impl->scoop_next;
                impl->scoop_avail -= len;
                return HS_OK;
        } else if (impl->scoop_avail) {
                /* We have some data in the scoop, but not enough to
                 * satisfy the request. */
                _hs_trace("data is present in the scoop and must be used");
                _hs_scoop_input(stream, len);

                if (impl->scoop_avail < len) {
                        _hs_trace("still only have %d bytes in scoop, not enough",
                                  impl->scoop_avail);
                        return HS_BLOCKED;
                } else {
                        _hs_trace("scoop now has %d bytes, this is enough",
                                  impl->scoop_avail);
                        *ptr = impl->scoop_next;
                        impl->scoop_avail -= len;
                        return HS_OK;
                }
        } else if (stream->avail_in >= len) {
                /* There's enough data in the stream's input */
                _hs_trace("got %d bytes direct from input", len);
                *ptr = stream->next_in;
                stream->next_in += len;
                stream->avail_in -= len;
                return HS_OK;
        } else {
                /* Nothing was queued before, but we don't have enough
                 * data to satisfy the request.  So queue what little
                 * we have, and try again next time. */
                _hs_trace("not enough data to satisfy request, scooping %d bytes",
                          impl->scoop_avail);
                _hs_scoop_input(stream, len);
                return HS_BLOCKED;
        }
}
