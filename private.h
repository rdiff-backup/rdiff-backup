/* -*- mode: c; c-file-style: "bsd" -*-

   $Id$

   private.h -- Private headers for libhsync

   Copyright (C) 2000 by Martin Pool <mbp@humbug.org.au>

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




#ifdef DO_HS_TRACE

void
_hs_trace0(char const *fmt, ...)
#ifdef __GNUC__
    __attribute__ ((format(printf, 1, 2)))
#endif
    ;

#  ifdef __GNUC__
void _hs_trace0(char const *fmt, ...)
    __attribute__ ((format(printf, 1, 2)));
#    define _hs_trace(fmt, arg...)			\
    do { _hs_trace0(__FUNCTION__ ": " fmt, ##arg);	\
    } while (0)
#  else

#    define _hs_trace _hs_trace0
    void _hs_trace0(char const *, ...);
#  endif /* ! __GNUC__ */

#else				/* !DO_HS_TRACE */
#define _hs_trace(s, str...)
#endif				/* !DO_HS_TRACE */


#define return_val_if_fail(expr, val) if (!(expr))	\
  { fprintf(stderr, "%s(%d): %s: assertion failed\n",	\
    __FILE__, __LINE__, __FUNCTION__); return (val); }

#ifdef __GNUC__

#  define _hs_fatal(s, str...) do { fprintf (stderr,	\
    "libhsync: " __FUNCTION__ ": "			\
    s "\n" , ##str); abort(); } while(0)

#define _hs_error(s, str...) {				\
     fprintf(stderr,					\
	     "libhsync: " __FUNCTION__ ": " s "\n" , ##str);	\
     } while (0)

#else /* ! __GNUC__ */

#  define _hs_fatal(s, str...) do { fprintf (stderr,    \
    "libhsync: " s "\n" , ##str); abort(); } while(0)

#  define _hs_error(s, str...) do { fprintf (stderr,    \
    "libhsync: " s "\n" , ##str); } while(0)

#endif /* ! __GNUC__ */


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


#ifdef __GNUC__
#  define UNUSED(x) x __attribute__((unused))
#elif __LCLINT__
#  define UNUSED(x) /*@unused@*/ x
#else /* !__GNUC__ && !__LCLINT__ */
#  define UNUSED(x)
#endif	/* !__GNUC__ && !__LCLINT__ */



#include "netio.h"

/* ========================================

   Literal output buffer.

   Data queued for output is now held in a MEMBUF IO pipe, and copied from
   there into the real output stream when necessary.  */
ssize_t
_hs_push_literal_buf(hs_membuf_t * litbuf,
		     hs_write_fn_t write_fn, void *write_priv,

		     hs_stats_t * stats, int kind);


void            _hs_check_blocksize(int block_len);


/* ========================================

   Memory buffers */


/* An HS_MEMBUF grows dynamically.  BUF points to an array of ALLOC bytes, of 
   which LENGTH contain data.  The cursor is at position OFS.  If BUF is
   null, then no memory has been allocated yet. */
struct hs_membuf {
    int             dogtag;
    char           *buf;
    hs_off_t        ofs;
    ssize_t         length;
    size_t          alloc;
};

/* hs_ptrbuf_t: Memory is provided by the caller, and they retain
   responsibility for it.  BUF points to an array of LENGTH bytes. The cursor 
   is currently at OFS. */
struct hs_ptrbuf {
    int             dogtag;
    char           *buf;
    hs_off_t        ofs;
    size_t          length;
};

/* ========================================

   _hs_inbuf_t: a buffer of new data waiting to be digested.

 */

/* 
   Buffer of new data waiting to be digested and encoded.  This is like a
   map_ptr, but more suitable for reading from a socket, where we can't seek, 
   and therefore can't skip forwards or rewind. Therefore we must be prepared 
   to give up any amount of memory rather than seek.

   The inbuf covers a particular part of the file with an in-memory buffer.
   The file is addressed by absolute position,

   inbuf[0..inbufamount-1] is valid, inbufamount <= inbuflen, cursor <=
   inbufamount is the next one to be processed.

   0 <= abspos is the absolute position in the input file of the start of the 
   buffer.  We need this to generate new signatures at the right positions. */
struct _hs_inbuf {
    int             tag;
    int             len;
    char           *buf;
    int             amount;
    int             cursor;
    int             abspos;
};

typedef struct _hs_inbuf _hs_inbuf_t;

int             _hs_fill_inbuf(_hs_inbuf_t *, hs_read_fn_t read_fn,

			       void *readprivate);

_hs_inbuf_t    *_hs_new_inbuf(void);
void            _hs_free_inbuf(_hs_inbuf_t *);
int             _hs_slide_inbuf(_hs_inbuf_t *);

/* ========================================

   Checksums */

#define MD4_LENGTH 16
#define SUM_LENGTH 8

/* We should make this something other than zero to improve the checksum
   algorithm: tridge suggests a prime number. */
#define CHAR_OFFSET 31

typedef unsigned short tag;

struct target {
    tag             t;
    int             i;
};

/* This structure describes all the sums generated for an instance of
   a file.  It incorporates some redundancy to make it easier to
   search. */
typedef struct hs_sum_set {
    hs_off_t        flength;	/* total file length */
    int             count;	/* how many chunks */
    int             remainder;	/* flength % block_length */
    int             block_len;	/* block_length */
    struct sum_buf *sums;	/* points to info for each chunk */
    int            *tag_table;
    struct target  *targets;
} hs_sum_set_t;


/* All blocks are the same length in the current algorithm except for the
   last block which may be short. */
typedef struct sum_buf {
    int             i;		/* index of this chunk */
    uint32_t        sum1;	/* simple checksum */
    char            strong_sum[SUM_LENGTH];	/* checksum  */
} sum_buf_t;

/* ROLLSUM_T contains the checksums that roll through the new version of the
   file as we see it.  We use this for two different things: searching for
   matches in the old version of the file, and also generating new-signature
   information to send down to the client.  */
typedef struct rollsum {
    int             havesum;	/* false if we've skipped & need to
				   recalculate */
    uint32_t        weak_sum, s1, s2;	/* weak checksum */
} rollsum_t;

uint32_t        _hs_calc_weak_sum(char const *buf1, int len);
uint32_t        _hs_calc_strong_sum(char const *buf, int len, char *sum);


#include "checksum.h"


/* ========================================

   queue of outgoing copy commands */

typedef struct _hs_copyq {
    off_t start;
    size_t           len;
} _hs_copyq_t;

int             _hs_queue_copy(hs_write_fn_t write_fn, void *write_priv,
			       _hs_copyq_t * copyq, off_t start, size_t len,
			       hs_stats_t * stats);
int             _hs_copyq_push(hs_write_fn_t write_fn, void *write_priv,
			       _hs_copyq_t * copyq, hs_stats_t * stats);


/* ========================================

   emit/inhale commands */

struct hs_op_kind_name {
    char           *name;
    int             code;
};

extern struct hs_op_kind_name const _hs_op_kind_names[];

int             _hs_emit_signature_cmd(hs_write_fn_t write_fn,
				       void *write_priv, size_t size);

int             _hs_emit_filesum(hs_write_fn_t write_fn, void *write_priv,
				 char const *buf, size_t size);

int             _hs_emit_literal_cmd(hs_write_fn_t write_fn, void *write_priv,
				     size_t size);

int             _hs_emit_checksum_cmd(hs_write_fn_t, void *, uint32_t size);

int             _hs_emit_copy(hs_write_fn_t write_fn, void *write_priv,
			      off_t offset, size_t length,
			      hs_stats_t * stats);


int             _hs_emit_eof(hs_write_fn_t write_fn, void *write_priv,
			     hs_stats_t * stats);

int             _hs_append_literal(hs_membuf_t * litbuf, char value);


int             _hs_inhale_command(hs_read_fn_t read_fn, void *read_priv,
				   int *kind, uint32_t * len, uint32_t * off);

int _hs_check_sig_version(hs_read_fn_t, void *);

/* ========================================

   map_ptr IO */

typedef struct hs_map hs_map_t;

hs_map_t       *_hs_map_file(int fd);
/*@null@*/ char const     *_hs_map_ptr(hs_map_t *, hs_off_t, ssize_t *len, int *reached_eof);
void            _hs_unmap_file(hs_map_t * map);

int             hs_file_open(char const *filename, int mode);


/* This structure holds all the state of the encoding operation.  Yes,
   it's a bit ugly to stick random variables in here like this, but we
   can't keep them on the stack, because we want to be able to suspend
   and resume the encoding operation to allow operation in a
   nonforking server.  */
typedef struct hs_encode_job {
    hs_sum_set_t *sums;

    hs_off_t sum_cursor;	/* we're about to sum the block here */
    hs_off_t search_cursor;	/* we're looking for a match or
                                   literal here */
#if 0
    ssize_t file_len;	/* total file length -- only know
                                   after seeing eof */
#endif
    rollsum_t *rollsum;
    _hs_inbuf_t *inbuf;
    rollsum_t new_roll;
    int block_len, short_block;
    hs_membuf_t *sig_tmpbuf, *lit_tmpbuf;
    _hs_copyq_t copyq;
    int token;
    int at_eof;			/* true if approaching end of the new
                                   file */
    int got_old;		/* true if there is an old signature */
    int need_bytes;		/* how much readahead do we need? */
    char *stats_str;
    hs_mdfour_t filesum;
    char filesum_result[MD4_LENGTH], filesum_hex[MD4_LENGTH * 2 + 2];
} hs_encode_job_t;


/* =======================================

   gd01 protocol.
*/
int _hs_read_sums(hs_encode_job_t *, hs_read_fn_t, void *);

int
_hs_read_blocksize(hs_read_fn_t sigread_fn, void *sigreadprivate,
		   int *block_len);

int
_hs_littok_header(hs_write_fn_t write_fn, void *write_priv);

int
_hs_newsig_header(int new_block_len,
		  hs_write_fn_t write_fn, void *writeprivate);


