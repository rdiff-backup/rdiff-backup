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
 * file.c -- This looks after the high-level, stdio-flavoured
 * interface.
 */


                              /*
                               * "You know, it'd be much cheaper if
                               * you flew on the 25th of December."
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

static const int HS_PATCH_FILE_TAG = 201214;

typedef struct hs_file {
        int tag;
        FILE *basis_file, *in_file;
	char *in_buf;
        hs_stream_t *stream;
        hs_patch_job_t *job;
} hs_file_t;


/*
 * Extract from a void pointer, and check the dogtag.
 */
static hs_file_t *_hs_patch_file_check(void *p) {
        hs_file_t *pf = (hs_file_t *) p;
        assert(pf->tag == HS_PATCH_FILE_TAG);
        return pf;
}


/*
 * Open a new hsync file which will apply a patch.  As you read from
 * the file using hs_read(), you'll receive parts of the new file.
 */
HSFILE *hs_patch_open(FILE *basis_file, FILE *delta_file)
{
        hs_file_t *pf;

        pf = _hs_alloc_struct(hs_file_t);
        
        pf->tag = HS_PATCH_FILE_TAG;
        pf->basis_file = basis_file;
        pf->in_file = delta_file;
        pf->stream = _hs_alloc_struct(hs_stream_t);

        pf->in_buf = _hs_alloc(hs_inbuflen, "delta input buffer");

	hs_stream_init(pf->stream);
	pf->job = hs_patch_begin(pf->stream);

        return pf;
}



/*
 * Read up to *LEN bytes from PF.  At end of file, return HS_OK; if
 * the patch is not yet complete returns HS_BLOCKED; if an error
 * occurred returns an appropriate code.  Adjusts LEN to show how much
 * was actually read.
 */
enum hs_result hs_patch_read(HSFILE *f, void *buf, size_t *len)
{
        hs_file_t *pf = _hs_patch_file_check(f);
        enum hs_result result;

        pf->stream->next_out = buf;
        pf->stream->avail_out = *len;
        
	do {
		_hs_fill_from_file(pf->stream, pf->in_buf, hs_inbuflen,
                                   pf->in_file);
		
		result = hs_patch_iter(pf->job);
                
		if (result == HS_BLOCKED && feof(pf->in_file) &&
                    !pf->stream->avail_in) {
                        /* The library wants more input, but it has
                         * none in its internal buffer and we're at
                         * the end of the file.  Therefore the delta
                         * must have been truncated. */
			result = HS_SHORT_STREAM;
                }
	} while (result == HS_BLOCKED);

        /* Return the amount of output actually available. */
        *len = hs_outbuflen - pf->stream->avail_out;

	return result;
}
