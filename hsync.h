/*=				       	-*- c-file-style: "linux" -*-
 *
 * libhsync -- library for network deltas
 * 
 * Copyright (C) 2000, 2001 by Martin Pool <mbp@samba.org>
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


/*! \file hsync.h
 *
 * \brief Main public interface to libhsync.
 * \author Martin Pool <mbp@samba.org>
 *
 * $Id$
 *
 * This file contains interfaces that do not depend on stdio.  For
 * them, see hsyncfile.h.  For a general introduction, see \ref intro.
 */

extern char const hs_libhsync_version[];
extern char const hs_licence_string[];


/**
 * \typedef hs_trace_fn_t
 * \brief Callback to write out log messages.
 * \param level a syslog level.
 * \param msg message to be logged.
 */
typedef void    hs_trace_fn_t(int level, char const *msg);

/** 
 * Set filters on message output.
 *
 * \todo Perhaps don't depend on syslog, but instead just have yes/no
 * tracing.  Do we really need such fine-grained control?
 */
void            hs_trace_set_level(int level);

/** Set trace callback. */
void            hs_trace_to(hs_trace_fn_t *);

/** Default trace callback that writes to stderr.  Implements
 * ::hs_trace_fn_t, and may be passed to hs_trace_to(). */
void            hs_trace_stderr(int level, char const *msg);

/** Check whether the library was compiled with debugging trace
 * suport. */
int             hs_supports_trace(void);



/*!
 * Convert FROM_LEN bytes at FROM_BUF into a hex representation in
 * TO_BUF, which must be twice as long plus one byte for the null
 * terminator.
 */
void     hs_hexify(char *to_buf, void const *from_buf, int from_len);

/**
 * Decode a base64 buffer in place.  \return the number of binary
 * bytes.
 */
size_t hs_unbase64(char *s);


/**
 * Encode a buffer as base64.
 */
void hs_base64(unsigned char const *buf, int n, char *out);


/**
 * \brief Return codes from nonblocking hsync operations.
 *
 * \sa hs_result
 */
enum hs_result {
        HS_OK =			0,	/**< completed successfully */
        HS_BLOCKED =		1, 	/**< OK, but more remains to be done */
        HS_RUN_OK  =            2,      /**< not yet finished or blocked */
        HS_IO_ERROR =		(-1),   /**< error in file or network IO */
        HS_MEM_ERROR =		(-2),   /**< out of memory */
        HS_SHORT_STREAM	=	(-3),	/**< unexpected eof */
        HS_BAD_MAGIC =          (-4)    /**< illegal value on stream */
};

/** \brief Return codes from nonblocking hsync operations.
 *
 * \sa enum hs_result
 */
typedef enum hs_result hs_result;

typedef struct hs_stats {
    char const     *op;
    char const     *algorithm;
    int             lit_cmds, lit_bytes;
    int             copy_cmds, copy_bytes;
    int             sig_cmds, sig_bytes;
    int             false_matches;
} hs_stats_t;


/** \typedef struct hs_mdfour hs_mdfour_t
 *
 * \brief MD4 message-digest accumulator.
 *
 * \sa mdfour.c: hs_mdfour(), hs_mdfour_begin(), hs_mdfour_update(),
 * hs_mdfour_result()
 */
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


/**
 * Stream through which the calling application feeds data to and from the
 * library.
 *
 * On each call to hs_job_iter, the caller can make available
 *
 *  - avail_in bytes of input data at next_in
 *  - avail_out bytes of output space at next_out
 *  - some of both
 *
 * There is some internal state in impl.  Streams are initialized by
 * hs_stream_init, and then used to create a job by hs_mksum_begin or
 * similar functions.
 */
struct hs_stream_s {
        int dogtag;		/**< To identify mutilated corpse */
    
        char *next_in;		/**< Next input byte */
        unsigned int avail_in;	/**< Number of bytes available at next_in */

        char *next_out;		/**< Next output byte should be put there */
        unsigned int avail_out;	/**< Remaining free space at next_out */

        struct hs_simpl *impl; /**< \internal */
};

typedef struct hs_stream_s hs_stream_t;

void hs_stream_init(hs_stream_t *);


/** Default length of strong signatures, in bytes.  The MD4 checksum
 * is truncated to this size. */
#define HS_DEFAULT_STRONG_LEN 8

/** Default block length, if not determined by any other factors. */
#define HS_DEFAULT_BLOCK_LEN 2048


/** \typedef struct hs_job hs_job_t
 *
 * \brief Job of work to be done.
 *
 * Created by functions such as hs_mksum_begin(), and then iterated
 * over by hs_job_iter(). */
typedef struct hs_job hs_job_t;

hs_job_t       *hs_accum_begin(hs_stream_t *);

hs_result       hs_job_iter(hs_job_t *, int ending);
hs_result       hs_job_free(hs_job_t *);

int             hs_accum_value(hs_job_t *, char *sum, size_t sum_len);

hs_job_t       *hs_mksum_begin(hs_stream_t *stream,
                               size_t new_block_len, size_t strong_sum_len);

hs_job_t       *hs_delta_begin(hs_stream_t *stream);

hs_job_t       *hs_readsum_begin(hs_stream_t *stream, hs_sumset_t **);

/**
 * \typedef hs_result (hs_copy_cb)(void *opaque, size_t *len, void **result);
 *
 * Callback used to retrieve parts of the basis file. */
typedef hs_result (hs_copy_cb)(void *opaque, size_t *len, void **result);


hs_job_t       *hs_patch_begin(hs_stream_t *, hs_copy_cb *, void *copy_arg);

