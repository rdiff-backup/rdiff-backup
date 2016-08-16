/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- library for network deltas
 *
 * Copyright 1999-2001, 2014, 2015 by Martin Pool <mbp@sourcefrog.net>
 * Copyright (C) 1999 by Andrew Tridgell <tridge@samba.org>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU Lesser General Public License as published by
 * the Free Software Foundation; either version 2.1 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */


/**
 * \file mksum.c Generate file signatures.
 **/

/*
 * Generating checksums is pretty easy, since we can always just
 * process whatever data is available.  When a whole block has
 * arrived, or we've reached the end of the file, we write the
 * checksum out.
 */

/* TODO: Perhaps force blocks to be a multiple of 64 bytes, so that we
 * can be sure checksum generation will be more efficient.  I guess it
 * will be OK at the moment, though, because tails are only used if
 * necessary. */

#include "config.h"

#include <stdlib.h>
#include <stdio.h>
#include <assert.h>

#include "librsync.h"
#include "stream.h"
#include "util.h"
#include "sumset.h"
#include "job.h"
#include "netint.h"
#include "trace.h"
#include "checksum.h"


/* Possible state functions for signature generation. */
static rs_result rs_sig_s_header(rs_job_t *);
static rs_result rs_sig_s_generate(rs_job_t *);



/**
 * State of trying to send the signature header.
 * \private
 */
static rs_result rs_sig_s_header(rs_job_t *job)
{
    rs_squirt_n4(job, job->magic);
    rs_squirt_n4(job, job->block_len);
    rs_squirt_n4(job, job->strong_sum_len);
    rs_trace("sent header (magic %#x, block len = %d, strong sum len = %d)",
             job->magic, (int) job->block_len, (int) job->strong_sum_len);
    job->stats.block_len = job->block_len;

    job->statefn = rs_sig_s_generate;
    return RS_RUNNING;
}


/**
 * Generate the checksums for a block and write it out.  Called when
 * we already know we have enough data in memory at \p block.
 * \private
 */
static rs_result
rs_sig_do_block(rs_job_t *job, const void *block, size_t len)
{
    rs_weak_sum_t       weak_sum;
    rs_strong_sum_t     strong_sum;

    weak_sum = rs_calc_weak_sum(block, len);

    if (job->magic == RS_BLAKE2_SIG_MAGIC) {
        rs_calc_blake2_sum(block, len, &strong_sum);
    } else if(job->magic == RS_MD4_SIG_MAGIC) {
        rs_calc_md4_sum(block, len, &strong_sum);
    } else {
        rs_error("BUG: invalid job magic %#lx", (unsigned long) job->magic);
        return RS_INTERNAL_ERROR;
    }

    rs_squirt_n4(job, weak_sum);
    rs_tube_write(job, strong_sum, job->strong_sum_len);

    if (rs_trace_enabled()) {
        char                strong_sum_hex[RS_MAX_STRONG_SUM_LENGTH * 2 + 1];
        rs_hexify(strong_sum_hex, strong_sum, job->strong_sum_len);
        rs_trace("sent weak sum 0x%08x and strong sum %s", weak_sum,
                 strong_sum_hex);
    }

    job->stats.sig_blocks++;

    return RS_RUNNING;
}


/**
 * State of reading a block and trying to generate its sum.
 * \private
 */
static rs_result
rs_sig_s_generate(rs_job_t *job)
{
    rs_result           result;
    size_t              len;
    void                *block;

    /* must get a whole block, otherwise try again */
    len = job->block_len;
    result = rs_scoop_read(job, len, &block);

    /* unless we're near eof, in which case we'll accept
     * whatever's in there */
    if ((result == RS_BLOCKED && rs_job_input_is_ending(job))) {
        result = rs_scoop_read_rest(job, &len, &block);
    } else if (result == RS_INPUT_ENDED) {
        return RS_DONE;
    } else if (result != RS_DONE) {
        rs_trace("generate stopped: %s", rs_strerror(result));
        return result;
    }

    rs_trace("got %ld byte block", (long) len);

    return rs_sig_do_block(job, block, len);
}


rs_job_t * rs_sig_begin(size_t new_block_len, size_t strong_sum_len,
                        rs_magic_number sig_magic)
{
    rs_job_t *job;
    int native_length;

    job = rs_job_new("signature", rs_sig_s_header);
    job->block_len = new_block_len;

    if (!sig_magic)
        sig_magic = RS_BLAKE2_SIG_MAGIC;

    switch (sig_magic) {
    case RS_BLAKE2_SIG_MAGIC:
        native_length = RS_BLAKE2_SUM_LENGTH;
        job->magic = sig_magic;
        break;
    case RS_MD4_SIG_MAGIC:
        job->magic = sig_magic;
        native_length = RS_MD4_SUM_LENGTH;
        break;
    default:
        rs_error("invalid sig_magic %#lx", (unsigned long) sig_magic);
        return NULL;
    }

    if (!strong_sum_len)
        job->strong_sum_len = native_length;
    else {
        assert(strong_sum_len <= native_length);
        job->strong_sum_len = strong_sum_len;
    }

    return job;
}

/* vim: expandtab shiftwidth=4
 */
