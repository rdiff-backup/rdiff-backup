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

#include <sys/types.h>
#include <stdint.h>

extern char const *const hs_libhsync_version;
extern char const *const hs_libhsync_libversion;
extern int const hs_libhsync_file_offset_bits;


/*
 * For the moment, we always work in the C library's off_t.  
 *
 * Supporting large files on 32-bit Linux is *NOT* just a matter of
 * setting these: people will typically need a different libc too :-(.
 * Anyhow, will anyone really have single HTTP requests >4GB?
 */

/* typedef off_t   hs_off_t; */

typedef struct stat hs_statbuf_t;


typedef unsigned char byte_t;


/***********************************************************************
 * Callback function prototypes
 */
typedef int     (*hs_read_fn_t) (void *readprivate, byte_t *buf, size_t len);

typedef int     (*hs_write_fn_t) (void *writeprivate, byte_t const *buf,
                                  size_t len);


/***********************************************************************
 * Public trace functions.
 */
/* LEVEL is a syslog level. */
typedef void    hs_trace_fn_t(int level, char const *);
void            hs_trace_set_level(int level);
void            hs_trace_to(hs_trace_fn_t *);
void            hs_trace_to_stderr(int level, char const *msg);
int             hs_supports_trace(void);


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


/* ========================================

   File buffers */

/* FILE* IO buffers */
struct file_buf;


/* This is the preferred name for new code: */
typedef struct file_buf hs_filebuf_t;

ssize_t         hs_filebuf_read(void *private, byte_t *buf, size_t len);
ssize_t         hs_filebuf_zread(void *private, byte_t *buf, size_t len);
ssize_t         hs_filebuf_write(void *private, byte_t const *buf, size_t len);
ssize_t         hs_filebuf_zwrite(void *private, byte_t const *buf, size_t len);

hs_filebuf_t   *hs_filebuf_open(char const *filename, int mode);
void            hs_filebuf_close(hs_filebuf_t * fbuf);
void            hs_filebuf_add_cache(hs_filebuf_t * fb, int);

hs_filebuf_t   *hs_filebuf_from_fd(int);
/* hs_filebuf_t   *hs_filebuf_from_file(FILE * fp); */


/* ========================================

   Memory buffers */

typedef struct hs_membuf hs_membuf_t;

off_t        hs_membuf_tell(void *private);
ssize_t         hs_membuf_write(void *private, byte_t const *buf, size_t len);
ssize_t         hs_membuf_read(void *private, byte_t *buf, size_t len);
ssize_t         hs_choose_block_size(ssize_t file_len);
hs_membuf_t    *hs_membuf_new(void);
void            hs_membuf_free(hs_membuf_t *);
void            hs_membuf_truncate(hs_membuf_t * mb);
size_t          hs_membuf_getbuf(hs_membuf_t const *mb, byte_t const **buf);
hs_membuf_t    *hs_membuf_on_buffer(byte_t *buf, int len);
ssize_t hs_membuf_read_ofs(void *private, byte_t *buf, size_t len, off_t ofs);

typedef struct hs_ptrbuf hs_ptrbuf_t;

off_t        hs_ptrbuf_tell(void *private);
ssize_t         hs_ptrbuf_write(void *private, byte_t const *buf, size_t len);
ssize_t         hs_ptrbuf_read(void *private, byte_t *buf, size_t len);
ssize_t         hs_choose_block_size(ssize_t file_len);
hs_ptrbuf_t    *hs_ptrbuf_on_buffer(byte_t *buf, int len);
void            hs_ptrbuf_truncate(hs_ptrbuf_t * mb);
size_t          hs_ptrbuf_getbuf(hs_ptrbuf_t const *mb, byte_t const **buf);
hs_ptrbuf_t    *hs_ptrbuf_on_buffer(byte_t *buf, int len);
ssize_t hs_ptrbuf_read_ofs(void *private, byte_t *buf, size_t len, off_t ofs);

/***********************************************************************
 * MD4 hash
 ***********************************************************************/

typedef struct hs_mdfour {
    uint32_t        A, B, C, D;
    uint32_t        totalN;
    int             tail_len;
    byte_t            tail[64];
} hs_mdfour_t;

void            hs_mdfour(byte_t *out, byte_t const *in, int n);
void            hs_mdfour_begin( /* @out@ */ hs_mdfour_t * md);
void            hs_mdfour_update(hs_mdfour_t * md, void const *,
				 size_t n);
void            hs_mdfour_result(hs_mdfour_t * md, /* @out@ */
				 byte_t *out);


void     hs_hexify_buf(char *to_buf, byte_t const *from_buf, int from_len);


char *hs_format_stats(hs_stats_t const *, char *, size_t);
int hs_log_stats(hs_stats_t const *stats);


/***********************************************************************
 * Nonblocking encoding interfaces
 ***********************************************************************/
typedef struct hs_mksum_job hs_mksum_job_t;


hs_mksum_job_t *hs_mksum_begin(int in_fd,
			       hs_write_fn_t write_fn, void *write_priv,
			       size_t new_block_len, size_t strong_sum_len);

hs_result_t     hs_mksum_iter(hs_mksum_job_t * job);



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


/***********************************************************************
 * Utilities 
 ***********************************************************************/

extern void     hs_bzero(void *buf, size_t size);

/**********************************************************************
 * File utilities
 **********************************************************************/
void hs_file_close(int fd);
int hs_file_open(char const *filename, int mode);
