/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- library for network deltas
 * $Id$
 *
 * Copyright (C) 2000, 2001 by Martin Pool <mbp@samba.org>
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

                                /*
                                 | Let's climb to the TOP of that
                                 | MOUNTAIN and think about STRIP
                                 | MINING!!
                                 */


/*
 * delta.c -- Generate in streaming mode an rsync delta given a set of
 * signatures, and a new file.
 *
 * The size of blocks for signature generation is determined by the
 * block size in the incoming signature.
 *
 * To calculate a signature, we need to be able to see at least one
 * block of the new file at a time.  Once we have that, we calculate
 * its weak signature, and see if there is any block in the signature
 * hash table that has the same weak sum.  If there is one, then we
 * also compute the strong sum of the new block, and cross check that.
 * If they're the same, then we can assume we have a match.
 *
 * The final block of the file has to be handled a little differently,
 * because it may be a short match.  Short blocks in the signature
 * don't include their length -- we just allow for the final short
 * block of the file to match any block in the signature, and if they
 * have the same checksum we assume they must have the same length.
 * Therefore, when we emit a COPY command, we have to send it with a
 * length that is the same as the block matched, and not the block
 * length from the signature.
 */


#include <config.h>

#include <assert.h>
#include <stdlib.h>
#include <stdio.h>

#include "rsync.h"
#include "emit.h"
#include "stream.h"
#include "util.h"
#include "sumset.h"
#include "job.h"
#include "trace.h"
#include "checksum.h"
#include "search.h"


static rs_result rs_delta_scan_short(rs_job_t *, rs_long_t avail_len, void *);
static rs_result rs_delta_scan_full(rs_job_t *, rs_long_t avail_len, void *);

static rs_result rs_delta_s_deferred_copy(rs_job_t *job);



static rs_result rs_delta_s_end(rs_job_t *job)
{
    rs_emit_end_cmd(job);
    return RS_DONE;
}


/**
 * \brief Get a block of data if possible, and see if it matches.
 *
 * On each call, we try to process all of the input data available on
 * the scoop and input buffer.
 */
static rs_result
rs_delta_s_scan(rs_job_t *job)
{
    size_t         this_len, avail_len;
    int            is_ending;
    void           *inptr;
    rs_result      result;

    rs_job_check(job);

    avail_len = rs_scoop_total_avail(job);
    this_len = job->block_len;
    is_ending = job->stream->eof_in;

    /* Now, we have avail_len bytes, and we need to scan through them
     * looking for a match.  We'll always end up emitting exactly one
     * command, either a literal or a copy, and after discovering that
     * we will skip over the appropriate number of bytes. */
    if (avail_len == 0) {
        if (is_ending) {
            /* no more delta to do */
            job->statefn = rs_delta_s_end;
        }
        return RS_BLOCKED;
    } 

    /* must read at least one block, or give up */
    if ((avail_len < job->block_len) && !is_ending) {
        /* we know we won't get it, but we have to try for a whole
         * block anyhow so that it gets into the scoop. */
        rs_scoop_input(job, job->block_len);
        return RS_BLOCKED;
    }
    
    result = rs_scoop_readahead(job, avail_len, &inptr);
    if (result != RS_DONE)
        return result;
    
    if (is_ending)
        return rs_delta_scan_short(job, avail_len, inptr);
    else {
        assert(avail_len >= job->block_len);
        return rs_delta_scan_full(job, avail_len, inptr);
    }
}


/**
 * Scan for a possibly-short block in the next \p avail_len bytes of input.
 */
static rs_result
rs_delta_scan_short(rs_job_t *job, rs_long_t avail_len, void *inptr)
{
/*     rs_result      result; */
/*     rs_long_t      this_len; */

    /* common case of not being near the end, and therefore trying
     * to read a whole block. */

    /* TODO: Instead of this, calculate the checksum, rolling if
     * possible.  Then look it up in the hashtable.  If we match, emit
     * that and advance over the scooed data.  Otherwise, emit a
     * literal byte and keep searching while there's input data. */

    /* TODO: Handle short end blocks. */
    
    rs_trace("emit lazy literal for %ld bytes", (long) avail_len);
    rs_emit_literal_cmd(job, avail_len);
    rs_tube_copy(job, avail_len);

    return RS_RUNNING;
}



/**
 * Scan for a full-size block in the next \p avail_len bytes of input.
 * 
 * Emit exactly one LITERAL or COPY command.
 */
static rs_result
rs_delta_scan_full(rs_job_t *job, rs_long_t avail_len, void *p)
{
    rs_weak_sum_t        weak_sum;
    rs_long_t            match_where;
    int                  search_pos;
    unsigned char        *inptr = (unsigned char *) p;
    
    /* So, we have avail_len bytes of data, and we want to look
     * through it for a match at some point.  It's OK if it's not at
     * the start of the available input data.  If we're approaching
     * the end and can't get a match, then we just block and get more
     * later. */

    /* TODO: If we don't match immediately, just queue up *one*
     * literal and then keep going. */
    for (search_pos = 0; search_pos <= avail_len - job->block_len; search_pos++) {
        weak_sum = rs_calc_weak_sum(inptr + search_pos, job->block_len);
        if (rs_search_for_block(weak_sum, inptr + search_pos, job->block_len,
                                job->signature, &job->stats, &match_where)) {
            /* So, we got a match.  cool.  now, if there was literal data
             * ahead of that, we need to flush it first.  otherwise, we
             * can emit the copy command. */
            /* TODO: Perhaps instead store this in the job, and set a new
             * statefn. */
            rs_trace("matched %ld!", (long) match_where);
            job->basis_pos = match_where;
            job->basis_len = job->block_len;
            job->statefn = rs_delta_s_deferred_copy;
            break;
        }
    }

    if (search_pos) {
        /* There's some literal data at the start of this window which
         * we know is not in any block. */
        rs_trace("got %d bytes of literal data", search_pos);
        rs_emit_literal_cmd(job, search_pos);
        rs_tube_copy(job, search_pos);
    }
    
    return RS_RUNNING;
}


static rs_result rs_delta_s_deferred_copy(rs_job_t *job)
{
    if (!job->basis_len) {
        rs_log(RS_LOG_ERR, "somehow got zero basis_len");
        return RS_INTERNAL_ERROR;
    }
    
    rs_emit_copy_cmd(job, job->basis_pos, job->basis_len);
    rs_scoop_advance(job, job->basis_len);

    job->statefn = rs_delta_s_scan;
    
    return RS_RUNNING;
}


/**
 * \brief State function that does a fake delta containing only
 * literal data to recreate the input.
 */
static rs_result rs_delta_s_fake(rs_job_t *job)
{
    rs_buffers_t * const stream = job->stream;
    size_t avail = stream->avail_in;

    if (avail) {
        rs_trace("emit fake delta for %ld available bytes", (long) avail);
        rs_emit_literal_cmd(job, avail);
        rs_tube_copy(job, avail);
        return RS_RUNNING;
    } else {
        if (rs_job_input_is_ending(job)) {
            job->statefn = rs_delta_s_end;
            return RS_RUNNING;
        } else {                
            return RS_BLOCKED;
        }
    }
}


/**
 * State function for writing out the header of the encoding job.
 */
static rs_result rs_delta_s_header(rs_job_t *job)
{
    rs_emit_delta_header(job);

    if (job->block_len) {
        if (!job->signature) {
            rs_error("no signature is loaded into the job");
            return RS_PARAM_ERROR;
        }
        job->statefn = rs_delta_s_scan;
    } else {
        rs_trace("block length is zero for this delta; "
                 "therefore using lazy deltas");
        job->statefn = rs_delta_s_fake;
    }

    return RS_RUNNING;
}


/**
 * Prepare to compute a streaming delta.
 */
rs_job_t *rs_delta_begin(rs_signature_t *sig)
{
    rs_job_t *job;

    job = rs_job_new("delta", rs_delta_s_header);
    job->signature = sig;
    
    if ((job->block_len = sig->block_len) < 0) {
        rs_log(RS_LOG_ERR, "unreasonable block_len %d in signature",
               job->block_len);
        return NULL;
    }

    job->strong_sum_len = sig->strong_sum_len;
    if (job->strong_sum_len < 0  ||  job->strong_sum_len > RS_MD4_LENGTH) {
        rs_log(RS_LOG_ERR, "unreasonable strong_sum_len %d in signature",
               job->strong_sum_len);
        return NULL;
    }
	
    return job;
}


