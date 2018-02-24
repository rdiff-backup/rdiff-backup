/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
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

/** \file readsums.c Load signatures from a file. */

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

/** Add a just-read-in checksum pair to the signature block. */
static rs_result rs_loadsig_add_sum(rs_job_t *job, rs_strong_sum_t *strong)
{
    rs_signature_t *sig = job->signature;

    if (rs_trace_enabled()) {
        char hexbuf[RS_MAX_STRONG_SUM_LENGTH * 2 + 2];
        rs_hexify(hexbuf, strong, sig->strong_sum_len);
        rs_trace("got block: weak=" FMT_WEAKSUM ", strong=%s", job->weak_sig,
                 hexbuf);
    }
    rs_signature_add_block(job->signature, job->weak_sig, strong);
    job->stats.sig_blocks++;
    return RS_RUNNING;
}

static rs_result rs_loadsig_s_weak(rs_job_t *job)
{
    int l;
    rs_result result;

    if ((result = rs_suck_n4(job, &l)) != RS_DONE) {
        if (result == RS_INPUT_ENDED)   /* ending here is OK */
            return RS_DONE;
        return result;
    }
    job->weak_sig = l;
    job->statefn = rs_loadsig_s_strong;
    return RS_RUNNING;
}

static rs_result rs_loadsig_s_strong(rs_job_t *job)
{
    rs_result result;
    rs_strong_sum_t *strongsum;

    if ((result =
         rs_scoop_read(job, job->signature->strong_sum_len,
                       (void **)&strongsum)) != RS_DONE)
        return result;
    job->statefn = rs_loadsig_s_weak;
    return rs_loadsig_add_sum(job, strongsum);
}

static rs_result rs_loadsig_s_stronglen(rs_job_t *job)
{
    int l;
    rs_result result;

    if ((result = rs_suck_n4(job, &l)) != RS_DONE)
        return result;
    if (l < 0 || l > RS_MAX_STRONG_SUM_LENGTH) {
        rs_error("strong sum length %d is implausible", l);
        return RS_CORRUPT;
    }
    rs_trace("got strong sum length %d", l);
    job->sig_strong_len = l;
    /* Initialize the signature. */
    if ((result =
         rs_signature_init(job->signature, job->sig_magic, job->sig_block_len,
                           job->sig_strong_len, job->sig_fsize)) != RS_DONE)
        return result;
    job->statefn = rs_loadsig_s_weak;
    return RS_RUNNING;
}

static rs_result rs_loadsig_s_blocklen(rs_job_t *job)
{
    int l;
    rs_result result;

    if ((result = rs_suck_n4(job, &l)) != RS_DONE)
        return result;
    if (l < 1) {
        rs_error("block length of %d is bogus", l);
        return RS_CORRUPT;
    }
    rs_trace("got block length %d", l);
    job->sig_block_len = l;
    job->stats.block_len = l;
    job->statefn = rs_loadsig_s_stronglen;
    return RS_RUNNING;
}

static rs_result rs_loadsig_s_magic(rs_job_t *job)
{
    int l;
    rs_result result;

    if ((result = rs_suck_n4(job, &l)) != RS_DONE)
        return result;
    rs_trace("got signature magic %#x", l);
    job->sig_magic = l;
    job->statefn = rs_loadsig_s_blocklen;
    return RS_RUNNING;
}

rs_job_t *rs_loadsig_begin(rs_signature_t **signature)
{
    rs_job_t *job;

    job = rs_job_new("loadsig", rs_loadsig_s_magic);
    *signature = job->signature = rs_alloc_struct(rs_signature_t);
    return job;
}
