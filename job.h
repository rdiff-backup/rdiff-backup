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


struct rs_job {
    int                 dogtag;

    /** Human-readable job operation name. */
    const char          *job_name;
    
    rs_stream_t *stream;

    /** Callback for each processing step. */
    rs_result           (*statefn)(rs_job_t *);

    /** Final result of processing job.  Used by rs_job_s_failed(). */
    rs_result final_result;

    /* Generic storage fields. */
    int                 block_len;
    int                 strong_sum_len;
    
    rs_copy_cb      *copy_cb;
    void            *copy_arg;
    
    /** Signature that's either being read in, or used for
     * generating a delta. */
    rs_signature_t      *signature;
    
    /** Command byte currently being processed, if any. */
    unsigned char       op;

    /** If in the middle of reading a signature (rs_loadsig_s_weak()),
     * this contains the weak signature. */
    rs_weak_sum_t       weak_sig;

    /** Lengths of expected parameters. */
    rs_long_t           param1, param2;
    
    struct rs_prototab_ent const *cmd;
    rs_mdfour_t      output_md4;

    /** Encoding statistics. */
    rs_stats_t          stats;

    /** Buffer of data left over in the scoop.  Allocation is
     * scoop_buf..scoop_alloc, and scoop_next[0..scoop_avail]
     * contains valid data. */
    char       *scoop_buf;
    char       *scoop_next;
    size_t      scoop_alloc;
    size_t      scoop_avail;
        
    /** If USED is >0, then buf contains that much literal data to
     * be sent out. */
    char        lit_buf[16];
    int         lit_len;

    /** If COPY_LEN is >0, then that much data should be copied
     * through from the input. */
    int         copy_len;
};


rs_job_t * rs_job_new(rs_stream_t *stream, const char *);
void rs_job_check(rs_job_t *job);
const rs_stats_t *rs_job_statistics(rs_job_t *);
