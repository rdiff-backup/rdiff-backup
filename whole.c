/*=                                     -*- c-file-style: "linux" -*-
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
                               * Is it possible that software is not
                               * like anything else, that it is meant
                               * to be discarded: that the whole point
                               * is to always see it as a soap bubble?
                               *        -- Alan Perlis
                               */



/*
 * whole.c -- This module contains routines for processing whole files
 * at a time.  These are normally called from rdiff, but if for some
 * reason you should want that functionality in your application here
 * they are.
 */

#include <config.h>

#include <assert.h>
#include <sys/types.h>
#include <stdlib.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>

#include <errno.h>

#include "trace.h"
#include "fileutil.h"
#include "hsync.h"
#include "hsyncfile.h"
#include "job.h"
#include "buf.h"
#include "whole.h"

/*
 * Run a job continuously, with input to/from the two specified files.
 * The job should already be set up, and it is freed before the
 * function returns.
 */
hs_result
hs_whole_run(hs_job_t *job, FILE *in_file, FILE *out_file)
{
        hs_stream_t     *stream = job->stream;
        hs_result       result, iores;
        hs_filebuf_t    *in_fb, *out_fb;
        int             ending = 0;

        in_fb = in_file ? hs_filebuf_new(in_file, stream, hs_inbuflen) : NULL;
        
        out_fb = out_file ? hs_filebuf_new(out_file, stream, hs_outbuflen)
                : NULL;

        do {
                if (in_fb) {
                        iores = hs_infilebuf_fill(in_fb, &ending);
                        if (iores != HS_OK)
                                return iores;
                }

                result = hs_job_iter(job, ending);
                if (result != HS_OK  &&  result != HS_BLOCKED)
                        return result;

                if (out_fb) {
                        iores = hs_outfilebuf_drain(out_fb);
                        if (iores != HS_OK)
                                return iores;
                }
        } while (result != HS_OK);

        hs_job_free(job);
                
        return result;
}



/*
 * Generate the signature of OLD_FILE, and write it to SIG_FILE.  The
 * generated signature will be for blocks of NEW_BLOCK_LEN bytes, and
 * the strong sum is truncated to STRONG_LEN.
 */
hs_result
hs_whole_signature(FILE *old_file, FILE *sig_file, size_t new_block_len,
                   size_t strong_len)
{
        hs_job_t        *job;
        hs_stream_t     stream;

        hs_stream_init(&stream);
        job = hs_mksum_begin(&stream, new_block_len, strong_len);

        return hs_whole_run(job, old_file, sig_file);

        hs_job_free(job);
}


/*
 * Load signatures from SIG_FILE into memory.  Return a pointer to the
 * newly allocated structure in SUMSET.
 */
hs_result
hs_file_readsums(FILE *sig_file, hs_sumset_t **sumset)
{
        hs_job_t        *job;
        hs_stream_t     stream;

        hs_stream_init(&stream);

        job = hs_readsum_begin(&stream, sumset);
        return hs_whole_run(job, sig_file, NULL);
}
