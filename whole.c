/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- the library for network deltas
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

#include <rsync.h>

#include "trace.h"
#include "fileutil.h"
#include "sumset.h"
#include "job.h"
#include "buf.h"
#include "whole.h"
#include "util.h"

/**
 * Run a job continuously, with input to/from the two specified files.
 * The job should already be set up, and must be free by the caller
 * after return.
 *
 * Buffers of ::rs_inbuflen and ::rs_outbuflen are allocated for
 * temporary storage.
 *
 * \param in_file Source of input bytes, or NULL if the input buffer
 * should not be filled.
 *
 * \return RS_DONE if the job completed, or otherwise an error result.
 */
rs_result
rs_whole_run(rs_job_t *job, FILE *in_file, FILE *out_file)
{
    rs_stream_t     *stream = job->stream;
    rs_result       result, iores;
    rs_filebuf_t    *in_fb = NULL, *out_fb = NULL;

    rs_bzero(stream, sizeof *stream);

    if (in_file)
        in_fb = rs_filebuf_new(in_file, stream, rs_inbuflen);

    if (out_file)
        out_fb = rs_filebuf_new(out_file, stream, rs_outbuflen);

    do {
        if (!stream->eof_in && in_fb) {
            iores = rs_infilebuf_fill(in_fb);
            if (iores != RS_DONE)
                return iores;
        }

        result = rs_job_iter(job);
        if (result != RS_DONE  &&  result != RS_BLOCKED)
            return result;

        if (out_fb) {
            iores = rs_outfilebuf_drain(out_fb);
            if (iores != RS_DONE)
                return iores;
        }
    } while (result != RS_DONE);

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
 * \sa rs_sig_begin()
 */
rs_result
rs_sig_file(FILE *old_file, FILE *sig_file, size_t new_block_len,
            size_t strong_len)
{
    rs_job_t        *job;
    rs_stream_t     stream;
    rs_result       r;

    job = rs_sig_begin(&stream, new_block_len, strong_len);
    r = rs_whole_run(job, old_file, sig_file);
    rs_job_free(job);

    return r;
}


/**
 * Load signatures from a signature file into memory.  Return a
 * pointer to the newly allocated structure in SUMSET.
 *
 * \sa rs_readsig_begin()
 */
rs_result
rs_loadsig_file(FILE *sig_file, rs_signature_t **sumset)
{
    rs_job_t            *job;
    rs_stream_t         stream;
    rs_result           r;

    rs_bzero(&stream, sizeof stream);
    job = rs_loadsig_begin(&stream, sumset);
    r = rs_whole_run(job, sig_file, NULL);
    rs_job_free(job);

    return r;
}



rs_result
rs_delta_file(rs_signature_t *sig, FILE *new_file, FILE *delta_file,
              rs_stats_t *stats)
{
    rs_job_t            *job;
    rs_stream_t         stream;
    rs_result           r;

    rs_bzero(&stream, sizeof stream);
    job = rs_delta_begin(&stream, sig);

    r = rs_whole_run(job, new_file, delta_file);

    if (stats)
        memcpy(stats, &job->stats, sizeof *stats);

    rs_job_free(job);

    return r;
}



rs_result rs_patch_file(FILE *basis_file, FILE *delta_file, FILE *new_file,
                        rs_stats_t *stats)
{
    rs_job_t            *job;
    rs_stream_t         stream;
    rs_result           r;

    rs_bzero(&stream, sizeof stream);
    job = rs_patch_begin(&stream, rs_file_copy_cb, basis_file);

    r = rs_whole_run(job, delta_file, new_file);
    
    if (stats)
        memcpy(stats, &job->stats, sizeof *stats);

    rs_job_free(job);

    return r;
}
