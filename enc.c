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
   checksum by summing the whole first block through _rs_calc_weak_sum.
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
  
   TODO: Cope without an old signature, in which case we generate a
   signature and chunk everything, but can't match blocks.  I think
   this is done now.

   FIXME: Something seems to be wrong with the trailing chunk; it
   doesn't match.  */

#include "includes.h"
#include "hsync.h"
#include "hsyncproto.h"
#include "private.h"


static int
_hs_newsig_header(int new_block_len,
		  rs_write_fn_t write_fn, void *writeprivate)
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
_hs_update_sums(inbuf_t * inbuf, int this_block_len, rollsum_t * rollsum)
{
     if (!rollsum->havesum) {
	  rollsum->weak_sum =
	       _hs_calc_weak_sum(inbuf->buf + inbuf->cursor, this_block_len);
	  _hs_trace("new weak checksum: %u", rollsum->weak_sum);
	  rollsum->havesum = 1;
	  rollsum->s1 = rollsum->weak_sum & 0xFFFF;
	  rollsum->s2 = rollsum->weak_sum >> 16;
     } else {
	  /*
	   * Add the value for this character.  The previous byte is
	   * already subtracted (below) */
	  int pos = inbuf->cursor + this_block_len - 1;
	  assert(pos >= 0);
	  if (pos <= inbuf->amount) {
	       rollsum->s1 += (inbuf->buf[pos] + CHAR_OFFSET);
	       rollsum->s2 += rollsum->s1;
	       rollsum->weak_sum = rollsum->s1 + (rollsum->s2 << 16);
	  }
     }

     return 0;
}


static int
_hs_roll_sums(inbuf_t * inbuf, rollsum_t * rollsum, int block_len)
{
     rollsum->s1 -= inbuf->buf[inbuf->cursor] + CHAR_OFFSET;
     rollsum->s2 -= block_len * (inbuf->buf[inbuf->cursor] + CHAR_OFFSET);

     return 0;
}


static int
_hs_find_match(int this_block_size, rollsum_t * rollsum, inbuf_t * inbuf,
	       struct sum_struct *sums)
{
     int token;
     token = _hs_find_in_hash(rollsum, inbuf->buf + inbuf->cursor,
			      this_block_size, sums);

     if (token > 0) {
	  _hs_trace("found token %d in stream at offset %d"
		    " length %d", token, inbuf->cursor, this_block_size);
     }
     return token;
}


static int
_hs_output_block_hash(rs_write_fn_t write_fn, void *write_priv,
		      inbuf_t * inbuf, int new_block_len,
		      rollsum_t * rollsum)
{
     char strong_sum[SUM_LENGTH];

//     _hs_trace("called, abspos=%d", inbuf->abspos + inbuf->cursor);

     _hs_write_netint(write_fn, write_priv, rollsum->weak_sum);
     _hs_calc_strong_sum(inbuf->buf + inbuf->cursor, new_block_len,
			 strong_sum);
     write_fn(write_priv, strong_sum, SUM_LENGTH);

     return 0;
}


static int _hs_signature_ready(inbuf_t * inbuf, int new_block_len)
{
     int abs_cursor = (inbuf->abspos + inbuf->cursor);

     return (abs_cursor % new_block_len) == 0;
}


static int
_hs_check_sig_version(rs_read_fn_t sigread_fn, void *sigreadprivate)
{
     uint32_t rs_remote_version;
     const uint32_t expect = HS_SIG_MAGIC;
     int ret;

     ret = _hs_read_netint(sigread_fn, sigreadprivate, &rs_remote_version);
     if (ret != 4)
	  return ret;

     if (rs_remote_version != expect) {
	  _hs_fatal("this librsync understands version %#08x."
		    " We don't take %#08x.", expect, rs_remote_version);
	  errno = EBADMSG;
	  return -1;
     }

     return ret;
}


static int
_hs_read_blocksize(rs_read_fn_t sigread_fn, void *sigreadprivate,
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



static int _hs_littok_header(rs_write_fn_t write_fn, void *write_priv)
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



ssize_t
hs_encode(rs_read_fn_t read_fn, void *readprivate,
	  rs_write_fn_t write_fn, void *write_priv,
	  rs_read_fn_t sigread_fn, void *sigreadprivate,
	  int new_block_len, hs_stats_t * stats)
{
     struct sum_struct *sums = 0;
     int ret;
     rollsum_t real_rollsum, *const rollsum = &real_rollsum;
     inbuf_t real_inbuf, *const inbuf = &real_inbuf;
     int block_len, shortened_block_len;
     hs_membuf_t *sig_tmpbuf, *lit_tmpbuf;
     _hs_copyq_t copyq;
     int token;
     int at_eof;
     int got_old;		/* true if there is an old signature */

     _hs_trace("**** beginning %s", __FUNCTION__);

     bzero(stats, sizeof *stats);
     bzero(&copyq, sizeof copyq);

     rollsum->havesum = 0;

     got_old = 1;
     ret = _hs_check_sig_version(sigread_fn, sigreadprivate);
     if (ret < 0)
	  got_old = 0;

     if (got_old) {
	  if (_hs_read_blocksize(sigread_fn, sigreadprivate, &block_len) < 0)
	       got_old = 0;
     }

     if (!block_len)
	  block_len = 512;
    
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
	  ret = _hs_fill_inbuf(inbuf, read_fn, readprivate);
	  at_eof = (ret == 0);
	  inbuf->cursor = 0;

	  /*
	   * If we've reached EOF then we keep processing right up to the end.
	   * Otherwise, we stop when we need more readahead to process a full
	   * block. 
	   */
	  while (at_eof
		 ? inbuf->cursor < inbuf->amount
		 : inbuf->cursor + block_len <= inbuf->amount) {
	       shortened_block_len = MIN(block_len, inbuf->amount - inbuf->cursor);
	       _hs_update_sums(inbuf, shortened_block_len, rollsum);

	       if (_hs_signature_ready(inbuf, block_len)) {
		    /*
		     * TODO: Maybe flush signature or literal data in here
		     * somewhere too?  Doing this avoids accumulating a lot of
		     * stuff in memory, at the price of sending commands more
		     * frequently than is really necessary.  If we do it, we
		     * should spit it out e.g. on the 64K boundary so that we
		     * just avoid going to a larger command. 
		     */
		    _hs_output_block_hash(hs_membuf_write, sig_tmpbuf,
					  inbuf, block_len, rollsum);
	       }

	       if (got_old)
		    token = _hs_find_match(shortened_block_len, rollsum, inbuf, sums);
	       else
		    token = 0;
	    
	       if (token > 0) {
		    if (_hs_flush_literal_buf(lit_tmpbuf, write_fn, write_priv, stats,
					      op_literal_1) < 0)
			 return -1;

		    /* TODO: Rather than actually sending a copy command,
		       queue it up in the hope that we'll also match on
		       succeeding blocks and can send one larger copy
		       command.  This is just an optimization.  */

		    /* Write the token */
		    ret = _hs_queue_copy(write_fn, write_priv,
					 &copyq, (token-1) * block_len,
					 shortened_block_len, stats);
		    if (ret < 0)
			 goto out;
		    inbuf->cursor += shortened_block_len;
		    rollsum->havesum = 0;
	       } else {
		    _hs_copyq_flush(write_fn, write_priv, &copyq, stats);
		 
		    /* Append this character to the outbuf */
		    ret = _hs_append_literal(lit_tmpbuf,
					     inbuf->buf[inbuf->cursor]);
		    _hs_roll_sums(inbuf, rollsum, block_len);
		    inbuf->cursor++;
	       }
	  }

	  _hs_slide_inbuf(inbuf);
     } while (!at_eof);

     /* Flush any literal or copy data remaining.  Only one or the
	other should happen. */

     ret = _hs_copyq_flush(write_fn, write_priv, &copyq, stats);
     if (ret < 0)
	  goto out;

     ret = _hs_flush_literal_buf(lit_tmpbuf, write_fn, write_priv,
				 stats, op_literal_1);
     if (ret < 0)
	  goto out;

     ret = _hs_flush_literal_buf(sig_tmpbuf, write_fn, write_priv,
				 stats, op_signature_1);
     if (ret < 0)
	  goto out;

     /* Terminate the stream with a null */
     ret = _hs_emit_eof(write_fn, write_priv);
     if (ret < 0)
	  goto out;

     _hs_trace("completed"
	       ": literal[%d cmds, %d bytes], "
	       "signature[%d cmds, %d bytes], "
	       "copy[%d cmds, %d bytes]",
	       stats->lit_cmds, stats->lit_bytes,
	       stats->sig_cmds, stats->sig_bytes,
	       stats->copy_cmds, stats->copy_bytes);
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
