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
                                * It was a cold and lonely winter
                                */

#include "config.h"

#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <stdint.h>
#include <limits.h>

#include "hsync.h"
#include "util.h"
#include "file.h"
#include "stream.h"
#include "trace.h"
#include "streamfile.h"
#include "sumset.h"


int hs_inbuflen = 500, hs_outbuflen = 600;


void hs_mksum_files(FILE *in_file, FILE *out_file, int block_len)
{
	_hs_fatal("not implemented!");
}



/*
 * Calculate a delta between two files; write the results to OUT_FILE.
 */
void hs_delta_files(FILE *new_file, FILE *delta_file)
{
	_hs_fatal("not implemented!");
}


/*
 * Copy until EOF.  This is only used for testing.
 */
int _hs_stream_copy_file(hs_stream_t *stream, FILE *in_file, FILE *out_file)
{
	char *in_buf, *out_buf;
	
	in_buf = _hs_alloc(hs_inbuflen, "stream copy input buffer");
	out_buf = _hs_alloc(hs_outbuflen, "stream copy output buffer");

	do {
		_hs_fill_from_file(stream, in_buf, hs_inbuflen, in_file);
		_hs_stream_copy(stream, INT_MAX);
		_hs_drain_to_file(stream, out_buf, hs_outbuflen, out_file);
	} while (!feof(in_file) || stream->avail_in);

	free(in_buf);
	free(out_buf);

	return HS_OK;
}


/*
 * Apply a patch from DELTA to BASIS and write output to NEW
 */
int hs_patch_files(FILE *basis_file, FILE *delta_file,
		   FILE *out_file)
{
	void *delta_buf, *out_buf;
	hs_stream_t stream;
	int input_done = 0, result;
	hs_patch_job_t *job;

	delta_buf = _hs_alloc(hs_inbuflen, "delta input buffer");
	out_buf = _hs_alloc(hs_outbuflen, "patch output buffer");

	hs_stream_init(&stream);
	job = hs_patch_begin(&stream);

	do {
		_hs_fill_from_file(&stream, delta_buf, hs_inbuflen, delta_file);
		
		result = hs_patch_iter(job);
		if (result == HS_BLOCKED && feof(delta_file) && !stream.avail_in)
			result = HS_SHORT_STREAM;

		_hs_drain_to_file(&stream, out_buf, hs_outbuflen, out_file);
	} while (result == HS_BLOCKED);

        _hs_trace("file patch concluded with result %d", result);

	free(delta_buf);
	free(out_buf);

	return result;
}



void hs_mdfour_file(FILE *in_file, char *result)
{
	_hs_fatal("not implemented any more");
}


