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

#include <config.h>

#ifdef HAVE_STDINT_H
#include <stdint.h>
#endif

#include <assert.h>
#include <stdlib.h>
#include <limits.h>

#include "hsync.h"
#include "private.h"
#include "util.h"
#include "file.h"
#include "stream.h"

void hs_mksum_files(int in_fd, int out_fd,
                    int block_len, int inbuflen, int outbuflen)
{
    hs_nozzle_t *in_iobuf, *out_iobuf;
    hs_stream_t stream;
    int input_done = 0, output_done = 0;
    hs_mksum_job_t *job;

    hs_stream_init(&stream);

    in_iobuf = hs_nozzle_new(in_fd, &stream, inbuflen, 'r');
    out_iobuf = hs_nozzle_new(out_fd, &stream, outbuflen, 'w');

    job = hs_mksum_begin(&stream, block_len, DEFAULT_SUM_LENGTH);
    
    do {
        if (!input_done)
            input_done = !hs_nozzle_in(in_iobuf);
        hs_mksum_iter(job);
        output_done = !hs_nozzle_out(out_iobuf);
    } while (!input_done || !output_done);
    
    hs_nozzle_delete(in_iobuf);
    hs_nozzle_delete(out_iobuf);
}



void hs_mdfour_file(int in_fd, byte_t *result, int inbuflen)
{
    hs_nozzle_t *in_iobuf;
    hs_stream_t stream;
    int input_done = 0;
    hs_mdfour_t sum;

    hs_stream_init(&stream);

    in_iobuf = hs_nozzle_new(in_fd, &stream, inbuflen, 'r');

    hs_mdfour_begin(&sum);

    do {
        input_done = !hs_nozzle_in(in_iobuf);
        hs_mdfour_update(&sum, stream.next_in, stream.avail_in);
        stream.next_in += stream.avail_in;
        stream.avail_in = 0;
    } while (!input_done);
    hs_nozzle_delete(in_iobuf);

    hs_mdfour_result(&sum, result);
}


/*
 * Copy until EOF.
 */
void _hs_stream_copy_file(hs_stream_t *stream, hs_nozzle_t *in_iobuf, hs_nozzle_t *out_iobuf)
{
    int seen_eof = 0, done_output;
    do {
        if (!seen_eof)
            seen_eof = !hs_nozzle_in(in_iobuf);
        done_output = hs_nozzle_out(out_iobuf);
        _hs_stream_copy(stream, INT_MAX);
    } while (!seen_eof || done_output);
}
