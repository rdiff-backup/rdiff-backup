/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
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
                               * Pick a window, Jimmy, you're leaving.
                               *   -- Martin Schwenke, regularly
                               */



#include <config.h>

#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <errno.h>
#include <string.h>

#include "hsync.h"
#include "hsyncfile.h"
#include "trace.h"
#include "buf.h"
#include "util.h"


int hs_inbuflen = 16000, hs_outbuflen = 16000;


struct hs_filebuf {
        FILE *f;
        hs_stream_t     *stream;
        char            *buf;
        size_t          buf_len;
};



hs_filebuf_t *hs_filebuf_new(FILE *f, hs_stream_t *stream, size_t buf_len) 
{
        hs_filebuf_t *pf = hs_alloc_struct(hs_filebuf_t);

        pf->buf = hs_alloc(buf_len, "file buffer");
        pf->buf_len = buf_len;
        pf->f = f;
        pf->stream = stream;

        return pf;
}


void hs_filebuf_free(hs_filebuf_t *fb) 
{
        hs_bzero(fb, sizeof *fb);
        free(fb);
}


/*
 * If the stream has no more data available, read some from F into
 * BUF, and let the stream use that.  On return, SEEN_EOF is true if
 * the end of file has passed into the stream.
 */
hs_result hs_infilebuf_fill(hs_filebuf_t *fb, int *seen_eof)
{
        hs_stream_t * const     stream = fb->stream;
        FILE                    *f = fb->f;
        
        /* This is only allowed if either the stream has no input buffer
         * yet, or that buffer could possibly be BUF. */
        if (stream->next_in != NULL) {
                assert(stream->avail_in <= fb->buf_len);
                assert(stream->next_in >= fb->buf);
                assert(stream->next_in <= fb->buf + fb->buf_len);
        } else {
                assert(stream->avail_in == 0);
        }
        
        if (stream->avail_in == 0 && !feof(fb->f)) {
                int len = fread(fb->buf, 1, fb->buf_len, f);
                if (len < 0) {
                        hs_error("error filling stream from file: %s",
                                  strerror(errno));
                        return HS_IO_ERROR;
                }
                stream->avail_in = len;
                stream->next_in = fb->buf;
        }

        if ((*seen_eof = feof(f))) {
                hs_trace("seen end of file on input");
        }

        return HS_DONE;
}


/*
 * The stream is already using BUF for an output buffer, and probably
 * contains some buffered output now.  Write this out to F, and reset
 * the buffer cursor.
 */
hs_result hs_outfilebuf_drain(hs_filebuf_t *fb)
{
        int present;
        hs_stream_t * const stream = fb->stream;
        FILE *f = fb->f;

        /* This is only allowed if either the stream has no output buffer
         * yet, or that buffer could possibly be BUF. */
        if (stream->next_out == NULL) {
                assert(stream->avail_out == 0);
                
                stream->next_out = fb->buf;
                stream->avail_out = fb->buf_len;
                
                return HS_DONE;
        }
        
        assert(stream->avail_out <= fb->buf_len);
        assert(stream->next_out >= fb->buf);
        assert(stream->next_out <= fb->buf + fb->buf_len);

        present = stream->next_out - fb->buf;
        if (present > 0) {
                int result;
                
                assert(present > 0);

                result = fwrite(fb->buf, 1, present, f);
                if (present != result) {
                        hs_error("error draining stream to file: %s",
                                  strerror(errno));
                        return HS_IO_ERROR;
                }

                stream->next_out = fb->buf;
                stream->avail_out = fb->buf_len;
        }
        
        return HS_DONE;
}


/**
 * Default copy implementation that retrieves a part of a stdio file.
 */
hs_result hs_file_copy_cb(void *arg, size_t *len, void **buf)
{
        int got;

        got = fread(*buf, 1, *len, (FILE *) arg);
        if (got == -1) {
                hs_error(strerror(errno));
                return HS_IO_ERROR;
        } else if (got == 0) {
                hs_error("unexpected eof");
                return HS_SHORT_STREAM;
        } else {
                *len = got;
                return HS_DONE;
        }
}
