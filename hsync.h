/*=                    -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * libhsync -- library for network deltas
 * $Id$
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
 * See \ref intro for an introduction to use of this library.
 */

extern char const hs_libhsync_version[];
extern char const hs_licence_string[];


/**
 * \brief Log severity levels.
 *
 * These are the same as syslog, at least in glibc.
 *
 * \sa hs_trace_set_level()
 */
typedef enum {
    HS_LOG_EMERG         = 0,   /**< System is unusable */
    HS_LOG_ALERT         = 1,   /**< Action must be taken immediately */
    HS_LOG_CRIT          = 2,   /**< Critical conditions */
    HS_LOG_ERR           = 3,   /**< Error conditions */
    HS_LOG_WARNING       = 4,   /**< Warning conditions */
    HS_LOG_NOTICE        = 5,   /**< Normal but significant condition */
    HS_LOG_INFO          = 6,   /**< Informational */
    HS_LOG_DEBUG         = 7    /**< Debug-level messages */
} hs_loglevel;



/**
 * \typedef hs_trace_fn_t
 * \brief Callback to write out log messages.
 * \param level a syslog level.
 * \param msg message to be logged.
 */
typedef void    hs_trace_fn_t(int level, char const *msg);

void            hs_trace_set_level(hs_loglevel level);

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
 */
typedef enum {
    HS_DONE =		0,	/**< Completed successfully. */
    HS_BLOCKED =	1, 	/**< Blocked waiting for more data. */
    HS_RUNNING  =       2,      /**< Not yet finished or blocked.
                                 * This value should never be returned
                                 * to the caller.  */
    
    HS_IO_ERROR =	100,   /**< Error in file or network IO. */
    HS_SYNTAX_ERROR =   101,   /**< Command line syntax error. */
    HS_MEM_ERROR =	102,   /**< Out of memory. */
    HS_SHORT_STREAM =	103,	/**< Unexpected end of input file. */
    HS_BAD_MAGIC =      104,   /**< Bad magic number at start of
                                   stream.  Probably not a libhsync
                                   file, or possibly the wrong kind of
                                   file or from an incompatible
                                   library version. */
    HS_UNIMPLEMENTED =  105,   /**< Author is lazy. */
    HS_CORRUPT =        106,   /**< Unbelievable value in stream. */
} hs_result;



/**
 * Return an English description of a ::hs_result value.
 */
char const *hs_strerror(hs_result r);


/**
 * \brief Performance statistics from a libhsync encoding or decoding
 * operation.
 *
 * \sa hs_format_stats(), hs_log_stats()
 */
typedef struct hs_stats {
        char const     *op;     /**< Human-readable name of current
                                 * operation.  For example,
                                 * "delta". */
        char const *algorithm;  /**< Algorithm used to perform the
                                 * operation. */
        int lit_cmds;           /**< Number of literal commands. */
        int lit_bytes;          /**< Number of literal bytes. */
        
    int             copy_cmds, copy_bytes;
    int             sig_cmds, sig_bytes;
    int             false_matches;
} hs_stats_t;


/** \typedef struct hs_mdfour hs_mdfour_t
 *
 * \brief MD4 message-digest accumulator.
 *
 * \sa hs_mdfour(), hs_mdfour_begin(), hs_mdfour_update(),
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
void hs_mdfour_result(hs_mdfour_t * md, unsigned char *out);

char *hs_format_stats(hs_stats_t const *, char *, size_t);

int hs_log_stats(hs_stats_t const *stats);


typedef struct hs_signature hs_signature_t;

void hs_free_sumset(hs_signature_t *);
void hs_sumset_dump(hs_signature_t const *);


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
 * hs_stream_init, and then used to create a job by hs_sig_begin or
 * similar functions.
 *
 * \sa hs_stream_t
 */
struct hs_stream_s {
        int dogtag;		/**< To identify mutilated corpse */
    
        char *next_in;		/**< Next input byte */
        unsigned int avail_in;	/**< Number of bytes available at next_in */

        char *next_out;		/**< Next output byte should be put there */
        unsigned int avail_out;	/**< Remaining free space at next_out */

        struct hs_simpl *impl; /**< \internal */
};

/**
 * Stream through which the calling application feeds data to and from the
 * library.
 *
 * \sa struct hs_stream_s
 */
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
 * Created by functions such as hs_sig_begin(), and then iterated
 * over by hs_job_iter(). */
typedef struct hs_job hs_job_t;

hs_job_t       *hs_accum_begin(hs_stream_t *);

hs_result       hs_job_iter(hs_job_t *, int ending);
hs_result       hs_job_free(hs_job_t *);

int             hs_accum_value(hs_job_t *, char *sum, size_t sum_len);

hs_job_t *hs_sig_begin(hs_stream_t *stream,
                       size_t new_block_len, size_t strong_sum_len);

hs_job_t       *hs_delta_begin(hs_stream_t *stream);

hs_job_t       *hs_loadsig_begin(hs_stream_t *, hs_signature_t **);

/**
 * \brief Callback used to retrieve parts of the basis file. */
typedef hs_result hs_copy_cb(void *opaque, size_t *len, void **result);


hs_job_t *hs_patch_begin(hs_stream_t *, hs_copy_cb *, void *copy_arg);


hs_result hs_build_hash_table(hs_signature_t* sums);
