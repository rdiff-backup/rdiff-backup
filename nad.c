/*=                                     -*- c-file-style: "bsd" -*-
 * rproxy -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool <mbp@humbug.org.au>
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
                                         | Hearts and thoughts they
                                         | fade, fade away.
                                         */


/*=
 * GENERATE NEW SIGNATURES AND DIFFERENCE STREAM
 *
 * Here's a diagram of the encoding process:
 *
 *                            /------- OLD SIGNATURE
 *                           v
 * UPSTREAM -raw-+-----> SEARCH ------> chunked -> DOWNSTREAM
 *               \                        ^
 *                > --- NEW SIGNATURE ---'
 *
 * Before the process starts, we read and hold in memory an
 * hs_sumset_t containing checksums of the old version of the file.
 * We want to read in the new file, and generate a chunked stream
 * describing differences from the old version.  Also, we generate a
 * checksum (not shown) of the entire file from upstream, which is
 * passed into the chunked stream as an extra check against mistakes
 * while encoding the file.
 *
 * All of this has to be pipelined.  This means that we start sending
 * data as soon as we can, rather than waiting until we've seen the
 * whole file: it might be arbitrarily big, or take a long time to
 * come down.  However, we need a certain amount of elbow-room to
 * generate signatures and find matches: in fact, we need a block of
 * readahead for both of them.
 *
 * The whole algorithm is done in a kind of non-blocking way: we
 * process as much input as is available on each iteration, and then
 * return to the caller so they can do something else if they wish.
 *
 * It's important to understand the relationship between
 * signature-generation and match-finding.  I think of them as train
 * cars bumping into each other: they're both using the same map_ptr
 * region and so are coupled, but they don't move in lock step.  So
 * there are separate cursors in the nad_job for all of them.  Each
 * time we map some input data, we process as much of each as
 * possible.
 *
 * The block sizes for old and new signatures may be different.
 * New signatures are always generated aligned on block boundaries,
 * and there's no point doing rolling checksums for them, since we
 * always know exactly where they're going to be.  We need to generate
 * an md4sum for each block.
 *
 * In the search checksums, rolling signatures are crucially important
 * -- these are meant to be cheap to calculate.  If we think we
 * matched on the weak rolling checksum, then we calculate the strong
 * (md4) checksum and see if it matches.  If we find a match, then we
 * emit a COPY command, advance the cursor and restart the rolling
 * checksum.
 *
 * (Calculating the new and search checksums independently is a little
 * inefficient when the block lengths are the same and they're
 * perfectly aligned: we're calculating the signature twice for the
 * same data.  Having the two files exactly the same is not uncommon,
 * but still it's OK to waste a little time in this version.  We might
 * in the future detect that they're the same and just echo back the
 * same signature, but that's an optimization.)
 *
 * This file doesn't know about the wire encoding format: it just says
 * something when it has a match, literal, or signature data, and
 * emit.c et al actually send it out.
 *
 * There are special cases when we're approaching the end of the
 * file.  The final signature must be generated over the (possibly)
 * short block at the end.  The search must be prepared to match that
 * short block, or if it doesn't match then to emit it as literal
 * data.
 *
 * At the same time, we also calculate a whole-file md4 checksum,
 * which the decoder is likely to use as proof that the server is not
 * mentally competent.
 *
 * Perhaps mapptr is not quite the right interface to use here, though
 * it's pretty close.  It's kind of arguable whether this function
 * should call for more input or vice versa.  If it calls for input,
 * then perhaps it should call through a callback function.  Still,
 * for the time being almost everyone will want to just use plain IO,
 * so there's no immediate reason to complicate it.
 */

/*
 * TODO: Check all return codes when writing.
 *
 * TODO: Statistics are not generated for literals.
 *
 * TODO: Send out literals through a literal buffer to make
 * transmission faster?  If we do this, then don't copy the data again
 * but just keep it mapped until we're finished with it.  Perhaps this
 * even points the way to a clean way to do non-blocking output as
 * well?
 *
 * TODO: Send out copy commands through a copy queue; I think the
 * design for this is already about as good as it can be.
 *
 * TODO: We should be nonblocking on output.  I'm not sure how clever
 * we have to be, though: is it enough just to queue up all the
 * output, or should we take the available output queue space into
 * account in deciding what to do?
 */


const int hs_encode_job_magic = 23452345;


#include "includes.h"
#include "nad_p.h"
#include "sum_p.h"
#include "command.h"
#include "emit.h"


static void
_hs_nad_filesum_begin(hs_encode_job_t *job)
{
    hs_mdfour_begin(&job->filesum);
}


static void
_hs_nad_sum_begin(hs_encode_job_t *job)
{
    job->sig_tmpbuf = hs_membuf_new();
    job->new_strong_len = DEFAULT_SUM_LENGTH;

    if (_hs_newsig_header(job->new_block_len,
                          hs_membuf_write,
                          job->sig_tmpbuf)
        < 0) {
        _hs_fatal("couldn't write newsig header!");
    }
}


/*
 * Start a new job of nad encoding.  After calling this, the return
 * value should be passed repeatedly to hs_encode_iter until all the
 * work is done.
 */
hs_encode_job_t *
hs_encode_begin(int in_fd, hs_write_fn_t write_fn, void *write_priv,
                hs_sumset_t *sums,
                hs_stats_t *stats,
                size_t new_block_len)
{
    hs_encode_job_t *job;
    int ret;

    job = _hs_alloc_struct(hs_encode_job_t);

    job->in_fd = in_fd;
    job->in_map = hs_map_file(in_fd);

    job->write_priv = write_priv;
    job->write_fn = write_fn;

    job->sums = sums;
    if (job->sums) {
        assert(job->sums->block_len > 0);
        job->search_block_len = job->sums->block_len;
    } else {
        /* We can read and process one byte at a time, because we can
         * never match.  Of course we hope mapptr will give us back
         * more data than that. */
        job->search_block_len = 1;
    }
    
    job->new_block_len = new_block_len;
    hs_bzero(stats, sizeof *stats);

    job->search_cursor = job->literal_cursor = 0;

    job->stats = stats;
    stats->op = "encode";
    stats->algorithm = "nad";
    
    job->rollsum = _hs_alloc_struct(hs_rollsum_t);

    _hs_trace("**** begin");

    hs_bzero(&job->copyq, sizeof job->copyq);

    _hs_nad_filesum_begin(job);

    if ((ret = _hs_littok_header(write_fn, write_priv)) < 0)
        _hs_fatal("couldn't write littok header!");

    _hs_nad_sum_begin(job);

    return job;
}


/*
 * Work out where we have to map to achieve something useful, and
 * return a pointer thereto.  Set MAP_LEN to the amount of available
 * data.
 */
static byte_t const *
_hs_nad_map(hs_encode_job_t *job)
{
    off_t            start, end, end2;

    /* once we've seen eof, we should never try to map any more
     * data. */
    assert(!job->seen_eof);

    /* Find the range we have to map that won't skip data that hasn't
     * been processed, but that allows us to accomplish something. */
    start = job->search_cursor;
    if (start > job->sum_cursor)
        start = job->sum_cursor;

    end = job->search_cursor + job->search_block_len;
    end2 = job->sum_cursor + job->new_block_len;

    _hs_trace("start(search=%ld, sum=%ld), end(search=%ld, sum=%ld)",
              (long) job->search_cursor, (long) job->sum_cursor,
              (long) end, (long) end2);

    /* We choose the earlier end, because that's the earliest place
     * that will allow us to get some useful work done.  Because the
     * blocks can be different it need not be the same as in the
     * previous condition. */
    if (end2 < end)
        end = end2;
    
    job->map_off = start;
    job->map_len = end - start;

    job->map_p = hs_map_ptr(job->in_map, job->map_off, &job->map_len,
                             &job->seen_eof);

    return job->map_p;
}


/*
 * Emit a literal command for the available data without doing any
 * searching.  We use this when we have no signature for the old file.
 */
static void
_hs_nad_baseless_iter(hs_encode_job_t *job)
{
    job->search_cursor = job->map_off + job->map_len;
    _hs_nad_flush_literal(job);
}


/*
 * Try to match at the current search cursor position.  If we find
 * one, then emit an appropriate copy command.  If not, emit a minimal
 * literal command and try again next time.
 */
static void
_hs_nad_sum_iter(hs_encode_job_t *job)
{
    byte_t const *p = job->map_p + job->sum_cursor - job->map_off;
    size_t avail = job->map_len - job->sum_cursor + job->map_off;

    while (avail >= job->new_block_len ||
           (job->seen_eof  && avail > 0)) {
        size_t  l;

        if (job->seen_eof)
            l = avail;
        else
            l = job->new_block_len;

        _hs_trace("do checksum @%ld+%ld", (long) job->sum_cursor,
                  (long) l);
        _hs_mksum_of_block(p, l, 
                           hs_membuf_write, job->sig_tmpbuf, 
                           job->new_strong_len);

        _hs_push_literal_buf(job->sig_tmpbuf,
                             job->write_fn, job->write_priv,
                             job->stats, op_kind_signature);

        p += l;
        job->sum_cursor += l;
        avail -= l;
    }
}



static void
_hs_nad_filesum_flush(hs_encode_job_t *job)
{
    byte_t             result[MD4_LENGTH];
#ifdef DO_HS_TRACE
    char               sum_hex[MD4_LENGTH * 3];
#endif

    hs_mdfour_result(&job->filesum, result);

#ifdef DO_HS_TRACE
    /* At the end, emit the whole thing */
    hs_hexify_buf(sum_hex, result, MD4_LENGTH);
    _hs_trace("flushing out filesum %s", sum_hex);
#endif

    _hs_emit_filesum(job->write_fn, job->write_priv,
                     result, MD4_LENGTH);
}



/*
 * Update the hash of the whole file to date, to be emitted at the
 * end to catch errors in the encode/decode algorithms.
 */
static void
_hs_nad_filesum_iter(hs_encode_job_t *job)
{
    byte_t const *p = job->map_p - job->map_off + job->filesum_cursor;
    size_t avail = job->map_len + job->map_off - job->filesum_cursor;
    
    hs_mdfour_update(&job->filesum, p, avail);

    job->filesum_cursor += avail;
}



hs_result_t
hs_encode_iter(hs_encode_job_t *job)
{
    /* Map some data.  We advance the map to the earliest point in the
     * datastream that anybody needs to see.
     *
     * Several things can happen here:
     *
     * If the stream is in blocking mode, then we'll read at least
     * enough data to run one of the coroutines.  If the stream is in
     * nonblocking mode, we might not get enough, in which case we'll
     * return and the caller will presumably call select(2).
     *
     * In either case, if we reach EOF we'll finish up processing
     * immediately.  */
    _hs_nad_map(job);

    /* We have essentially three coroutines to run here.  We know
     * their cursor position, so we can give each of them a pointer
     * and length for their data. */
    if (job->sums) {
        _hs_nad_search_iter(job);
    } else {
        _hs_nad_baseless_iter(job);
    }
    
    _hs_nad_sum_iter(job);
    _hs_nad_filesum_iter(job);

    /* TODO: When we have copy queues, we should flush them here
     * too. */
    _hs_nad_flush_literal(job);

    /* The problem here is that we might be near EOF, but mapptr won't
     * realize it has to do another read, and we won't know that we
     * should force it.  All we see is that we have not enough data to
     * do a full read.  What now? */

    if (job->seen_eof) {
        _hs_nad_filesum_flush(job);
        _hs_emit_eof(job->write_fn, job->write_priv, job->stats);
        return HS_DONE;
    } else {
        return HS_AGAIN;
    }
}
