/* -*- mode: c; c-file-style: "bsd" -*- * $Id: enc.c,v 1.27 2000/06/01
   03:30:38 mbp Exp $ * * enc.c -- combined encode and sign

   Copyright (C) 1999-2000 by Martin Pool. Copyright (C) 1999-2000 by Peter
   Barker. Copyright (C) 1999 by Andrew Tridgell

   This program is free software; you can redistribute it and/or modify it
   under the terms of the GNU General Public License as published by the Free 
   Software Foundation; either version 2 of the License, or (at your option)
   any later version.

   This program is distributed in the hope that it will be useful, but
   WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY 
   or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
   for more details.

   You should have received a copy of the GNU General Public License along
   with this program; if not, write to the Free Software Foundation, Inc., 59 
   Temple Place, Suite 330, Boston, MA 02111-1307 USA */

/* 
   This file has an implementation of combined encoding & signing. The result 
   is a single token stream which contains the changes relative to the old
   signature and also the new signature.

   If we recognize a block whose signature we know at that point, then we
   skip the read cursor over the whole block and write out its token.

   If we don't, then we just emit a single byte and will try again at the
   next position.

   We make sure that there is more than a block of readahead data available
   in inbuf, unless we're approaching the end of the file.

   If we're approaching the end of the file and there is less than block_size 
   left, then we can still send a short block.  The checksum in this case is
   taken just over the remaining part of the file.

   When we first start processing a stream, we have to kickstart the weak
   checksum by summing the whole first block through _hs_calc_weak_sum. After 
   this, though, we can just let the checksum accumulate by adding the byte
   at the end of the block and letting older bytes fall off the end.  We
   will need to calculate a whole-block checksum again after outputting a
   token, because we've skipped over the block whose state we held.

   For simplicity, we use the same block size for both the old and new
   checksums.

   We can also encode & checksum without an old signature returned from the
   client.  We revert to this mode if anything goes wrong with the clients
   signature, so this basically makes us fail-safe: if they scrambled or
   damaged their signature then they ought to just get a copy of the new
   data.

   As we read input from upstream, we have to send it into the encoding
   process and also use it to generate a new signature.  We never worry about 
   caching the information because if we're encoding we expect to encode
   again in the future, and the encoder never needs the old value.

 */


/* FIXME: Check that we use signed/unsigned integers properly.

   TODO: Add another command, which contains the checksum for the *whole new
   file* so far.  Then we can compare it at both ends and *tell if we fucked
   up.

   (TODO: Cope without an old signature, in which case we generate a
   signature and chunk everything, but can't match blocks.  I think this is
   done now. ?)

   FIXME: Something seems to be wrong with the trailing chunk; it doesn't
   match.

   TODO: Have something like an MTU: after we've processed this much input,
   we flush commands whether it's necessary or not.  This will help with
   liveness downstream: there's no point leaving the downstream network idle
   for too long.  Another name for this is `early emit'.

   tridge reckons a good size is 32kb, and that the algorithm should be: if
   either the literal or the copy queues represent 32kb of input, then push
   them out.  32kb is chosen because it is typical of the size of TCP buffers 
   in many systems.

   Also, we have to keep the literal data in memory until we push it out, and 
   so we have to flush before we use up too much memory doing that.

   TODO: If it should happen that the old and new block sizes are the same,
   then we only need to keep track of one rolling checksum, which is more
   efficient.  Should we force this to always be the case?  Probably not.

   TODO: If we're encoding and realize we can't continue, then have a
   fallback mode in which everything is sent as literal data.  In fact, we
   can just map buffers straight through in that case. */

/* 
 * TODO: Maybe flush signature or literal data in here
 * somewhere too?  Doing this avoids accumulating a lot of
 * stuff in memory, at the price of sending commands more
 * frequently than is really necessary.  If we do it, we
 * should spit it out e.g. on the 64K boundary so that we
 * just avoid going to a larger command. 
 */

#include "includes.h"

static int
_hs_output_block_hash(hs_write_fn_t write_fn, void *write_priv,
		      _hs_inbuf_t * inbuf, int short_block, uint32_t weak_sum)
{
    byte_t            strong_sum[MD4_LENGTH];
    char            strong_hex[MD4_LENGTH * 2 + 2];

    _hs_write_netint(write_fn, write_priv, weak_sum);
    _hs_calc_strong_sum(inbuf->buf + inbuf->cursor, short_block,
			strong_sum, DEFAULT_SUM_LENGTH);
    hs_hexify_buf(strong_hex, strong_sum, DEFAULT_SUM_LENGTH);

    _hs_write_loop(write_fn, write_priv, strong_sum, DEFAULT_SUM_LENGTH);

    _hs_trace("output block hash at abspos=%-10d weak=%#010x strong=%s",
	      inbuf->abspos + inbuf->cursor, weak_sum, strong_hex);

    return 0;
}


static int
_hs_signature_ready(_hs_inbuf_t * inbuf, int new_block_len)
{
    int             abs_cursor = (inbuf->abspos + inbuf->cursor);

    /* Is this the right calculation?  Are we really called on every byte? */

    return (abs_cursor % new_block_len) == 0;
}




#ifdef HS_PAINFUL_HONESTY
static void
_hs_painful_check(uint32_t weak_sum, _hs_inbuf_t * inbuf, int short_block)
{
    uint32_t        checked_weak;

    checked_weak = _hs_calc_weak_sum(inbuf->buf + inbuf->cursor, short_block);
    if (weak_sum != checked_weak) {
	_hs_fatal("internal error: "
		  "at absolute position %-10d: "
		  "weak sum by rolling algorithm is %#010x, but "
		  "calculated from scratch it is %#010x",
		  inbuf->abspos + inbuf->cursor, weak_sum, checked_weak);
	abort();
    }
}
#endif				/* HS_PAINFUL_HONESTY */



ssize_t
hs_encode_old(hs_read_fn_t read_fn, void *readprivate,
	      hs_write_fn_t write_fn, void *write_priv,
	      hs_read_fn_t sigread_fn, void *sigreadprivate,
	      UNUSED(int new_block_len), hs_stats_t * stats)
{
    hs_sumset_t    *sums = 0;
    int             ret;
    hs_rollsum_t    rollsum;
    hs_rollsum_t    new_roll;
    _hs_inbuf_t    *inbuf = NULL;
    int             block_len, short_block;
    hs_membuf_t    *sig_tmpbuf, *lit_tmpbuf;
    _hs_copyq_t     copyq;
    int             token;
    int             at_eof;
    int             got_old;	/* true if there is an old signature */
    int             need_bytes;	/* how much readahead do we need? */
    hs_mdfour_t     filesum;
    byte_t          filesum_result[MD4_LENGTH];
    char            filesum_hex[MD4_LENGTH * 2 + 2];
    char            stats_str[256];

    _hs_trace("**** begin");

    hs_bzero(stats, sizeof *stats);
    hs_bzero(&copyq, sizeof copyq);
    hs_bzero(&new_roll, sizeof new_roll);

    stats->op = "encode";
    stats->algorithm = "encode_old";

    hs_mdfour_begin(&filesum);

    got_old = 1;
    sums = hs_read_sumset(sigread_fn, sigreadprivate);
    if (!sums) {
	got_old = 0;

	/* XXX: For simplicity, this is hardwired at the moment. */
	block_len = 1024;
    } else {
	block_len = sums->block_len;
    }

    assert(block_len > 0);

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
    _hs_roll_reset(&rollsum);
    do {
	/* TODO: Try to read from the input in such a size that if all of the 
	   blocks in the buffer match, we won't need to shuffle any data.
	   This isn't urgent, and in the general case we can't avoid
	   shuffling, since the matches may be offset and so not align nicely 
	   with the buffer length. */
	ret = _hs_fill_inbuf(inbuf, read_fn, readprivate);
	at_eof = (ret == 0);
	inbuf->cursor = 0;

	/* If we've reached EOF then we keep processing right up to the end,
	   whether we have a block of readahead or not. Otherwise, we stop
	   when we need more readahead to process a full block.  */
	if (at_eof)
	    need_bytes = 1;
	else
	    need_bytes = block_len;

	while (inbuf->cursor + need_bytes <= inbuf->amount) {
	    short_block = MIN(block_len, inbuf->amount - inbuf->cursor);
	    _hs_stretch_sums(inbuf->buf + inbuf->cursor, block_len,
			    short_block, &rollsum);
	    _hs_stretch_sums(inbuf->buf + inbuf->cursor, block_len,
			    short_block, &new_roll);

#ifdef HS_PAINFUL_HONESTY
	    _hs_painful_check(rollsum.weak_sum, inbuf, short_block);
#endif				/* HS_PAINFUL_HONESTY */

	    if (_hs_signature_ready(inbuf, block_len)) {
		_hs_output_block_hash(hs_membuf_write, sig_tmpbuf,
				      inbuf, short_block, new_roll.weak_sum);
	    }

	    if (got_old) {
		token = _hs_find_in_hash(rollsum.weak_sum,
					 inbuf->buf + inbuf->cursor,
					 short_block, sums, stats);
	    } else
		token = 0;

	    if (token > 0) {
		/* if we're at eof, then we should only be able to match the
		   last token, because it's the only short one.  we don't
		   store the token lengths; they're implied by the checksum.
		   the reverse isn't true: the last token might be a full
		   block, so we are allowed to match it anytime. */
		if (at_eof) {
		    assert(token == sums->count);
		}

		_hs_trace("found token %d in stream at abspos=%-8d"
			  " length=%-6d", token,
			  inbuf->abspos + inbuf->cursor, short_block);

		if (_hs_push_literal_buf
		    (lit_tmpbuf, write_fn, write_priv, stats,
		     op_kind_literal) < 0)
		    return -1;

		/* tokens are ones-based, blocks are zeros-based, so we
		   subtract 1. */
		ret = _hs_queue_copy(write_fn, write_priv,
				     &copyq, (token - 1) * block_len,
				     short_block, stats);

		/* FIXME: It's no good to skip over the block like this,
		   because we might have to update and output sums from the
		   middle of it. */
		/* FIXME: Does this update our absolute position in the right 
		   way? */
		if (ret < 0)
		    goto out;
		hs_mdfour_update(&filesum, inbuf->buf + inbuf->cursor,
				 short_block);
		inbuf->cursor += short_block;
		_hs_roll_reset(&rollsum);
		_hs_roll_reset(&new_roll);
	    } else {
		if (got_old)
		    _hs_copyq_push(write_fn, write_priv, &copyq, stats);

		/* Append this character to the outbuf */
		ret = _hs_append_literal(lit_tmpbuf,
					 inbuf->buf[inbuf->cursor]);
		_hs_trim_sums(inbuf->buf + inbuf->cursor,
			      &rollsum, short_block);
		_hs_trim_sums(inbuf->buf + inbuf->cursor,
			      &new_roll, short_block);
		hs_mdfour_update(&filesum, inbuf->buf + inbuf->cursor, 1);
		inbuf->cursor++;
	    }
	}

	_hs_slide_inbuf(inbuf);
    } while (!at_eof);

#if 0
    /* If we didn't just send a block hash, then send it now for the last
       short block. */
    if (!_hs_signature_ready(inbuf, block_len)) {
	_hs_output_block_hash(hs_membuf_write, sig_tmpbuf,
			      inbuf, short_block, new_roll.weak_sum);
    }
#endif

    /* Flush any literal or copy data remaining.  Only one or the other
       should happen. */

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

    ret = _hs_emit_filesum(write_fn, write_priv, filesum_result, MD4_LENGTH);
    if (ret < 0)
	goto out;

    /* Terminate the stream with a null */
    ret = _hs_emit_eof(write_fn, write_priv, stats);
    if (ret < 0)
	goto out;

    hs_format_stats(stats, stats_str, sizeof stats_str);
    _hs_trace("completed: %s", stats_str);

    ret = 1;

  out:
    if (sig_tmpbuf)
	hs_membuf_free(sig_tmpbuf);
    if (lit_tmpbuf)
	hs_membuf_free(lit_tmpbuf);
    if (sums)
	hs_free_sumset(sums);
    if (inbuf->buf)
	free(inbuf->buf);

    return ret;
}
