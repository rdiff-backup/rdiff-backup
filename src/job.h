/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- the library for network deltas
 *
 * Copyright (C) 2000, 2001, 2014 by Martin Pool <mbp@sourcefrog.net>
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

#include "mdfour.h"
#include "rollsum.h"

/** \struct rs_job The contents of this structure are private. */
struct rs_job {
    int dogtag;

    /** Human-readable job operation name. */
    const char *job_name;

    rs_buffers_t *stream;

    /** Callback for each processing step. */
    rs_result (*statefn) (rs_job_t *);

    /** Final result of processing job. Used by rs_job_s_failed(). */
    rs_result final_result;

    /* Arguments for initializing the signature used by mksum.c and readsums.c.
     */
    int sig_magic;
    int sig_block_len;
    int sig_strong_len;

    /** The size of the signature file if available. Used by loadsums.c when
     * initializing the signature to preallocate memory. */
    rs_long_t sig_fsize;

    /** Pointer to the signature that's being used by the operation. */
    rs_signature_t *signature;

    /** Flag indicating signature should be destroyed with the job. */
    int job_owns_sig;

    /** Command byte currently being processed, if any. */
    unsigned char op;

    /** The weak signature digest used by readsums.c */
    rs_weak_sum_t weak_sig;

    /** The rollsum weak signature accumulator used by delta.c */
    Rollsum weak_sum;

    /** Lengths of expected parameters. */
    rs_long_t param1, param2;

    struct rs_prototab_ent const *cmd;
    rs_mdfour_t output_md4;

    /** Encoding statistics. */
    rs_stats_t stats;

    /** Buffer of data in the scoop. Allocation is scoop_buf[0..scoop_alloc],
     * and scoop_next[0..scoop_avail] contains data yet to be processed.
     * scoop_next[scoop_pos..scoop_avail] is the data yet to be scanned. */
    rs_byte_t *scoop_buf;       /* the allocation pointer */
    rs_byte_t *scoop_next;      /* the data pointer */
    size_t scoop_alloc;         /* the allocation size */
    size_t scoop_avail;         /* the data size */
    size_t scoop_pos;           /* the scan position */

    /** If USED is >0, then buf contains that much write data to be sent out. */
    rs_byte_t write_buf[36];
    int write_len;

    /** If \p copy_len is >0, then that much data should be copied through
     * from the input. */
    rs_long_t copy_len;

    /** Copy from the basis position. */
    rs_long_t basis_pos, basis_len;

    /** Callback used to copy data from the basis into the output. */
    rs_copy_cb *copy_cb;
    void *copy_arg;

};

rs_job_t *rs_job_new(const char *, rs_result (*statefn) (rs_job_t *));

int rs_job_input_is_ending(rs_job_t *job);

/** Magic job tag number for checking jobs have been initialized. */
#define RS_JOB_TAG 20010225

/** Assert that a job is valid.
 *
 * We don't use a static inline function here so that assert failure output
 * points at where rs_job_check() was called from. */
#define rs_job_check(job) do {\
    assert(job->dogtag == RS_JOB_TAG);\
} while (0)
