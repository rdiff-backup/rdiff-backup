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

/*
 * Profiling results as of v1.26, 2001-03-18:
 *
 * If everything matches, then we spend almost all our time in
 * rs_mdfour64 and rs_weak_sum, which is unavoidable and therefore a
 * good profile.
 *
 * If nothing matches, it is not so good.
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
#include "types.h"


/**
 * Turn this on to make all rolling checksums be checked from scratch.
 */
int rs_roll_paranoia = 0;


static rs_result rs_delta_scan(rs_job_t *, rs_long_t avail_len, void *);
static rs_result rs_delta_match(rs_job_t *, rs_long_t avail_len, void *);

static rs_result rs_delta_s_deferred_advance(rs_job_t *job);



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
     * looking for a match.  We may end up emitting a bunch of 
     * commands depending on how the blocks match with the signature */
    if ((avail_len == 0) && (job->basis_len == 0)) {
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
    
    if (!job->basis_len)
        return rs_delta_scan(job, avail_len, inptr);
    else
        return rs_delta_match(job, avail_len, inptr);
}


/**
 * Scan for a matching block in the next \p avail_len bytes of input.
 *
 * If nonmatching data is found, then a LITERAL command will be put in
 * the tube immediately.  If matching data is found, then its position
 * will be saved in the job, and the job state set up to to perform
 * RLL encoding after handling the literal.
 */
static rs_result
rs_delta_scan(rs_job_t *job, rs_long_t avail_len, void *p)
{
    rs_long_t            match_where;
    int                  search_pos, end_pos;
    unsigned char        *inptr = (unsigned char *) p;
    uint32_t             s1 = job->weak_sig & 0xFFFF;
    uint32_t             s2 = job->weak_sig >> 16;

    if (job->basis_len) {
        rs_log(RS_LOG_ERR, "somehow got nonzero basis_len");
        return RS_INTERNAL_ERROR;
    }

    
    /* So, we have avail_len bytes of data, and we want to look
     * through it for a match at some point.  It's OK if it's not at
     * the start of the available input data.  If we're approaching
     * the end and can't get a match, then we just block and get more
     * later. */

    /* FIXME: Perhaps we should be working in signed chars for the
     * rolling sum? */
    
    if (job->stream->eof_in)
        end_pos = avail_len - 1;
    else
        end_pos = avail_len - job->block_len;
    
    for (search_pos = 0; search_pos <= end_pos; search_pos++) {
        size_t this_len = job->block_len;
            
        /* Did we inherit the signature from rs_delta_match?*/
        if (job->have_weak_sig < 0) {
            job->have_weak_sig = 1;
            /* We already know that this block won't match!*/
            continue;
        }

        if (search_pos + this_len > avail_len) {
            this_len = avail_len - search_pos;
            rs_trace("block reduced to %d", this_len);
        } else if (job->have_weak_sig > 0) {
            unsigned char a = inptr[search_pos + this_len - 1];
            /* roll in the newly added byte, if any */
            s1 += a + RS_CHAR_OFFSET;
            s2 += s1;

            job->weak_sig = (s1 & 0xffff) | (s2 << 16);
        }

        if (!job->have_weak_sig) {
            rs_trace("calculate weak sum from scratch");
            job->weak_sig = rs_calc_weak_sum(inptr + search_pos, this_len);
            s1 = job->weak_sig & 0xFFFF;
            s2 = job->weak_sig >> 16;
            job->have_weak_sig = 1;
        }

        if (rs_roll_paranoia) {
            rs_weak_sum_t verify = rs_calc_weak_sum(inptr + search_pos, this_len);
            if (verify != job->weak_sig) {
                rs_fatal("mismatch between rolled sum %#x and check %#x",
                         job->weak_sig, verify);
            }
        }            
        
        if (rs_search_for_block(job->weak_sig, inptr + search_pos, this_len,
                                job->signature, &job->stats, &match_where)) {
            /* So, we got a match.  Cool.  However, there may be
             * leading unmatched data that we need to flush.  Thus we
             * set our statefn to be rs_delta_s_deferred_advance so that
             * we can skip bytes and write out the copy command later. */

            rs_trace("matched %.0f bytes at %.0f!",
                     (double) this_len, (double) match_where);
            job->basis_pos = match_where;
            job->basis_len = this_len;
            job->statefn = rs_delta_s_deferred_advance;
            job->have_weak_sig = 0;
            break;
        } else {
            /* advance by one; roll out the byte we just moved over. */
            unsigned char a = inptr[search_pos];
            unsigned shift = a + RS_CHAR_OFFSET;

            s1 -= shift;
            s2 -= this_len * shift;
            job->weak_sig = (s1 & 0xffff) | (s2 << 16);
        }
    }

    if (search_pos > 0) {
        /* We may or may not have found a block, but we know we found
         * some literal data at the start of the buffer.  Therefore,
         * we have to flush that out before we can continue on and
         * emit the copy command or keep searching. */
         
        /* FIXME: At the moment, if you call with very short buffers,
         * then you will get a series of very short LITERAL commands.
         * Perhaps this is what you deserve, or perhaps we should try
         * to get more readahead and avoid that. */

        /* There's some literal data at the start of this window which
         * we know is not in any block. */
        rs_trace("got %d bytes of literal data", search_pos);
        rs_emit_literal_cmd(job, search_pos);
        rs_tube_copy(job, search_pos);
    }

    return RS_RUNNING;
}

/**
 * advance the scoop pointer to skip a matched block.
 *
 * We can't do this greedily within rs_delta_scan since rs_tube_copy is lazy.
 * Instead we use this intermediate state to advance the scoop.
 */
static rs_result
rs_delta_s_deferred_advance(rs_job_t *job)
{
    if (!job->basis_len) {
        rs_log(RS_LOG_ERR, "somehow got zero basis_len");
        return RS_INTERNAL_ERROR;
    }

    rs_scoop_advance(job,job->basis_len);
    job->statefn=rs_delta_s_scan;

    return RS_RUNNING;
}

/**
 * Do RLL coding of output.
 *
 * When a matched block is found we are in this state. We try to accumulate
 * adjacent blocks for RLL encoding of the output. If a non-adjacent block is
 * matched, we emit a copy command for the accumulated blocks and start a
 * new RLL sequence. If a block can't be matched we need to rescan.
 */
static rs_result
rs_delta_match(rs_job_t *job, rs_long_t avail_len, void *p)
{
    rs_long_t            match_where;
    int                  search_pos;
    unsigned char        *inptr = (unsigned char *) p;
    int                  ending= job->stream->eof_in;

    if (!job->basis_len) {
        rs_log(RS_LOG_ERR, "somehow got zero basis_len");
        return RS_INTERNAL_ERROR;
    }

    /* So, we have avail_len bytes of data, and we previously matched 
     * one or more blocks. We now look for adjacent matches to roll into the
     * the current match. If we hit a block that has no match, we need to
     * go back rs_delta_scan and rescan. */

    for (search_pos = 0; search_pos <= avail_len; search_pos+=job->block_len) {
        size_t this_len = job->block_len;
            
        if (search_pos + this_len > avail_len) {
            /* We only allow short blocks at the end of stream*/
            if (!ending) {
                rs_trace("waiting for more input");
                return RS_BLOCKED;
            }
            this_len = avail_len - search_pos;
            rs_trace("block reduced to %d", this_len);
        } 

        rs_trace("calculate weak sum from scratch");
        job->weak_sig = rs_calc_weak_sum(inptr + search_pos, this_len);
        job->have_weak_sig = -1;

        if (rs_search_for_block(job->weak_sig, inptr + search_pos, this_len,
                                job->signature, &job->stats, &match_where)) {
            /* So, we got a match.  Cool. Now try to roll it into the previous
             * match. If we can't we start a new rll sequence. */
            rs_trace("matched %.0f bytes at %.0f!",
                     (double) this_len, (double) match_where);
            /* At this point we have matched this block so skip it*/
            /* We do this now since we might return in the IF block*/
            rs_scoop_advance(job,this_len);

            if (match_where == (job->basis_pos + job->basis_len)) {
                job->basis_len += this_len;
                rs_trace("adjacent match: accumulated %.0f bytes at %.0f",
                          (double)job->basis_len,(double)job->basis_pos);
            } else {
                rs_trace("new match, flushing %.0f bytes at %.0f",
                     (double)job->basis_pos,(double)job->basis_len);
                rs_emit_copy_cmd(job, job->basis_pos, job->basis_len);
                job->basis_pos = match_where;
                job->basis_len = this_len;
                /* Give the tube a chance to catchup */
                return RS_RUNNING;
            }
        } else {
            /* Copy blocks that we acummulated, there should be at least one */
            rs_trace("no match, copying %.0f bytes at %.0f",
                     (double)job->basis_len,(double)job->basis_pos);
            rs_emit_copy_cmd(job, job->basis_pos, job->basis_len);

            /* Unmatched data...we need to rescan*/
            job->basis_len=0;
            return RS_RUNNING;
        }
    }

    if (ending) {
        /* The job ended with a matching block..we must copy everything*/
        rs_emit_copy_cmd(job, job->basis_pos, job->basis_len);
        job->basis_len=0;
    }

    return RS_RUNNING;
}


/**
 * \brief State function that does a slack delta containing only
 * literal data to recreate the input.
 */
static rs_result rs_delta_s_slack(rs_job_t *job)
{
    rs_buffers_t * const stream = job->stream;
    size_t avail = stream->avail_in;

    if (avail) {
        rs_trace("emit slack delta for %.0f available bytes", (double) avail);
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
                 "therefore using slack deltas");
        job->statefn = rs_delta_s_slack;
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


