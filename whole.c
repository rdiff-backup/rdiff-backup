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
                               * Is it possible that software is not
                               * like anything else, that it is meant
                               * to be discarded: that the whole point
                               * is to always see it as a soap bubble?
                               *        -- Alan Perlis
                               */



#include <config.h>

#include <assert.h>
#include <sys/types.h>
#include <stdlib.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>

#include <errno.h>

#include "trace.h"
#include "fileutil.h"
#include "hsync.h"
#include "hsyncfile.h"
#include "sumset.h"
#include "job.h"
#include "buf.h"
#include "whole.h"

/**
 * Run a job continuously, with input to/from the two specified files.
 * The job should already be set up, and it is freed when the function
 * returns.
 *
 * Buffers of ::hs_inbuflen and ::hs_outbuflen are allocated for
 * temporary storage.
 *
 * \param in_file Source of input bytes, or NULL if the input buffer
 * should not be filled.
 *
 * \return HS_DONE if the job completed, or otherwise an error result.
 */
hs_result
hs_whole_run(hs_job_t *job, FILE *in_file, FILE *out_file)
{
    hs_stream_t     *stream = job->stream;
    hs_result       result, iores;
    hs_filebuf_t    *in_fb = NULL, *out_fb = NULL;
    int             ending = 0;

    if (in_file)
        in_fb = hs_filebuf_new(in_file, stream, hs_inbuflen);

    if (out_file)
        out_fb = hs_filebuf_new(out_file, stream, hs_outbuflen);

    do {
        if (in_fb) {
            iores = hs_infilebuf_fill(in_fb, &ending);
            if (iores != HS_DONE)
                return iores;
        }

        result = hs_job_iter(job, ending);
        if (result != HS_DONE  &&  result != HS_BLOCKED)
            return result;

        if (out_fb) {
            iores = hs_outfilebuf_drain(out_fb);
            if (iores != HS_DONE)
                return iores;
        }
    } while (result != HS_DONE);

    /* FIXME: At the moment we leak if there's an IO error.  That's no
     * good. */
    hs_job_free(job);
                
    return result;
}



/**
 * Generate the signature of a basis file, and write it out to
 * another.
 *
 * \param new_block_len block size for signature generation, in bytes
 * 
 * \param strong_len truncated length of strong checksums, in bytes
 *
 * \sa hs_sig_begin()
 */
hs_result
hs_sig_file(FILE *old_file, FILE *sig_file, size_t new_block_len,
            size_t strong_len)
{
        hs_job_t        *job;
        hs_stream_t     stream;
        hs_result       r;

        hs_stream_init(&stream);
        job = hs_sig_begin(&stream, new_block_len, strong_len);

        r = hs_whole_run(job, old_file, sig_file);

        hs_job_free(job);

        return r;
}


/**
 * Load signatures from a signature file into memory.  Return a
 * pointer to the newly allocated structure in SUMSET.
 *
 * \sa hs_readsig_begin()
 */
hs_result
hs_loadsig_file(FILE *sig_file, hs_signature_t **sumset)
{
        hs_job_t        *job;
        hs_stream_t     stream;

        hs_stream_init(&stream);

        job = hs_loadsig_begin(&stream, sumset);
        return hs_whole_run(job, sig_file, NULL);
}



hs_result
hs_delta_file(hs_signature_t *sumset, FILE *new_file, FILE *delta_file)
{
    hs_error("not implemented at the moment");

    return HS_UNIMPLEMENTED;
}
