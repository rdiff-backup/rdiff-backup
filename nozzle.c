/*=                                     -*- c-file-style: "bsd" -*-
 *
 * libhsync -- library for network deltas
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool <mbp@samba.org>
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
 * Wrap a stream onto stdio files.
 *
 * The wrapper object contains small memory buffers that accumulate
 * data before it is written out.  At the moment the size is fixed.
 * You must create separate objects for input and output.
 */

#include "config.h"

#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <stdio.h>
#include <stdarg.h>
#include <assert.h>
#include <stdlib.h>

#include "hsync.h"
#include "trace.h"
#include "util.h"
#include "nozzle.h"
#include "tube.h"
#include "stream.h"

#define HS_NOZZLE_IN_TAG 0x87232
#define HS_NOZZLE_OUT_TAG 0x87233


struct hs_nozzle {
    int          tag;
    FILE        *file;
    char	*buf;
    size_t       buf_len;
    hs_stream_t *stream;
};


hs_nozzle_t *
_hs_nozzle_new_fd(int fd, hs_stream_t *stream, int buf_len,
		  char const * mode)
{
    return _hs_nozzle_new(fdopen(fd, mode), stream, buf_len, mode);
}



hs_nozzle_t *
_hs_nozzle_new(FILE *file, hs_stream_t *stream, int buf_len,
	       char const *mode)
{
    /* allocate a new nozzle object */
    hs_nozzle_t *noz = _hs_alloc_struct(hs_nozzle_t);

    assert(buf_len > 0);

    noz->file = file;
    noz->buf_len = buf_len;
    noz->buf = _hs_alloc(noz->buf_len, "nozzle buffer");
    noz->stream = stream;

    if (*mode == 'r') {
        assert(!stream->next_in);
        stream->next_in = noz->buf;
        stream->avail_in = 0;
	noz->tag = HS_NOZZLE_IN_TAG;
    } else {
        assert(*mode == 'w');
        assert(!stream->next_out);
        stream->next_out = noz->buf;
        stream->avail_out = noz->buf_len;
	noz->tag = HS_NOZZLE_OUT_TAG;
    }

    return noz;
}


void
_hs_nozzle_delete(hs_nozzle_t *noz)
{
    assert(noz->tag == HS_NOZZLE_IN_TAG
	   || noz->tag == HS_NOZZLE_OUT_TAG);
    free(noz->buf);
    free(noz);
}


/*
 * Move existing data, if any, to the start of the buffer.  Read in
 * more data to fill the buffer up.
 *
 * Returns false at EOF; true otherwise.
 */
int
_hs_nozzle_in(hs_nozzle_t *noz)
{
    hs_stream_t * const stream = noz->stream;
    int to_read, got;
    
    assert(noz->tag == HS_NOZZLE_IN_TAG);
    
    if (feof(noz->file)) {
	return 0;
    }

    assert(stream->avail_in <= noz->buf_len);
    assert(stream->next_in >= noz->buf
           && stream->next_in <= noz->buf + noz->buf_len);
    
    if (stream->avail_in > 0) {
        memmove(noz->buf, stream->next_in, stream->avail_in);
    }

    to_read = noz->buf_len - stream->avail_in;
    assert(to_read >= 0);
    assert((size_t) to_read <= noz->buf_len);
    if (to_read == 0)
        return stream->avail_in;

    
    got = fread(noz->buf + stream->avail_in, 1, to_read, noz->file);
    if (got < 0) {
	_hs_fatal("error reading: %s", strerror(errno));
    }

    stream->next_in = noz->buf;
    stream->avail_in += got;

    return 1;
}



/*
 * Write out available output data.  Move remaining data to the start
 * of the buffer.  Returns the amount of data returning to be written,
 * so when this reaches zero there is no more data (at the moment).
 */
int
_hs_nozzle_out(hs_nozzle_t *noz)
{
    hs_stream_t * const stream = noz->stream;
    int remains = 0, done, buffered;

    assert(noz->tag == HS_NOZZLE_OUT_TAG);

    assert(stream->avail_out <= noz->buf_len);
    assert(stream->next_out >= noz->buf
           && stream->next_out <= noz->buf + noz->buf_len);

    buffered = noz->buf_len - stream->avail_out;
    
    if (buffered) {
	_hs_trace("write %d bytes from stream to file", buffered);
	
        done = fwrite(noz->buf, 1, buffered, noz->file);
        if (done < 0) {
            _hs_fatal("error writing: %s", strerror(errno));
        }

        /* retain data */
        remains = buffered - done;

        if (remains)
            memmove(noz->buf, noz->buf + done, remains);
    }

    stream->next_out = noz->buf + remains;
    stream->avail_out = noz->buf_len - remains;
    return remains;
}


/* Continue doing output until the tube is empty */
void
_hs_nozzle_drain(hs_nozzle_t *out_nozzle, hs_stream_t *stream)
{
    do {
        _hs_tube_catchup(stream);
        _hs_nozzle_out(out_nozzle);
    } while (!_hs_tube_is_idle(stream));
}


/* Continue doing input and output until the stream is at rest */
void
_hs_nozzle_siphon(hs_stream_t *stream, hs_nozzle_t *in_nozzle,
		  hs_nozzle_t *out_nozzle)
{
    do {
	_hs_nozzle_in(in_nozzle);
        _hs_tube_catchup(stream);
        _hs_nozzle_out(out_nozzle);
    } while (!_hs_tube_is_idle(stream));
}


