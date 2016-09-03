/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- the library for network deltas
 *
 * Copyright 2000, 2001, 2014, 2015 by Martin Pool <mbp@sourcefrog.net>
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



#include "config.h"

#include <assert.h>
#include <stdlib.h>
#ifdef HAVE_UNISTD_H
#include <unistd.h>
#endif
#include <stdio.h>
#include <string.h>
#include <errno.h>

#include "librsync.h"

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
    rs_buffers_t    buf;
    rs_result       result;
    rs_filebuf_t    *in_fb = NULL, *out_fb = NULL;

    if (in_file)
        in_fb = rs_filebuf_new(in_file, rs_inbuflen);

    if (out_file)
        out_fb = rs_filebuf_new(out_file, rs_outbuflen);

    result = rs_job_drive(job, &buf,
                          in_fb ? rs_infilebuf_fill : NULL, in_fb,
                          out_fb ? rs_outfilebuf_drain : NULL, out_fb);

    if (in_fb)
        rs_filebuf_free(in_fb);

    if (out_fb)
        rs_filebuf_free(out_fb);

    return result;
}



rs_result
rs_sig_file(FILE *old_file, FILE *sig_file, size_t new_block_len,
            size_t strong_len,
	    rs_magic_number sig_magic,
	    rs_stats_t *stats)
{
    rs_job_t        *job;
    rs_result       r;

    job = rs_sig_begin(new_block_len, strong_len, sig_magic);
    r = rs_whole_run(job, old_file, sig_file);
    if (stats)
        memcpy(stats, &job->stats, sizeof *stats);
    rs_job_free(job);

    return r;
}


rs_result
rs_loadsig_file(FILE *sig_file, rs_signature_t **sumset, rs_stats_t *stats)
{
    rs_job_t            *job;
    rs_result           r;

    job = rs_loadsig_begin(sumset);

    /* Estimate a number of signatures by file size */
    rs_get_filesize(sig_file, &job->sig_file_bytes);

    r = rs_whole_run(job, sig_file, NULL);
    if (stats)
        memcpy(stats, &job->stats, sizeof *stats);
    rs_job_free(job);

    return r;
}



rs_result
rs_delta_file(rs_signature_t *sig, FILE *new_file, FILE *delta_file,
              rs_stats_t *stats)
{
    rs_job_t            *job;
    rs_result           r;

    job = rs_delta_begin(sig);

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
    rs_result           r;

    job = rs_patch_begin(rs_file_copy_cb, basis_file);

    r = rs_whole_run(job, delta_file, new_file);
    
    if (stats)
        memcpy(stats, &job->stats, sizeof *stats);

    rs_job_free(job);

    return r;
}
