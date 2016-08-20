/*=                     -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- the library for network deltas
 *
 * Copyright (C) 1999, 2000, 2001 by Martin Pool <mbp@sourcefrog.net>
 * Copyright (C) 1999 by Andrew Tridgell <tridge@samba.org>
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


/**
 * \file readsums.c
 * \brief Load signatures from a file.
 */

#include "config.h"

#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#include "librsync.h"
#include "sumset.h"
#include "job.h"
#include "trace.h"
#include "netint.h"
#include "util.h"
#include "stream.h"


static rs_result rs_loadsig_s_weak(rs_job_t *job);
static rs_result rs_loadsig_s_strong(rs_job_t *job);



/**
 * Add a just-read-in checksum pair to the signature block.
 */
static rs_result rs_loadsig_add_sum(rs_job_t *job, rs_strong_sum_t *strong)
{
    size_t              new_size;
    rs_signature_t      *sig = job->signature;
    rs_block_sig_t      *asignature;

    sig->count++;
    if (sig->count > job->estimated_signature_count) {

        job->estimated_signature_count = sig->count;
        new_size = sig->count * sizeof(rs_block_sig_t);

        sig->block_sigs = realloc(sig->block_sigs, new_size);
    }

    if (sig->block_sigs == NULL) {
        return RS_MEM_ERROR;
    }
    asignature = &(sig->block_sigs[sig->count - 1]);

    asignature->weak_sum = job->weak_sig;
    asignature->i = sig->count;

    memcpy(asignature->strong_sum, strong, sig->strong_sum_len);

    if (rs_trace_enabled()) {
        char                hexbuf[RS_MAX_STRONG_SUM_LENGTH * 2 + 2];
        rs_hexify(hexbuf, strong, sig->strong_sum_len);

        rs_trace("read in checksum: weak=%#x, strong=%s", asignature->weak_sum,
                 hexbuf);
    }

    job->stats.sig_blocks++;

    return RS_RUNNING;
}


static rs_result rs_loadsig_s_weak(rs_job_t *job)
{
    int                 l;
    rs_result           result;

    result = rs_suck_n4(job, &l);
    if (result == RS_DONE)
        ;
    else if (result == RS_INPUT_ENDED) /* ending here is OK */
        return RS_DONE;
    else
        return result;

    job->weak_sig = l;

    job->statefn = rs_loadsig_s_strong;

    return RS_RUNNING;
}



static rs_result rs_loadsig_s_strong(rs_job_t *job)
{
    rs_result           result;
    rs_strong_sum_t     *strongsum;

    result = rs_scoop_read(job, job->signature->strong_sum_len,
                           (void **) &strongsum);
    if (result != RS_DONE) return result;

    job->statefn = rs_loadsig_s_weak;

    return rs_loadsig_add_sum(job, strongsum);
}



static rs_result rs_loadsig_s_stronglen(rs_job_t *job)
{
    int                 l;
    rs_result           result;

    if ((result = rs_suck_n4(job, &l)) != RS_DONE)
        return result;
    job->strong_sum_len = l;
    
    if (l < 0  ||  l > RS_MAX_STRONG_SUM_LENGTH) {
        rs_error("strong sum length %d is implausible", l);
        return RS_CORRUPT;
    }

    job->signature->block_len = job->block_len;
    job->signature->strong_sum_len = job->strong_sum_len;
    
    rs_trace("allocated sigset_t (strong_sum_len=%d, block_len=%d)",
             (int) job->strong_sum_len, (int) job->block_len);

    job->statefn = rs_loadsig_s_weak;
    
    /* Estimate the number of blocks stored in signature */
    /* Magic+header is 12 bytes,
       each block thereafter is 4 bytes weak_sum+strong_sum_len bytes */
    if ((job->estimated_signature_count == 0) && (job->sig_file_bytes > 0)) {
        job->estimated_signature_count = (job->sig_file_bytes-12)/(4+job->strong_sum_len);
        rs_trace("estimating %d blocks in signature (%d bytes)",
            job->estimated_signature_count, job->estimated_signature_count*sizeof(rs_block_sig_t));
    }

    /* Allocate memory for signature sums */
    if (job->estimated_signature_count > 0) {
        job->signature->block_sigs = calloc(job->estimated_signature_count, sizeof(rs_block_sig_t));
        if (job->signature->block_sigs == NULL) {
            job->estimated_signature_count = 0;
            return RS_MEM_ERROR;
        }
    }

    return RS_RUNNING;
}


static rs_result rs_loadsig_s_blocklen(rs_job_t *job)
{
    int                 l;
    rs_result           result;

    if ((result = rs_suck_n4(job, &l)) != RS_DONE)
        return result;
    job->block_len = l;

    if (job->block_len < 1) {
        rs_error("block length of %d is bogus", (int) job->block_len);
        return RS_CORRUPT;
    }

    job->statefn = rs_loadsig_s_stronglen;
    job->stats.block_len = job->block_len;
        
    return RS_RUNNING;
}


static rs_result rs_loadsig_s_magic(rs_job_t *job)
{
    int                 l;
    rs_result           result;

    if ((result = rs_suck_n4(job, &l)) != RS_DONE) {
        return result;
    }

    switch(l) {
        case RS_MD4_SIG_MAGIC:
        case RS_BLAKE2_SIG_MAGIC:
            job->magic = job->signature->magic = l;
            rs_trace("got signature magic %#10x", l);
            break;
	default:
            rs_error("wrong magic number %#10x for signature", l);
            return RS_BAD_MAGIC;
    }

    job->statefn = rs_loadsig_s_blocklen;

    return RS_RUNNING;
}


rs_job_t *rs_loadsig_begin(rs_signature_t **signature)
{
    rs_job_t *job;

    job = rs_job_new("loadsig", rs_loadsig_s_magic);
    *signature = job->signature = rs_alloc_struct(rs_signature_t);
    job->signature->count = 0;

    return job;
}
