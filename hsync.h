/*=				       	-*- c-file-style: "bsd" -*-
 *
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
 * hsync.h: public interface to libhsync.  This shouldn't contain
 * anything that's not potentially part of the public interface.
 */

extern char const *const hs_libhsync_version;
extern char const *const hs_libhsync_libversion;
extern int const hs_libhsync_file_offset_bits;


/*
 * For the moment, we always work in the C library's off_t.  
 *
 * Supporting large files on 32-bit Linux is *NOT* just a matter of
 * setting these: people will typically need a different libc and
 * possibly an LFS-supported kernel too.  :-(
 *
 * Anyhow, will anyone really have single HTTP requests >=2GB?
 */

/* XXX: This should not be public; other people might be using it. */
typedef unsigned char byte_t;


#if 0
/***********************************************************************
 * Callback function prototypes
 */
typedef int     (*hs_read_fn_t) (void *readprivate, byte_t *buf, size_t len);

typedef int     (*hs_write_fn_t) (void *writeprivate, byte_t const *buf,
                                  size_t len);
#endif

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
void     hs_hexify(char *to_buf, byte_t const *from_buf, int from_len);

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
    HS_DONE,
    HS_AGAIN,
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

#if 0
/***********************************************************************
 * Blocking decode
 ***********************************************************************/
ssize_t
hs_decode(int oldread_fd,
	  hs_write_fn_t write_fn, void *write_priv,
          hs_read_fn_t ltread_fn, void *ltread_priv,
	  hs_write_fn_t newsig_fn, void *newsig_priv, hs_stats_t * stats);


/**********************************************************************
 * Nonblocking mapped decode
 **********************************************************************/
ssize_t
hs_alw_decode(int oldread_fd, int ltread_fd, 
              hs_write_fn_t write_fn, void *write_priv,
              hs_write_fn_t newsig_fn, void *newsig_priv, hs_stats_t * stats);


#endif 

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
void            hs_mdfour(byte_t *out, byte_t const *in, int n);
void            hs_mdfour_begin(/* @out@ */ hs_mdfour_t * md);
void            hs_mdfour_update(hs_mdfour_t * md, void const *,
				 size_t n);
void            hs_mdfour_result(hs_mdfour_t * md, /* @out@ */
				 byte_t *out);



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
    int dogtag;
    
    byte_t  *next_in;  /* next input byte */
    unsigned int avail_in;  /* number of bytes available at next_in */

    byte_t  *next_out; /* next output byte should be put there */
    unsigned int avail_out; /* remaining free space at next_out */

    struct hs_tube *tube;       /* small output buffer */
} hs_stream_t;

/* TODO: Account for total bytes read/written */


void hs_stream_init(hs_stream_t *);

typedef struct hs_mksum_job hs_mksum_job_t;


hs_mksum_job_t *hs_mksum_begin(hs_stream_t *stream,
                               size_t new_block_len, size_t strong_sum_len);

hs_result_t hs_mksum_iter(hs_mksum_job_t * job);

void hs_mksum_finish(hs_mksum_job_t * job);





typedef struct hs_iobuf hs_nozzle_t;
typedef struct hs_iobuf hs_fdoutbuf_t;

hs_nozzle_t * hs_nozzle_new(int fd, hs_stream_t *stream, int buf_len, char mode);
void hs_nozzle_delete(hs_nozzle_t *iot);

int hs_nozzle_in(hs_nozzle_t *iot);
int hs_nozzle_out(hs_nozzle_t *iot);


/*
 * Generate checksum for a file, write to another file.
 */
void hs_mksum_files(int in_fd, int out_fd,
                    int block_len, int inbuflen, int outbuflen);

void hs_mdfour_file(int in_fd, byte_t *result, int inbuflen);

#if 0

/***********************************************************************
 * Sumsets
 ***********************************************************************/
typedef struct hs_sumset hs_sumset_t;

hs_sumset_t    *hs_read_sumset(hs_read_fn_t, void *);
void            hs_free_sumset(hs_sumset_t * psums);
void hs_sumset_dump(hs_sumset_t const *sums);




typedef struct hs_encode_job hs_encode_job_t;


hs_encode_job_t *hs_encode_begin(int in_fd, hs_write_fn_t write_fn,
				 void *write_priv, hs_sumset_t * sums,
				 hs_stats_t * stats, size_t new_block_len);

hs_result_t     hs_encode_iter(hs_encode_job_t *);




#endif
