/*=				       	-*- c-file-style: "linux" -*-
 *
 * libhsync -- library for network deltas
 * $Id$
 * 
 * Copyright (C) 2000, 2001 by Martin Pool <mbp@linuxcare.com.au>
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
                               * You should never wear your best
                               * trousers when you go out to fight for
                               * freedom and liberty.
                               *        -- Henrik Ibsen
                               */


/*
 * hsync.h: public interface to libhsync.  
 */

extern char const hs_libhsync_version[];
extern char const hs_licence_string[];


/***********************************************************************
 * Public trace functions.
 */
/* LEVEL is a syslog level. */
typedef void    hs_trace_fn_t(int level, char const *);
void            hs_trace_set_level(int level);
void            hs_trace_to(hs_trace_fn_t *);
void            hs_trace_stderr(int level, char const *msg);
int             hs_supports_trace(void);



/*
 * Convert FROM_LEN bytes at FROM_BUF into a hex representation in
 * TO_BUF, which must be twice as long plus one byte for the null
 * terminator.
 */
void     hs_hexify(char *to_buf, void const *from_buf, int from_len);

/*
 * Decode a base64 buffer in place.  Return the number of binary
 * bytes.
 */
size_t hs_unbase64(char *s);


/*
 * Encode a buffer as base64.
 */
void hs_base64(unsigned char const *buf, int n, char *out);




/* Return codes */
typedef enum hs_result {
        HS_OK =			0,	/* completed successfully */
        HS_BLOCKED =		1, 	/* OK, but more remains to be done */
        HS_RUN_OK  =            2,      /* not yet finished or blocked */
        HS_IO_ERROR =		(-1),   /* error in file or network IO */
        HS_MEM_ERROR =		(-2),   /* out of memory */
        HS_SHORT_STREAM	=	(-3),	/* unexpected eof */
        HS_BAD_MAGIC =          (-4)    /* illegal value on stream */
} hs_result;


/***********************************************************************
 * Statistics about an encode/decode operation
 ***********************************************************************/

typedef struct hs_stats {
    char const     *op;
    char const     *algorithm;
    int             lit_cmds, lit_bytes;
    int             copy_cmds, copy_bytes;
    int             sig_cmds, sig_bytes;
    int             false_matches;
} hs_stats_t;


/***********************************************************************
 * MD4 hash
 ***********************************************************************/

typedef struct hs_mdfour {
    int                 A, B, C, D;
    int                 totalN;
    int                 tail_len;
    unsigned char       tail[64];
} hs_mdfour_t;

#define HS_MD4_LENGTH 16
void            hs_mdfour(unsigned char *out, void const *in, int n); 
void            hs_mdfour_begin(/* @out@ */ hs_mdfour_t * md);
void            hs_mdfour_update(hs_mdfour_t * md, void const *,
				 size_t n);
void            hs_mdfour_result(hs_mdfour_t * md, unsigned char *out);



char *hs_format_stats(hs_stats_t const *, char *, size_t);
int hs_log_stats(hs_stats_t const *stats);

char const *hs_strerror(hs_result r);



typedef struct hs_sumset hs_sumset_t;

void hs_free_sumset(hs_sumset_t *);
void hs_sumset_dump(hs_sumset_t const *);


/***********************************************************************
 * All encoding routines follow a calling protocol similar to that of
 * zlib: the caller passes the address and length of input and output
 * buffers, plus an opaque state object.  Each routine processes as
 * much data as possible, and returns when the input buffer is empty
 * or the output buffer is full.
 */


typedef struct hs_stream_s {
        int dogtag;			/* to identify mutilated corpse */
    
        char *next_in;		/* next input byte */
        unsigned int avail_in;	/* number of bytes available at next_in */

        char *next_out;		/* next output byte should be put there */
        unsigned int avail_out;	/* remaining free space at next_out */

        struct hs_simpl *impl;
} hs_stream_t;

void hs_stream_init(hs_stream_t *);




/***********************************************************************
 * Low-level delta interface.  
 ***********************************************************************/

#define HS_DEFAULT_STRONG_LEN 8
#define HS_DEFAULT_BLOCK_LEN 2048


typedef struct hs_job hs_job_t;

hs_job_t       *hs_accum_begin(hs_stream_t *);

hs_result       hs_job_iter(hs_job_t *, int ending);
hs_result       hs_job_free(hs_job_t *);

int             hs_accum_value(hs_job_t *, char *sum, size_t sum_len);

hs_job_t       *hs_mksum_begin(hs_stream_t *stream,
                               size_t new_block_len, size_t strong_sum_len);

hs_job_t       *hs_delta_begin(hs_stream_t *stream);

/* Callback used to retrieve parts of the basis file. */
typedef hs_result (hs_copy_cb)(void *opaque, size_t *len, void **result);

hs_job_t       *hs_patch_begin(hs_stream_t *, hs_copy_cb *, void *copy_arg);

