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


#include "config.h"

#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <errno.h>
#include <string.h>

#include "hsync.h"
#include "trace.h"
#include "streamfile.h"



/*
 * If the stream has no more data available, read some from F into BUF,
 * and let the stream use that.
 */
int _hs_fill_from_file(hs_stream_t *stream, char *buf, size_t buf_len, FILE *f)
{
        /* This is only allowed if either the stream has no input buffer
         * yet, or that buffer could possibly be BUF. */
        if (stream->next_in != NULL) {
                assert(stream->avail_in <= buf_len);
                assert(stream->next_in >= buf);
                assert(stream->next_in <= buf + buf_len);
        } else {
                assert(stream->avail_in == 0);
        }
        
        if (stream->avail_in == 0 && !feof(f)) {
                int len = fread(buf, 1, buf_len, f);
                if (len < 0) {
                        _hs_error("error filling stream from file: %s",
                                  strerror(errno));
                        return HS_IO_ERROR;
                }
                stream->avail_in = len;
                stream->next_in = buf;
        }

        return HS_OK;
}


/*
 * The stream is already using BUF for an output buffer, and probably
 * contains some buffered output now.  Write this out to F, and reset
 * the buffer cursor.
 */
enum hs_result _hs_drain_to_file(hs_stream_t *stream,
                                 char *buf, size_t buf_len,
                                 FILE *f)
{
        int present;

        /* This is only allowed if either the stream has no output buffer
         * yet, or that buffer could possibly be BUF. */
        if (stream->next_out == NULL) {
                assert(stream->avail_out == 0);
                
                stream->next_out = buf;
                stream->avail_out = buf_len;
                
                return HS_OK;
        }
        
        assert(stream->avail_out <= buf_len);
        assert(stream->next_out >= buf);
        assert(stream->next_out <= buf + buf_len);

        present = stream->next_out - buf;
        if (present > 0) {
                int result;
                
                assert(present > 0);

                result = fwrite(buf, 1, present, f);
                if (present != result) {
                        _hs_error("error draining stream to file: %s",
                                  strerror(errno));
                        return HS_IO_ERROR;
                }

                stream->next_out = buf;
                stream->avail_out = buf_len;
        }
        
        return HS_OK;
}
