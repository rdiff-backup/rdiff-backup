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
                               | Is it possible that software is not
                               | like anything else, that it is meant
                               | to be discarded: that the whole point
                               | is to always see it as a soap bubble?
                               |        -- Alan Perlis
                               */



#include <config.h>

#include <assert.h>
#include <stdlib.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>
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
 * The job should already be set up, and must be free by the caller
 * after return.
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

    if (in_file)
        in_fb = hs_filebuf_new(in_file, stream, hs_inbuflen);

    if (out_file)
        out_fb = hs_filebuf_new(out_file, stream, hs_outbuflen);

    do {
        if (!stream->eof_in && in_fb) {
            iores = hs_infilebuf_fill(in_fb);
            if (iores != HS_DONE)
                return iores;
        }

        result = hs_job_iter(job);
        if (result != HS_DONE  &&  result != HS_BLOCKED)
            return result;

        if (out_fb) {
            iores = hs_outfilebuf_drain(out_fb);
            if (iores != HS_DONE)
                return iores;
        }
    } while (result != HS_DONE);

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
    hs_job_t            *job;
    hs_stream_t         stream;
    hs_result           r;

    hs_stream_init(&stream);

    job = hs_loadsig_begin(&stream, sumset);
    r = hs_whole_run(job, sig_file, NULL);
    hs_job_free(job);

    return r;
}



hs_result
hs_delta_file(hs_signature_t *sig, FILE *new_file, FILE *delta_file, hs_stats_t *stats)
{
    hs_job_t            *job;
    hs_stream_t         stream;
    hs_result           r;

    hs_stream_init(&stream);
    job = hs_delta_begin(&stream, sig);

    r = hs_whole_run(job, new_file, delta_file);

    if (stats)
        memcpy(stats, &job->stats, sizeof *stats);

    hs_job_free(job);

    return r;
}



hs_result hs_patch_file(FILE *basis_file, FILE *delta_file, FILE *new_file, hs_stats_t *stats)
{
    hs_job_t            *job;
    hs_stream_t         stream;
    hs_result           r;

    hs_stream_init(&stream);
    job = hs_patch_begin(&stream, hs_file_copy_cb, basis_file);

    r = hs_whole_run(job, delta_file, new_file);
    
    if (stats)
        memcpy(stats, &job->stats, sizeof *stats);

    hs_job_free(job);

    return r;
}
