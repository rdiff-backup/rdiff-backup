/* -*- mode: c; c-file-style: "gnu" -*-  */

/* private.h -- Private headers for libhsync
   Copyright (C) 2000 by Martin Pool <mbp@humbug.org.au>

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
   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
   USA
*/

#define _hs_trace(s, str...) fprintf (stderr, \
  "        " __FUNCTION__ ": " s "\n" , ##str)

#define return_val_if_fail(expr, val) if (!(expr)) \
  { fprintf(stderr, "%s(%d): %s: assertion failed\n", \
    __FILE__, __LINE__, __FUNCTION__); return (val); }

#define _hs_error(s, str...) { fprintf (stderr, \
  s , ##str); abort(); }


/* ========================================

   Nice macros */

#undef	MAX
#define MAX(a, b)  (((a) > (b)) ? (a) : (b))

#undef	MIN
#define MIN(a, b)  (((a) < (b)) ? (a) : (b))

#undef	ABS
#define ABS(a)	   (((a) < 0) ? -(a) : (a))

#undef	CLAMP
#define CLAMP(x, low, high)  (((x) > (high)) ? (high) : (((x) < (low)) ? (low) : (x)))



/* ========================================

   Net IO functions */

int _hs_do_read(rs_read_fn_t, void *readprivate, char *buf, size_t len);

int _hs_do_write(rs_write_fn_t, void *writeprivate, char const *buf, int len);

int _hs_read_netlong(rs_read_fn_t read_fn, void *read_priv, uint32_t *result);

int _hs_read_netshort(rs_read_fn_t read_fn, void *read_priv, uint16_t *result);


int _hs_read_netbyte (rs_read_fn_t read_fn, void *read_priv, uint8_t * result);

int _hs_write_netlong (rs_write_fn_t write_fn, void *write_priv, uint32_t out);

int _hs_write_netshort (rs_write_fn_t write_fn, void *write_priv, uint16_t out);

int _hs_write_netbyte (rs_write_fn_t write_fn, void *write_priv, uint8_t out);

int _hs_copy_ofs (uint32_t offset, uint32_t length,
		  rs_readofs_fn_t readofs_fn, void *readofs_priv,
		  rs_write_fn_t write_fn, void *write_priv);

/* ========================================

   Literal output buffer.

   Data queued for output is now held in a MEMBUF IO pipe, and copied
   from there into the real output stream when necessary.  */
ssize_t
_hs_flush_literal_buf (hs_membuf_t * litbuf,
		       rs_write_fn_t write_fn, void *write_priv,
		       hs_stats_t *stats,
		       int code_base);


void _hs_check_blocksize(int block_len);


/* ========================================

   emit gd-plus commands
*/

int _hs_emit_chunk_cmd (rs_write_fn_t write_fn, void *write_priv,
			uint32_t size, int base);


int _hs_emit_copy (rs_write_fn_t write_fn, void *write_priv,
		   uint32_t offset, uint32_t length,
		   hs_stats_t *stats);


int _hs_emit_eof (rs_write_fn_t write_fn, void *write_priv);

int _hs_append_literal (hs_membuf_t * litbuf, char value);

/* ========================================

   Memory buffers
*/


/* You can either set BUF and LENGTH, or you can leave length as -1
   and let the buffer be reallocated on demand. */

struct hs_membuf {
  char *buf;
  off_t ofs;
  ssize_t length;
  size_t alloc;
};

/* Buffer of new data waiting to be digested and encoded.
   
   inbuf[0..inbufamount-1] is valid, inbufamount <= inbuflen,
   cursor <= inbufamount is the next one to be processed.
   
   0 <= abspos is the absolute position in the input file of the start
   of the buffer.  We need this to generate new signatures at the
   right positions. */
typedef struct inbuf
{
  int len;
  char *buf;
  int amount;
  int cursor;
  int abspos;
}
inbuf_t;

int _hs_fill_inbuf (inbuf_t * inbuf, rs_read_fn_t read_fn, void *readprivate);

int _hs_alloc_inbuf (inbuf_t * inbuf, int block_len);

int _hs_slide_inbuf (inbuf_t *inbuf);

/* ========================================

  Checksums
*/

#define MD4_LENGTH 16
#define SUM_LENGTH 8
#define CHAR_OFFSET 0

typedef unsigned short tag;

struct target
{
  tag t;
  int i;
};

typedef struct sum_struct {
  off_t flength;		/* total file length */
  int count;		/* how many chunks */
  int remainder;		/* flength % block_length */
  int n;			/* block_length */
  struct sum_buf *sums;	/* points to info for each chunk */
  int *tag_table;
  struct target *targets;
} sum_struct_t;


/* All blocks are the same length in the current algorithm except for
   the last block which may be short. */
typedef struct sum_buf {
  off_t offset;		/* offset in file of this chunk */
  int len;		/* length of chunk of file */
  int i;			/* index of this chunk */
  uint32_t sum1;	        /* simple checksum */
  char sum2[SUM_LENGTH];	/* checksum  */
} sum_buf_t;

/* ROLLSUM_T contains the checksums that roll through the new version
   of the file as we see it.  We use this for two different things:
   searching for matches in the old version of the file, and also
   generating new-signature information to send down to the client.  */
typedef struct rollsum
{
  int havesum;			/* false if we've skipped & need to
				   recalculate */
  uint32_t weak_sum, s1, s2;		/* weak checksum */
}
rollsum_t;

uint32_t _hs_calc_weak_sum (char const *buf1, int len);
uint32_t _hs_calc_strong_sum (char const *buf, int len, char *sum);



/* ========================================

   Things to do with searching through the hashtable of blocks from
   downstream.  */

int _hs_find_in_hash (rollsum_t *rollsum,
		      char const *inbuf, int block_len,
		      struct sum_struct const *sigs);

int _hs_build_hash_table (struct sum_struct *sums);

int
_hs_make_sum_struct(struct sum_struct ** signatures,
		    rs_read_fn_t sigread_fn, void * sigreadprivate,
		    int block_len);

void _hs_free_sum_struct(struct sum_struct **psums);
