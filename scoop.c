/*=                    -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * libhsync -- the library for network deltas
 * $Id$
 * 
 * Copyright (C) 2000, 2001 by Martin Pool <mbp@samba.org>
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
 * scoop.c -- This file deals with readahead from caller-supplied
 * buffers.
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

#include <config.h>

#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#include "hsync.h"
#include "stream.h"
#include "trace.h"
#include "util.h"


/**
 * Try to accept a from the input buffer to get LEN bytes in the scoop.
 */
static void hs_scoop_input(hs_stream_t *stream, size_t len)
{
    hs_simpl_t *impl = stream->impl;
    size_t tocopy;

    assert(len > impl->scoop_avail);

    if (impl->scoop_alloc < len) {
        /* need to allocate a new buffer, too */
        char *newbuf;
        int newsize = 2 * len;
        newbuf = hs_alloc(newsize, "scoop buffer");
        if (impl->scoop_avail)
            memcpy(newbuf, impl->scoop_next, impl->scoop_avail);
        if (impl->scoop_buf)
            free(impl->scoop_buf);
        impl->scoop_buf = impl->scoop_next = newbuf;
        hs_trace("resized scoop buffer to %d bytes from %d",
                 newsize, impl->scoop_alloc);
        impl->scoop_alloc = newsize;
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
    hs_trace("accepted %d bytes from input to scoop", tocopy);
    impl->scoop_avail += tocopy;
    stream->next_in += tocopy;
    stream->avail_in -= tocopy;
}


/*
 * Advance the input cursor forward LEN bytes.  This is used after
 * doing readahead, when you decide you want to keep it.  LEN must be
 * no more than the amount of available data, so you can't cheat.
 *
 * So when creating a delta, we require one block of readahead.  But
 * after examining that block, we might decide to advance over all of
 * it (if there is a match), or just one byte (if not).
 */
void hs_scoop_advance(hs_stream_t *stream, size_t len)
{
    hs_simpl_t *impl = stream->impl;
        
    if (impl->scoop_avail) {
        /* reading from the scoop buffer */
/*         hs_trace("advance over %d bytes from scoop", len); */
        assert(len <= impl->scoop_avail);
        impl->scoop_avail -= len;
        impl->scoop_next += len;
    } else {
/*         hs_trace("advance over %d bytes from input buffer", len); */
        assert(len <= stream->avail_in);
        stream->avail_in -= len;
        stream->next_in += len;
    }
}



/*
 * Ask for LEN bytes of input from the stream.  If that much data is
 * available, then return a pointer to it in PTR, advance the stream
 * input pointer over the data, and return HS_DONE.  If there's not
 * enough data, then accept whatever is there into a buffer, advance
 * over it, and return HS_BLOCKED.
 *
 * The data is not actually removed from the input, so this function
 * lets you do readahead.  If you want to keep any of the data, you
 * should also call hs_scoop_advance to skip over it.
 */
hs_result hs_scoop_readahead(hs_stream_t *stream, size_t len, void **ptr)
{
    hs_simpl_t *impl = stream->impl;
        
    hs_stream_check(stream);
    if (impl->scoop_avail >= len) {
        /* We have enough data queued to satisfy the request,
         * so go straight from the scoop buffer. */
        hs_trace("got %d bytes direct from scoop", len);
        *ptr = impl->scoop_next;
        return HS_DONE;
    } else if (impl->scoop_avail) {
        /* We have some data in the scoop, but not enough to
         * satisfy the request. */
        hs_trace("data is present in the scoop and must be used");
        hs_scoop_input(stream, len);

        if (impl->scoop_avail < len) {
            hs_trace("still have only %d bytes in scoop",
                     impl->scoop_avail);
            return HS_BLOCKED;
        } else {
            hs_trace("scoop now has %d bytes, this is enough",
                     impl->scoop_avail);
            *ptr = impl->scoop_next;
            return HS_DONE;
        }
    } else if (stream->avail_in >= len) {
        /* There's enough data in the stream's input */
        hs_trace("got %d bytes direct from input", len);
        *ptr = stream->next_in;
        return HS_DONE;
    } else if (impl->scoop_avail > 0) {
        /* Nothing was queued before, but we don't have enough
         * data to satisfy the request.  So queue what little
         * we have, and try again next time. */
        hs_trace("couldn't satisfy request for %d, scooping %d bytes",
                 len, impl->scoop_avail);
        hs_scoop_input(stream, len);
        return HS_BLOCKED;
    } else if (stream->eof_in) {
        /* Nothing is queued before, and nothing is in the input
         * buffer at the moment. */
        hs_trace("reached EOF on input stream");
        return HS_INPUT_ENDED;
    } else {
        /* Nothing queued at the moment. */
        hs_trace("blocked with no data in scoop or input buffer");
        return HS_BLOCKED;
    }
}



/**
 * Read LEN bytes if possible, and remove them from the input scoop.
 * If there's not enough data yet, return HS_BLOCKED.
 *
 * \param ptr will be updated to point to a read-only buffer holding
 * the data, if enough is available.
 *
 * \return HS_DONE if all the data was available, HS_BLOCKED if it's
 * not there.
 */
hs_result hs_scoop_read(hs_stream_t *stream, size_t len, void **ptr)
{
    hs_result result;

    result = hs_scoop_readahead(stream, len, ptr);
    if (result == HS_DONE)
        hs_scoop_advance(stream, len);

    return result;
}



/*
 * Read whatever remains in the input stream, assuming that it runs up
 * to the end of the file.  Set LEN appropriately.
 */
hs_result hs_scoop_read_rest(hs_stream_t *stream, size_t *len, void **ptr)
{
    hs_simpl_t *impl = stream->impl;

    *len = impl->scoop_avail + stream->avail_in;

    return hs_scoop_read(stream, *len, ptr);
}
