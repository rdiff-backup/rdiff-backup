/*				       	-*- c-file-style: "bsd" -*-
 *
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool
 * 
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */


#include "includes.h"

/* GENERATE NEW SIGNATURES AND DIFFERENCE STREAM
  
   OK, here's the deal: we hold the signatures for the cached
   instance, and we're reading the new instance from upstream.  As we
   read, we need to generate signatures for the new instance, and also
   search for blocks in it that match the old version.
  
   All of this has to be pipelined.  This means that we start sending
   data as soon as we can, rather than waiting until we've seen the
   whole file: it might be arbitrarily big, or take a long time to
   come down.  However, we need a certain amount of elbow-room to
   generate signatures and find matches: in fact, we need a block of
   readahead for both of them.
  
   It's important to understand the relationship between
   signature-generation and match-finding.  I think of them as train
   cars bumping into each other: they're both using the same map_ptr
   region and so are coupled, but they don't move in lock step.
  
   The block sizes for old and new signatures may be different.
   New signatures are always generated aligned on block boundaries,
   and there's no point doing rolling checksums for them, since we
   always know exactly where they're going to be.  We need to generate
   an md4sum for each block.
  
   In the search checksums, rolling signatures are crucially
   important, and we generate strong checksums pretty infrequently.
   If we find a match, then we need to skip over it and restart the
   rolling checksum.
  
   (Calculating the new and search checksums independently is a little
   inefficient when the block lengths are the same and they're
   perfectly aligned: we're calculating the signature twice for the
   same data.  Having the two files exactly the same is not uncommon,
   but still it's OK to waste a little time in this version.  We might
   in the future detect that they're the same and just echo back the
   same signature, but that's an optimization.)
  
   This file doesn't know about the wire encoding format: it just says
   something when it has a match, literal, or signature data, and
   emit.c et al actually send it out.
  
   Both the signature and search work is done from a single map_ptr
   buffer.  map_ptr does most of the intelligence about retaining and
   discarding data.  We
  
   There are special cases when we're approaching the end of the
   file.  The final signature must be generated over the (possibly)
   short block at the end.  The search must be prepared to match that
   short block, or if it doesn't match then to emit it as literal
   data.
  
   At the same time, we also calculate a whole-file md4 checksum,
   which the decoder is likely to use as proof that the server is not
   mentally competent.  */



const int hs_encode_job_magic = 23452345;


struct hs_encode_job {
    int			tag;

    int			in_fd;
    hs_map_t	       *in_map;

    /* On the next iteration, we'll try to generate the checksum for a
     * block at this location. */
    hs_sum_set_t       *sums;
    hs_stats_t	       *stats;

    /* We'll read more checksum data from this point. */
    hs_off_t		check_cursor;
    hs_mdfour_t		filesum;
    size_t		filesum_block;

    /* Things for the new checksum. */
    hs_off_t		sum_cursor;
    size_t		new_block_len;
    size_t		new_strong_len;

    /* This points to the rolling sums used for searching. */
    hs_off_t		search_cursor;
    hs_rollsum_t       *rollsum;

    int			seen_eof;

    hs_membuf_t	       *sig_tmpbuf;
    hs_membuf_t	       *lit_tmpbuf;
    _hs_copyq_t	        copyq;

    hs_write_fn_t       write_fn;
    void	       *write_priv;

    size_t		input_block;
};


static void
_hs_nad_filesum_begin(hs_encode_job_t *job)
{
    hs_mdfour_begin(&job->filesum);
    job->check_cursor = 0;
    job->filesum_block = 32 << 10;
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


hs_encode_job_t *
hs_encode_begin(int in_fd, hs_write_fn_t write_fn, void *write_priv,
		hs_sum_set_t *sums,
		hs_stats_t *stats,
		size_t new_block_len)
{
    hs_encode_job_t *job;
    int ret;

    job = _hs_alloc_struct(hs_encode_job_t);

    job->in_fd = in_fd;
    job->in_map = _hs_map_file(in_fd);

    job->write_priv = write_priv;
    job->write_fn = write_fn;

    /* FIXME: Should we use input blocks, or should we just read
     * enough to run a coroutine? */
    job->input_block = 32<<10;
				    
    job->sums = sums;
    job->stats = stats;
    job->new_block_len = new_block_len;
    hs_bzero(stats, sizeof *stats);

    job->rollsum = _hs_alloc_struct(hs_rollsum_t);

    _hs_trace("**** begin");

    hs_bzero(&job->copyq, sizeof job->copyq);

    _hs_nad_filesum_begin(job);

    /* Allocate a buffer to hold literal output */
    job->lit_tmpbuf = hs_membuf_new();

    if ((ret = _hs_littok_header(write_fn, write_priv)) < 0)
	_hs_fatal("couldn't write littok header!");

    _hs_nad_sum_begin(job);

    return job;
}


/* Work out where we have to map to achieve something useful, and
 * return a pointer thereto.  Set MAP_LEN to the amount of available
 * data. */
static char const *
_hs_nad_map(hs_encode_job_t *job,
	       hs_off_t *map_off,
	       size_t *map_len)
{
    char const	       *p;
    hs_off_t		start;

    /* once we've seen eof, we should never try to map any more
     * data. */
    assert(!job->seen_eof);

    /* Find the range we have to map that won't skip data that hasn't
     * been processed, but that allows us to accomplish something. */
    start = job->check_cursor;
    if (start > job->search_cursor)
	start = job->search_cursor;
    if (start > job->sum_cursor)
	start = job->sum_cursor;
    
    *map_off = start;
    *map_len = job->input_block;

    p = _hs_map_ptr(job->in_map, *map_off, map_len, &job->seen_eof);

    return p;
}


static void
_hs_nad_search_iter(hs_encode_job_t *job,
		       char const *p,
		       ssize_t avail)
{
    if (avail <= 0)
	return;
    
    /* Actual searching is stubbed out for the moment; we just
     * generate literal commands. */
    _hs_send_literal(job->write_fn, job->write_priv, op_kind_literal,
		     p, avail);
    job->search_cursor += avail;
}


/* Write out checksums for whatever part of this file we can manage.  */
static void
_hs_nad_sum_iter(hs_encode_job_t *job,
		    char const *p,
		    ssize_t avail)
{
    while (avail >= (ssize_t) job->new_block_len ||
	   (job->seen_eof  && avail > 0)) {
	size_t	l;

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
    char	       result[MD4_LENGTH];
#ifdef DO_HS_TRACE
    char	       sum_hex[MD4_LENGTH * 2 + 2];
#endif

    hs_mdfour_result(&job->filesum, result);

#ifdef DO_HS_TRACE
    // At the end, emit the whole thing
    hs_hexify_buf(sum_hex, (char const *)result, MD4_LENGTH);
    _hs_trace("got filesum %s", sum_hex);
#endif

    _hs_emit_filesum(job->write_fn, job->write_priv,
		     result, MD4_LENGTH);
}


static void
_hs_nad_filesum_iter(hs_encode_job_t *job,
			char const *p,
			ssize_t avail)
{
    while (avail >= (ssize_t) job->filesum_block
	   || (job->seen_eof && avail > 0)) {
	size_t	l;

	if (job->seen_eof)
	    l = avail;
	else
	    l = job->filesum_block;
	
	_hs_trace("add in @%ld+%ld",
		  (long) job->check_cursor, (long) l);
	hs_mdfour_update(&job->filesum, p, l);
	_hs_nad_filesum_flush(job);

	p += l;
	avail -= l;
	job->check_cursor += l;
    }
}



hs_result_t
hs_encode_iter(hs_encode_job_t *job)
{
    size_t		map_len;
    char const		*p;
    hs_off_t		map_off;
     
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
    p = _hs_nad_map(job, &map_off, &map_len);

    /* We have essentially three coroutines to run here.  We know
     * their cursor position, so we can give each of them a pointer
     * and length for their data. */
    _hs_nad_search_iter(job,
			   p + job->search_cursor - map_off,
			   map_len - job->search_cursor + map_off);
    _hs_nad_sum_iter(job,
			p + job->sum_cursor - map_off,
			map_len - job->sum_cursor + map_off);
    _hs_nad_filesum_iter(job, p + job->check_cursor - map_off,
			    map_len - job->check_cursor + map_off);

    /* There is no need to flush: these functions all do output as
     * soon as they can. */

    /* The problem here is that we might be near EOF, but mapptr won't
     * realize it has to do another read, and we won't know that we
     * should force it.  All we see is that we have not enough data to
     * do a full read.  What now? */

    if (job->seen_eof) {
	_hs_emit_eof(job->write_fn, job->write_priv, job->stats);
	return HS_DONE;
    } else {
	return HS_AGAIN;
    }
}
