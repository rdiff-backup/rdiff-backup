/*=				       	-*- c-file-style: "bsd" -*-
 *
 * libhsync -- library for network deltas
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool <mbp@samba.org>
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
 * hsync.h: public interface to libhsync.  This shouldn't contain
 * anything that's not potentially part of the public interface.
 */

extern char const *const hs_libhsync_version;
extern int const hs_libhsync_file_offset_bits;


void hs_show_version(char const *program);

/*
 * For the moment, we always work in the C library's off_t.  
 *
 * Supporting large files on 32-bit Linux is *NOT* just a matter of
 * setting these: people will typically need a different libc and
 * possibly an LFS-supported kernel too.  :-(
 *
 * Anyhow, will anyone really have single HTTP requests >=2GB?
 */



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




/*======================================================================
 * Return codes from incremental functions.  On each call, we can
 * return HS_DONE if we have finished completely, HS_AGAIN if we want
 * to be called again when convenient (typically when more input data
 * is available), HS_FAILED if an error occurred.
 * *======================================================================*/
typedef enum {
    HS_OK,
    HS_COMPLETE,
    HS_FAILED
} hs_result_t;


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

    struct hs_tube *tube;       /* small output buffer */
} hs_stream_t;

/* TODO: Account for total bytes read/written */


void hs_stream_init(hs_stream_t *);




/***********************************************************************
 * Low-level delta interface.  
 ***********************************************************************/
   
typedef struct hs_mksum_job hs_mksum_job_t;


hs_mksum_job_t *hs_mksum_begin(hs_stream_t *stream,
                               size_t new_block_len, size_t strong_sum_len);
hs_result_t hs_mksum_iter(hs_mksum_job_t * job);
void hs_mksum_finish(hs_mksum_job_t * job);


int hs_delta_begin(hs_stream_t *stream);
int hs_delta(hs_stream_t *stream, int ending);
int hs_delta_finish(hs_stream_t *stream);




/***********************************************************************
 * High-level file-based interfaces.  Just pass in open file
 * descriptors and all the data will be processed.
 ***********************************************************************/

void hs_mksum_files(FILE *old_file, FILE *sig_file, int block_len);

void hs_loadsig_file(FILE *sig_file);

void hs_delta_files(FILE *input, FILE *output);

void hs_mdfour_file(FILE *input, char *result);

extern int hs_inbuflen, hs_outbuflen;


