/* -*- mode: c; c-file-style: "bsd" -*- */
/*--------------------------------------------------------------------
   $Id$
  
   nat.c -- Generate combined signature/difference stream.
   
   Copyright (C) 2000 by Martin Pool
   
   This program is free software; you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation; either version 2 of the License, or
   (at your option) any later version.
   
   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.
   
   You should have received a copy of the GNU General Public License
   along with this program; if not, write to the Free Software
   Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#include "includes.h"
#include "hsync.h"
#include "hsyncproto.h"
#include "private.h"
#include "emit.h"

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




/* The new and sexy GD01 sign+encode algorithm!  Thanks, Luke!
   Thanks, Tridge!
  
   READ_FN|READ_PRIV is connected to the upstream socket, which
   supplies the new version of the file.  WRITE_FN|WRITE_PRIV is
   connected to the client, who wants to read a gd01 stream of
   reconstruction and new-signature operations.
   SIGREAD_FN|SIGREAD_PRIV supplies the old signature, which we can
   use to search for matching blocks.
  
   STATS will be filled up with performance statistics about the
   encoding process. */
ssize_t
hs_gd01_encode(hs_read_fn_t read_fn, void *readprivate,
	       hs_write_fn_t write_fn, void *write_priv,
	       hs_read_fn_t sigread_fn, void *sigreadprivate,
	       UNUSED(int new_block_len), hs_stats_t * stats)
{
     _hs_trace("**** begin");

     bzero(stats, sizeof *stats);
     bzero(&copyq, sizeof copyq);
     bzero(&new_roll, sizeof new_roll);

     hs_mdfour_begin(&filesum);

     /* XXX: For simplicity, this is hardwired at the moment. */
     block_len = 1024;
    
     return_val_if_fail(block_len > 0, -1);

     if ((ret = _hs_littok_header(write_fn, write_priv)) < 0)
	  goto out;

     /* Allocate a buffer to hold literal output */
     sig_tmpbuf = hs_membuf_new();
     lit_tmpbuf = hs_membuf_new();
     inbuf = _hs_new_inbuf();

     ret = _hs_newsig_header(block_len, hs_membuf_write, sig_tmpbuf);
     if (ret < 0)
	  goto out;

     /* Now do our funky checksum checking */
     rollsum->havesum = 0;
     do {
	  /* TODO: Try to read from the input in such a size that if
	     all of the blocks in the buffer match, we won't need to
	     shuffle any data.  This isn't urgent, and in the general
	     case we can't avoid shuffling, since the matches may be
	     offset and so not align nicely with the buffer length. */
	  ret = _hs_fill_inbuf(inbuf, read_fn, readprivate);
	  at_eof = (ret == 0);
	  inbuf->cursor = 0;

	  /* If we've reached EOF then we keep processing right up to
	     the end, whether we have a block of readahead or not.
	     Otherwise, we stop when we need more readahead to process
	     a full block.  */
	  if (at_eof)
	       need_bytes = 1;
	  else
	       need_bytes = block_len;
	  
	  while (inbuf->cursor + need_bytes <= inbuf->amount) {
	       short_block = MIN(block_len, inbuf->amount - inbuf->cursor);
	       _hs_update_sums(inbuf, block_len, short_block, rollsum);
	       _hs_update_sums(inbuf, block_len, short_block, &new_roll);

#ifdef HS_PAINFUL_HONESTY
	       _hs_painful_check(rollsum->weak_sum, inbuf, short_block);
#endif /* HS_PAINFUL_HONESTY */
	    
	       if (_hs_signature_ready(inbuf, block_len)) {
		    _hs_output_block_hash(hs_membuf_write, sig_tmpbuf,
					  inbuf, short_block, &new_roll);
	       }

	       if (got_old) {
		    token = _hs_find_in_hash(rollsum, inbuf->buf + inbuf->cursor,
					     short_block, sums, stats);
	       }
	       else
		    token = 0;

	       if (token > 0) {
		    /* if we're at eof, then we should only be able to
		       match the last token, because it's the only
		       short one.  we don't store the token lengths;
		       they're implied by the checksum.  the reverse
		       isn't true: the last token might be a full
		       block, so we are allowed to match it
		       anytime. */
		    if (at_eof) {
			 assert(token == sums->count);
		    }
		    
		    _hs_trace("found token %d in stream at abspos=%-8d"
			      " length=%-6d", token,
			      inbuf->abspos+inbuf->cursor,
			      short_block);

		    if (_hs_push_literal_buf(lit_tmpbuf, write_fn, write_priv, stats,
					      op_kind_literal) < 0)
			 return -1;

		    /* tokens are ones-based, blocks are zeros-based,
		       so we subtract 1. */
		    ret = _hs_queue_copy(write_fn, write_priv,
					 &copyq, (token-1) * block_len,
					 short_block, stats);

		    /* FIXME: It's no good to skip over the block like
                       this, because we might have to update and
                       output sums from the middle of it. */
		    /* FIXME: Does this update our absolute position
                       in the right way? */
		    if (ret < 0)
			 goto out;
		    hs_mdfour_update(&filesum, inbuf->buf + inbuf->cursor, short_block);
		    inbuf->cursor += short_block;
		    rollsum->havesum = new_roll.havesum = 0;
	       } else {
		    if (got_old)
			 _hs_copyq_push(write_fn, write_priv, &copyq, stats);
		 
		    /* Append this character to the outbuf */
		    ret = _hs_append_literal(lit_tmpbuf,
					     inbuf->buf[inbuf->cursor]);
		    _hs_trim_sums(inbuf, rollsum, short_block);
		    _hs_trim_sums(inbuf, &new_roll, short_block);
		    hs_mdfour_update(&filesum, inbuf->buf + inbuf->cursor, 1);
		    inbuf->cursor++;
	       }
	  }

	  _hs_slide_inbuf(inbuf);
     } while (!at_eof);

#if 0
     /* If we didn't just send a block hash, then send it now for the
        last short block. */
     if (!_hs_signature_ready(inbuf, block_len)) {
	  _hs_output_block_hash(hs_membuf_write, sig_tmpbuf,
				inbuf, short_block, &new_roll);
     }
#endif

     /* Flush any literal or copy data remaining.  Only one or the
	other should happen. */

     ret = _hs_copyq_push(write_fn, write_priv, &copyq, stats);
     if (ret < 0)
	  goto out;

     ret = _hs_push_literal_buf(lit_tmpbuf, write_fn, write_priv,
				 stats, op_kind_literal);
     if (ret < 0)
	  goto out;

     ret = _hs_push_literal_buf(sig_tmpbuf, write_fn, write_priv,
				 stats, op_kind_signature);
     if (ret < 0)
	  goto out;

     hs_mdfour_result(&filesum, filesum_result);
     hs_hexify_buf(filesum_hex, filesum_result, MD4_LENGTH);
     _hs_trace("filesum is %s", filesum_hex);

     ret = _hs_emit_filesum(write_fn, write_priv,
			    filesum_result, MD4_LENGTH);
     if (ret < 0)
	  goto out;

     /* Terminate the stream with a null */
     ret = _hs_emit_eof(write_fn, write_priv, stats);
     if (ret < 0)
	  goto out;

     stats_str = hs_format_stats(stats);
     _hs_trace("completed: %s", stats_str);
     free(stats_str);
    
     ret = 1;

 out:
     if (sig_tmpbuf)
	  hs_membuf_free(sig_tmpbuf);
     if (lit_tmpbuf)
	  hs_membuf_free(lit_tmpbuf);
     if (sums)
	  _hs_free_sum_struct(sums);
     if (inbuf->buf)
	  free(inbuf->buf);

     return ret;
}


/* We're finished encoding when we've seen the end of file, and both
   the SEARCH and SUM cursors have run up to meet it. */
static int
_hs_enc_complete(hs_encode_job_t *job)
{
    if (!at_eof)
	return 0;		/* nowhere near it! */
    if (job->sum_cursor < job->file_len)
	return 0;
    if (job->search_cursor < job->file_len)
	return 0;
    
    return 1;
}


/* Adjust the mapptr so that it covers some useful data, given the
   current positions of the search and sum cursors.

   What's useful?  Well, we certainly don't want to skip over data we
   have not yet considered both for output and for summing, so we need
   to cover at least the earliest of the two cursors.  Also, we need
   to be able to process at least one block of at least one operation,
   so we need to calculate the end of those blocks and set the map
   length to at cover them.  */
int
hs_enc_cover_me(hs_encode_job_t *job)
{
    hs_off_t first_cursor, last_end;
    hs_ssize_t len;

    first_cursor = MIN(job->sum_cursor, job->search_cursor);
    last_end = MAX(job->sum_cursor + job->block_len,
		   job->search_cursor + job->sums->block_len);

    len = last_end - first_cursor;    
}


/* The guts of the encode+sign algorithm, leading out the hassles of
   dealing with signatures and headers.

   Eventually when we're stateless, the caller will be able to return
   to this function repeatedly until encoding is complete.  That's not
   done yet, though. */
ssize_t
hs_gd01_enc_body(hs_encode_job_t *job,
		 hs_stats_t *stats)
{
    do {
	hs_enc_cover_me(job);
    } while (!_hs_enc_complete(job));

    return ret;
}
