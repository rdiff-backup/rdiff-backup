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


struct hs_job {
    int                 dogtag;

    /** Human-readable job operation name. */
    const char          *job_name;
    
    hs_stream_t *stream;

    /** Callback for each processing step. */
    hs_result           (*statefn)(hs_job_t *);

    /** Final result of processing job.  Used by hs_job_s_failed(). */
    hs_result final_result;

    /* Generic storage fields. */
    size_t          block_len;
    size_t          strong_sum_len;
    
    hs_copy_cb      *copy_cb;
    void            *copy_arg;
    
    /** Signature that's either being read in, or used for
     * generating a delta. */
    hs_signature_t      *signature;
    
    /** Command byte currently being processed, if any. */
    int op;

    /** If in the middle of reading a signature (hs_loadsig_s_weak()),
     * this contains the weak signature. */
    hs_weak_sum_t       weak_sig;

    /** Lengths of expected parameters. */
    int param1, param2;
    
    struct hs_prototab_ent const *cmd;
    hs_mdfour_t      output_md4;

    /** Encoding statistics. */
    hs_stats_t          stats;
};


hs_job_t * hs_job_new(hs_stream_t *stream, const char *);
void hs_job_check(hs_job_t *job);
const hs_stats_t *hs_job_statistics(hs_job_t *);
