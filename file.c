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
#include <errno.h>
#include <string.h>

#include "hsync.h"
#include "util.h"
#include "stream.h"
#include "trace.h"
#include "streamfile.h"
#include "sumset.h"
#include "hsyncfile.h"


int hs_inbuflen = 500, hs_outbuflen = 600;

static const int HS_PATCH_FILE_TAG = 201214,
        HS_MKSUM_FILE_TAG = 201215;

typedef struct hs_file {
        int tag;
        FILE *basis_file, *in_file, *out_file;

        char *buf;
        size_t buf_len;
        
        hs_stream_t *stream;

        /* one of the following: */
        hs_patch_job_t *patch_job;
        hs_mksum_job_t *mksum_job;
} hs_file_t;


/*
 * Extract from a void pointer, and check the dogtag.
 */
static hs_file_t *_hs_file_check(void *p, int tag) {
        hs_file_t *pf = (hs_file_t *) p;
        assert(pf->tag == tag);
        return pf;
}


static hs_file_t *_hs_file_new(size_t buf_len) {
        hs_file_t *pf = _hs_alloc_struct(hs_file_t);
        pf->stream = _hs_alloc_struct(hs_stream_t);
	hs_stream_init(pf->stream);

        pf->buf = _hs_alloc(buf_len, "file buffer");
        pf->buf_len = buf_len;

        return pf;
}


/*
 * Open a new hsync file which will apply a patch.  As you read from
 * the file using hs_read(), you'll receive parts of the new file.
 */
HSFILE *hs_patch_open(FILE *basis_file, FILE *delta_file)
{
        hs_file_t *pf;

        pf = _hs_file_new(hs_inbuflen);
        
        pf->tag = HS_PATCH_FILE_TAG;
        pf->basis_file = basis_file;
        pf->in_file = delta_file;

	pf->patch_job = hs_patch_begin(pf->stream, hs_file_copy_cb, basis_file);

        return pf;
}



/*
 * Open a file to write out the signature of caller-supplied data.
 */
HSFILE *hs_mksum_open(FILE *sig_file, int block_len, int strong_sum_len)
{
        hs_file_t *pf = _hs_file_new(hs_outbuflen);

        pf->tag = HS_MKSUM_FILE_TAG;
        pf->out_file = sig_file;
        pf->mksum_job = hs_mksum_begin(pf->stream, block_len, strong_sum_len);

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
        hs_file_t *pf = _hs_file_check(f, HS_PATCH_FILE_TAG);
        enum hs_result result;

        pf->stream->next_out = buf;
        pf->stream->avail_out = *len;
        
	do {
		_hs_fill_from_file(pf->stream, pf->buf, pf->buf_len,
                                   pf->in_file);
		
		result = hs_patch_iter(pf->patch_job);
                
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
        assert(pf->stream->next_out >= (char *) buf);
        *len = pf->stream->next_out - (char *) buf;
        _hs_trace("returns %d bytes: %s", *len, hs_strerror(result));

	return result;
}



enum hs_result hs_mksum_write(HSFILE *f, void *buf, size_t len)
{
        hs_file_t *pf = _hs_file_check(f, HS_MKSUM_FILE_TAG);
        enum hs_result result, io_result;

        pf->stream->next_in = buf;
        pf->stream->avail_in = len;

        do { 
                result = hs_mksum_iter(pf->mksum_job, 0);
                
                io_result = _hs_drain_to_file(pf->stream, pf->buf, pf->buf_len,
                                              pf->out_file);
        
                if (io_result != HS_OK)
                        return result;
        } while (result == HS_BLOCKED && pf->stream->avail_in > 0);

        _hs_trace("returns %s(%d)", hs_strerror(result), result);

        return result;
}


/*
 * Close off a patch file.  If the patch has not finished, then the
 * rest of the data is just lost.  The files used are not closed.
 */
enum hs_result hs_patch_close(HSFILE *f)
{
        hs_file_t *pf = _hs_file_check(f, HS_PATCH_FILE_TAG);
        if (pf->buf)
                free(pf->buf);
        hs_patch_finish(pf->patch_job);
        return HS_OK;
}



enum hs_result hs_mksum_close(HSFILE *f)
{
        hs_file_t *pf = _hs_file_check(f, HS_MKSUM_FILE_TAG);
        enum hs_result result, io_result;

        pf->stream->next_in = 0;
        pf->stream->avail_in = 0;

        /* Continue to run until all stream data has drained; then
         * deallocate and leave. */
        do {
                result = hs_mksum_iter(pf->mksum_job, 1);
                
                io_result = _hs_drain_to_file(pf->stream, pf->buf, pf->buf_len,
                                              pf->out_file);
                
                if (io_result != HS_OK)
                        return result;
        } while (result == HS_BLOCKED);
        
        if (pf->buf)
                free(pf->buf);
        hs_mksum_finish(pf->mksum_job);
        return HS_OK;
}



/*
 * Default copy implementation that retrieves a part of a stdio file.
 */
enum hs_result hs_file_copy_cb(void *arg, size_t *len, void **buf)
{
        int got;

        got = fread(*buf, 1, *len, (FILE *) arg);
        if (got == -1) {
                _hs_error(strerror(errno));
                return HS_IO_ERROR;
        } else if (got == 0) {
                _hs_error("unexpected eof");
                return HS_SHORT_STREAM;
        } else {
                *len = got;
                return HS_OK;
        }
}
