/* -*- mode: c; c-file-style: "k&r" -*- */

/*
   librsync: combined encode and sign
   
   Copyright (C) 1999-2000 by Martin Pool.
   Copyright (C) 1999-2000 by Peter Barker.
   Copyright (C) 1999 by Andrew Tridgell
   
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
   Temple Place, Suite 330, Boston, MA 02111-1307 USA 
  */

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
   checksum by summing the whole first block through _hs_calc_weak_sum.
   After this, though, we can just let the checksum accumulate by adding the
   byte at the end of the block and letting older bytes fall off the end.  We 
   will need to calculate a whole-block checksum again after outputting a
   token, because we've skipped over the block whose state we held.

   For simplicity, we use the same block size for both the old and new
   checksums.

   We can also encode & checksum without an old signature returned
   from the client.  We revert to this mode if anything goes wrong
   with the clients signature, so this basically makes us fail-safe:
   if they scrambled or damaged their signature then they ought to
   just get a copy of the new data.

   As we read input from upstream, we have to send it into the
   encoding process and also use it to generate a new signature.  We
   never worry about caching the information because if we're encoding
   we expect to encode again in the future, and the encoder never
   needs the old value.  
   
*/


/* FIXME: Check that we use signed/unsigned integers properly.

   TODO: Add another command, which contains the checksum for the
   *whole new file* so far.  Then we can compare it at both ends and
   *tell if we fucked up.
  
   (TODO: Cope without an old signature, in which case we generate a
   signature and chunk everything, but can't match blocks.  I think
   this is done now. ?)

   FIXME: Something seems to be wrong with the trailing chunk; it
   doesn't match.

   TODO: Have something like an MTU: after we've processed this much
   input, we flush commands whether it's necessary or not.  This will
   help with liveness downstream: there's no point leaving the
   downstream network idle for too long.  Another name for this is
   `early emit'.

   tridge reckons a good size is 32kb, and that the algorithm should
   be: if either the literal or the copy queues represent 32kb of
   input, then push them out.  32kb is chosen because it is typical of
   the size of TCP buffers in many systems.

   Also, we have to keep the literal data in memory until we push it
   out, and so we have to flush before we use up too much memory doing
   that.

   TODO: If it should happen that the old and new block sizes are the
   same, then we only need to keep track of one rolling checksum,
   which is more efficient.  Should we force this to always be the
   case?  Probably not.

   TODO: If we're encoding and realize we can't continue, then have a
   fallback mode in which everything is sent as literal data.  In
   fact, we can just map buffers straight through in that case. */

/*
 * TODO: Maybe flush signature or literal data in here
 * somewhere too?  Doing this avoids accumulating a lot of
 * stuff in memory, at the price of sending commands more
 * frequently than is really necessary.  If we do it, we
 * should spit it out e.g. on the 64K boundary so that we
 * just avoid going to a larger command. 
 */

#include "includes.h"
#include "hsync.h"
#include "hsyncproto.h"
#include "private.h"
#include "emit.h"

/* Define this to check all weak checksums the slow way.  As a
   debuggging assertion, calculate the weak checksum *in full* at
   every byte, and make sure it is the same.  This will be really
   slow, but it will catch problems with rolling. */
#define HS_PAINFUL_HONESTY


static int
_hs_newsig_header(int new_block_len,
		  hs_write_fn_t write_fn, void *writeprivate)
{
     int ret;
     ret = _hs_write_netint(write_fn, writeprivate, HS_SIG_MAGIC);
     if (ret < 0)
	  return -1;

     ret = _hs_write_netint(write_fn, writeprivate, new_block_len);
     if (ret < 0)
	  return -1;

     return 0;
}


static int
_hs_update_sums(_hs_inbuf_t * inbuf, int full_block,
		int short_block, rollsum_t * rollsum)
{
     if (!rollsum->havesum) {
	  rollsum->weak_sum = _hs_calc_weak_sum(inbuf->buf + inbuf->cursor,
						short_block);
	  _hs_trace("recalculate checksum: weak=%#x", rollsum->weak_sum);
	  rollsum->s1 = rollsum->weak_sum & 0xFFFF;
	  rollsum->s2 = rollsum->weak_sum >> 16;
     } else {
	  /* Add into the checksum the value of the byte one block
             hence.  However, if that byte doesn't exist because we're
             approaching the end of the file, don't add it. */
	  if (short_block == full_block) {
	       int pos = inbuf->cursor + short_block - 1;
	       assert(pos >= 0);
	       rollsum->s1 += (inbuf->buf[pos] + CHAR_OFFSET);
	       rollsum->s2 += rollsum->s1;
	  } else {
#if 0
	       _hs_trace(__FUNCTION__ ": no byte to roll in at abspos=%d",
			 inbuf->abspos + inbuf->cursor);
#endif /* 0 */
	  }

	  rollsum->weak_sum = (rollsum->s1 & 0xffff) | (rollsum->s2 << 16);
     }

     rollsum->havesum = 1;

     return 0;
}


/* One byte rolls off the checksum. */
static int
_hs_trim_sums(_hs_inbuf_t * inbuf, rollsum_t * rollsum,
	      int short_block)
{
     rollsum->s1 -= inbuf->buf[inbuf->cursor] + CHAR_OFFSET;
     rollsum->s2 -= short_block * (inbuf->buf[inbuf->cursor] + CHAR_OFFSET);

     return 0;
}



static int
_hs_output_block_hash(hs_write_fn_t write_fn, void *write_priv,
		      _hs_inbuf_t * inbuf, int short_block,
		      rollsum_t * rollsum)
{
     char strong_sum[SUM_LENGTH];
     char strong_hex[SUM_LENGTH * 3];

     _hs_write_netint(write_fn, write_priv, rollsum->weak_sum);
     _hs_calc_strong_sum(inbuf->buf + inbuf->cursor, short_block,
			 strong_sum);
     hs_hexify_buf(strong_hex, strong_sum, SUM_LENGTH);

     _hs_write_loop(write_fn, write_priv, strong_sum, SUM_LENGTH);

     _hs_trace("output block hash at abspos=%-10d weak=%#010x strong=%s",
	       inbuf->abspos + inbuf->cursor,
	       rollsum->weak_sum, strong_hex);

     return 0;
}


static int
_hs_signature_ready(_hs_inbuf_t * inbuf, int new_block_len)
{
     int abs_cursor = (inbuf->abspos + inbuf->cursor);

     /* Is this the right calculation?  Are we really called on every
        byte? */
     
     return (abs_cursor % new_block_len) == 0;
}


static int
_hs_check_sig_version(hs_read_fn_t sigread_fn, void *sigreadprivate)
{
     uint32_t hs_remote_version;
     const uint32_t expect = HS_SIG_MAGIC;
     int ret;

     ret = _hs_read_netint(sigread_fn, sigreadprivate, &hs_remote_version);
     if (ret == 0) {
	  _hs_trace("eof on old signature stream before reading version; "
		    "there is no old signature");
	  return 0;
     } else if (ret < 0) {
	  _hs_fatal("error reading signature version");
	  return -1;
     } else if (ret != 4) {
	  _hs_fatal("bad-sized read while trying to get signature version");
	  return -1;
     }

     if (hs_remote_version != expect) {
	  _hs_fatal("this librsync understands version %#010x."
		    " We don't take %#010x.", expect, hs_remote_version);
	  errno = EBADMSG;
	  return -1;
     }

     return 1;
}


static int
_hs_read_blocksize(hs_read_fn_t sigread_fn, void *sigreadprivate,
		   int *block_len)
{
     int ret;

     ret = _hs_read_netint(sigread_fn, sigreadprivate, block_len);
     if (ret < 0) {
	  _hs_error("couldn't read block length from signature");
	  return -1;
     } else if (ret != 4) {
	  _hs_error("short read while trying to get block length");
	  return -1;
     }

     _hs_trace("The block length is %d", *block_len);

     return 0;
}



static int _hs_littok_header(hs_write_fn_t write_fn, void *write_priv)
{
     int ret;

     /*
      * Write the protocol version the token stream follows to the token
      * stream 
      */
     ret = _hs_write_netint(write_fn, write_priv, HS_LT_MAGIC);
     if (ret < 0) {
	  _hs_fatal("error writing version to littok stream");
	  return -1;
     }

     return 0;
}


#ifdef HS_PAINFUL_HONESTY
static void
_hs_painful_check(uint32_t weak_sum, _hs_inbuf_t *inbuf,
		  int short_block)
{
     uint32_t checked_weak;
     checked_weak = _hs_calc_weak_sum(inbuf->buf + inbuf->cursor,
				      short_block);
     if (weak_sum != checked_weak) {
	  _hs_fatal("internal error: "
		    "at absolute position %-10d: "
		    "weak sum by rolling algorithm is %#010x, but "
		    "calculated from scratch it is %#010x",
		    inbuf->abspos + inbuf->cursor,
		    weak_sum, checked_weak);
	  abort();
     }
}
#endif /* HS_PAINFUL_HONESTY */



ssize_t
hs_encode(hs_read_fn_t read_fn, void *readprivate,
	  hs_write_fn_t write_fn, void *write_priv,
	  hs_read_fn_t sigread_fn, void *sigreadprivate,
	  int new_block_len UNUSED, hs_stats_t * stats)
{
     struct sum_struct *sums = 0;
     int ret;
     rollsum_t real_rollsum, *const rollsum = &real_rollsum;
     _hs_inbuf_t real_inbuf, *const inbuf = &real_inbuf;
     rollsum_t new_roll;
     int block_len, short_block;
     hs_membuf_t *sig_tmpbuf, *lit_tmpbuf;
     _hs_copyq_t copyq;
     int token;
     int at_eof;
     int got_old;		/* true if there is an old signature */
     int need_bytes;		/* how much readahead do we need? */
     char *stats_str;
     hs_mdfour_t filesum;
     char filesum_result[MD4_LENGTH], filesum_hex[MD4_LENGTH * 2 + 2];
     
     _hs_trace("**** beginning %s", __FUNCTION__);

     bzero(stats, sizeof *stats);
     bzero(&copyq, sizeof copyq);
     bzero(&new_roll, sizeof new_roll);

     hs_mdfour_begin(&filesum);

     got_old = 1;
     ret = _hs_check_sig_version(sigread_fn, sigreadprivate);
     if (ret <= 0)
	  got_old = 0;

     if (got_old) {
	  if (_hs_read_blocksize(sigread_fn, sigreadprivate, &block_len) < 0)
	       got_old = 0;
     }

     /* XXX: For simplicity, this is hardwired at the moment. */
     block_len = 1024;
    
     return_val_if_fail(block_len > 0, -1);

     if (got_old) {
	  /* Put the char * sigbuffer into our structures */
	  ret = _hs_make_sum_struct(&sums, sigread_fn, sigreadprivate,
				    block_len);
	  if (ret < 0)
	       got_old = 0;
     }

     if ((ret = _hs_littok_header(write_fn, write_priv)) < 0)
	  goto out;

     /* Allocate a buffer to hold literal output */
     sig_tmpbuf = hs_membuf_new();
     lit_tmpbuf = hs_membuf_new();
     _hs_alloc_inbuf(inbuf, block_len);

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
		    _hs_trace("found token %d in stream at abspos=%-8d"
			      " length=%-6d", token,
			      inbuf->abspos+inbuf->cursor,
			      short_block);

		    if (_hs_push_literal_buf(lit_tmpbuf, write_fn, write_priv, stats,
					      op_kind_literal) < 0)
			 return -1;

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
	  _hs_free_sum_struct(&sums);
     if (inbuf->buf)
	  free(inbuf->buf);

     return ret;
}
