/*=                                     -*- c-file-style: "bsd" -*-
 *
 * libhsync -- dynamic caching and delta update in HTTP
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
                                         * It was a cold and lonely winter
                                         */

#include "config.h"

#ifdef HAVE_STDINT_H
#include <stdint.h>
#endif

#include <assert.h>
#include <stdlib.h>
#include <limits.h>
#include <stdarg.h>
#include <stdio.h>

#include "hsync.h"
#include "private.h"
#include "util.h"
#include "file.h"
#include "stream.h"
#include "trace.h"
#include "nozzle.h"


int hs_inbuflen = 500, hs_outbuflen = 600;



void hs_mksum_files(FILE *in_file, FILE *out_file, int block_len)
{
    hs_nozzle_t *in_nozzle, *out_nozzle;
    hs_stream_t stream;
    int input_done = 0, output_done = 0;
    hs_mksum_job_t *job;

    hs_stream_init(&stream);

    in_nozzle = _hs_nozzle_new(in_file, &stream, hs_inbuflen, "r");
    out_nozzle = _hs_nozzle_new(out_file, &stream, hs_outbuflen, "w");

    job = hs_mksum_begin(&stream, block_len, DEFAULT_SUM_LENGTH);
    
    do {
        if (!input_done)
            input_done = !_hs_nozzle_in(in_nozzle);
        hs_mksum_iter(job);
        output_done = !_hs_nozzle_out(out_nozzle);
    } while (!input_done || !output_done);
    
    _hs_nozzle_delete(in_nozzle);
    _hs_nozzle_delete(out_nozzle);
}



/*
 * Calculate a delta between two files; write the results to OUT_FILE.
 */
void hs_delta_files(FILE *new_file, FILE *delta_file)
{
    hs_nozzle_t *in_nozzle, *out_nozzle;
    hs_stream_t stream;
    int input_done = 0, result;

    hs_stream_init(&stream);

    in_nozzle = _hs_nozzle_new(new_file, &stream, hs_inbuflen, "r");
    out_nozzle = _hs_nozzle_new(delta_file, &stream, hs_outbuflen, "w");

    hs_delta_begin(&stream);
    
    do {
        if (!input_done)
            input_done = !_hs_nozzle_in(in_nozzle);
        result = hs_delta(&stream, input_done);
	_hs_nozzle_out(out_nozzle);
    } while (!input_done || !_hs_stream_is_empty(&stream));
    
    _hs_nozzle_delete(in_nozzle);
    _hs_nozzle_delete(out_nozzle);
}



void hs_mdfour_file(FILE *in_file, char *result)
{
    hs_nozzle_t *in_nozzle;
    hs_stream_t stream;
    int input_done = 0;
    hs_mdfour_t sum;

    hs_stream_init(&stream);

    in_nozzle = _hs_nozzle_new(in_file, &stream, hs_inbuflen, "r");

    hs_mdfour_begin(&sum);

    do {
        input_done = !_hs_nozzle_in(in_nozzle);
        hs_mdfour_update(&sum, stream.next_in, stream.avail_in);
        stream.next_in += stream.avail_in;
        stream.avail_in = 0;
    } while (!input_done);
    _hs_nozzle_delete(in_nozzle);

    hs_mdfour_result(&sum, result);
}


