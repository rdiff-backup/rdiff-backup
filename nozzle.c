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
                                         | No two people ever read the
                                         | same book.
                                         */


/*
 * Wrap a stream onto file descriptors.
 *
 * The wrapper object contains small memory buffers that accumulate
 * data before it is written out.  At the moment the size is fixed.
 * You must create separate objects for input and output.
 */

#include "includes.h"

#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <stdio.h>

#include "trace.h"
#include "util.h"


struct hs_iobuf {
    int    fd;
    byte_t *buf;
    size_t buf_len;
    hs_stream_t *stream;
};


hs_nozzle_t *
hs_nozzle_new(int fd, hs_stream_t *stream, int buf_len, char mode)
{
    /* allocate a new iobuf object */
    hs_nozzle_t *iot = _hs_alloc_struct(hs_nozzle_t);

    assert(buf_len > 0);

    iot->fd = fd;
    iot->buf_len = buf_len;
    iot->buf = _hs_alloc(iot->buf_len, "iobuf buffer");
    iot->stream = stream;

    if (mode == 'r') {
        assert(!stream->next_in);
        stream->next_in = iot->buf;
        stream->avail_in = 0;
    } else {
        assert(mode == 'w');
        assert(!stream->next_out);
        stream->next_out = iot->buf;
        stream->avail_out = iot->buf_len;
    }

    return iot;
}


void
hs_nozzle_delete(hs_nozzle_t *iot)
{
    free(iot->buf);
    free(iot);
}


/*
 * Move existing data, if any, to the start of the buffer.  Read in
 * more data to fill the buffer up.
 *
 * Returns amount of data now available; this goes to 0 at eof.
 */
int
hs_nozzle_in(hs_nozzle_t *iot)
{
    hs_stream_t * const stream = iot->stream;
    int to_read, got;
    
    assert(stream->avail_in <= iot->buf_len);
    assert(stream->next_in >= iot->buf
           && stream->next_in <= iot->buf + iot->buf_len);
    
    if (stream->avail_in > 0) {
        memmove(iot->buf, stream->next_in, stream->avail_in);
    }

    to_read = iot->buf_len - stream->avail_in;
    assert(to_read >= 0);
    assert((size_t) to_read <= iot->buf_len);
    if (to_read == 0)
        return stream->avail_in;

    got = read(iot->fd, iot->buf + stream->avail_in, to_read);
    if (got < 0) {
        _hs_fatal("error reading: %s", strerror(errno));
    }

    /* FIXME: If we see EOF, then don't keep trying to read. */
    
    stream->next_in = iot->buf;
    return stream->avail_in += got;
}



/*
 * Write out available output data.  Move remaining data to the start
 * of the buffer.  Returns the amount of data returning to be written,
 * so when this reaches zero there is no more data (at the moment).
 */
int
hs_nozzle_out(hs_nozzle_t *iot)
{
    hs_stream_t * const stream = iot->stream;
    int remains = 0, done, buffered;

    assert(stream->avail_out <= iot->buf_len);
    assert(stream->next_out >= iot->buf
           && stream->next_out <= iot->buf + iot->buf_len);

    buffered = iot->buf_len - stream->avail_out;
    
    if (buffered) {
        done = write(iot->fd, iot->buf, buffered);
        if (done < 0) {
            _hs_fatal("error writing: %s", strerror(errno));
        }

        /* retain data */
        remains = buffered - done;

        if (remains)
            memmove(iot->buf, iot->buf + done, remains);
    }

    stream->next_out = iot->buf + remains;
    stream->avail_out = iot->buf_len - remains;
    return remains;
}


