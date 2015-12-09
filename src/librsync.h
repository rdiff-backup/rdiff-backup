/*=                    -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- library for network deltas
 *
 * Copyright 2000, 2001, 2014, 2015 by Martin Pool <mbp@sourcefrog.net>
 * Copyright (C) 2003 by Donovan Baarda <abo@minkirri.apana.org.au>
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
                               | You should never wear your best
                               | trousers when you go out to fight for
                               | freedom and liberty.
                               |        -- Henrik Ibsen
                               */


/*!
 * \file librsync.h
 * \brief Public header for librsync.
 */

#ifndef _RSYNC_H
#define _RSYNC_H

#include <sys/types.h>
#include "librsync-config.h"

#ifdef __cplusplus
extern "C" {
#endif

extern char const rs_librsync_version[];
extern char const rs_licence_string[];

typedef unsigned char rs_byte_t;



                          /*
                           | "The IETF already has more than enough
                           | RFCs that codify the obvious, make
                           | stupidity illegal, support truth,
                           | justice, and the IETF way, and generally
                           | demonstrate the author is a brilliant and
                           | valuable Contributor to The Standards
                           | Process."
                           |     -- Vernon Schryver
                           */


/**
 * A uint32 magic number, emitted in bigendian/network order at the start of
 * librsync files.
 **/
typedef enum {
    /** A delta file. At present, there's only one delta format.
     *
     * The four-byte literal \c "rs\x026".
     **/
    RS_DELTA_MAGIC          = 0x72730236,

    /**
     * A signature file with MD4 signatures.
     *
     * Backward compatible with
     * librsync < 1.0, but strongly deprecated because it creates a security
     * vulnerability on files containing partly untrusted data. See
     * <https://github.com/librsync/librsync/issues/5>.
     *
     * The four-byte literal \c "rs\x016".
     **/
    RS_MD4_SIG_MAGIC        = 0x72730136,

    /**
     * A signature file using the BLAKE2 hash. Supported from librsync 1.0.
     *
     * The four-byte literal \c "rs\x017".
     **/
    RS_BLAKE2_SIG_MAGIC     = 0x72730137
} rs_magic_number;



/**
 * \defgroup api_trace Debugging trace and error logging
 * @{
 
librsync can output trace or log messages as it proceeds.
Error
messages supplement return codes by describing in more detail what went
wrong. Debug messages are useful when debugging librsync or applications
that call it.

These
follow a fairly standard priority-based filtering system
(rs_trace_set_level()), using the same severity levels as UNIX syslog.
Messages by default are sent to stderr, but may be passed to an
application-provided callback (rs_trace_to(), rs_trace_fn_t()).

The default configuration is that warning and error messages are written
to stderr. This should be appropriate for many applications. If it is
not, the level and destination of messages may be changed.

Messages are passed out of librsync through a trace callback which is
passed a severity and message string. The type for this callback is
\ref rs_trace_fn_t.

The default trace function is \ref rs_trace_stderr.

The trace callback may be changed at runtime with \ref rs_trace_to.

Messages from librsync are labelled with a severity indicator of
enumerated type \ref rs_loglevel.

The application may also specify a minimum severity of interest through
\ref rs_trace_set_level.
Messages lower than the specified level
are discarded without being passed to the trace callback.

 */
 
/**
 * \brief Log severity levels.
 *
 * These are the same as syslog, at least in glibc.
 *
 * \sa rs_trace_set_level()
 */
typedef enum {
    RS_LOG_EMERG         = 0,   /**< System is unusable */
    RS_LOG_ALERT         = 1,   /**< Action must be taken immediately */
    RS_LOG_CRIT          = 2,   /**< Critical conditions */
    RS_LOG_ERR           = 3,   /**< Error conditions */
    RS_LOG_WARNING       = 4,   /**< Warning conditions */
    RS_LOG_NOTICE        = 5,   /**< Normal but significant condition */
    RS_LOG_INFO          = 6,   /**< Informational */
    RS_LOG_DEBUG         = 7    /**< Debug-level messages */
} rs_loglevel;


/**
 * \typedef rs_trace_fn_t
 * \brief Callback to write out log messages.
 * \param level a syslog level.
 * \param msg message to be logged.
 */
typedef void    rs_trace_fn_t(rs_loglevel level, char const *msg);

/**
 * Set the least important message severity that will be output.
 */
void            rs_trace_set_level(rs_loglevel level);

/** Set trace callback. */
void            rs_trace_to(rs_trace_fn_t *);

/** Default trace callback that writes to stderr.  Implements
 * ::rs_trace_fn_t, and may be passed to rs_trace_to(). */
void            rs_trace_stderr(rs_loglevel level, char const *msg);

/** Check whether the library was compiled with debugging trace
 *
 * \returns True if the library contains trace code; otherwise false.
 * If this returns false, then trying to turn trace on will achieve
 * nothing.
 */
int             rs_supports_trace(void);

/**
 * @}
 */


/**
 * Convert FROM_LEN bytes at FROM_BUF into a hex representation in
 * TO_BUF, which must be twice as long plus one byte for the null
 * terminator.
 */
void     rs_hexify(char *to_buf, void const *from_buf, int from_len);

/**
 * Decode a base64 buffer in place.  \return the number of binary
 * bytes.
 */
size_t rs_unbase64(char *s);


/**
 * Encode a buffer as base64.
 */
void rs_base64(unsigned char const *buf, int n, char *out);


/**
 * \enum rs_result
 * \brief Return codes from nonblocking rsync operations.
 */
typedef enum rs_result {
    RS_DONE =		0,	/**< Completed successfully. */
    RS_BLOCKED =	1, 	/**< Blocked waiting for more data. */
    
    /** The job is still running, and not yet finished or blocked.
     * (This value should never be seen by the application.) */
    RS_RUNNING  =       2,

    RS_TEST_SKIPPED =   77,     /**< Test neither passed or failed. */

    RS_IO_ERROR =	100,    /**< Error in file or network IO. */
    RS_SYNTAX_ERROR =   101,    /**< Command line syntax error. */
    RS_MEM_ERROR =	102,    /**< Out of memory. */
    /** Unexpected end of input file, perhaps due to a truncated file
     * or dropped network connection. */
    RS_INPUT_ENDED =	103,
    RS_BAD_MAGIC =      104,    /**< Bad magic number at start of
                                   stream.  Probably not a librsync
                                   file, or possibly the wrong kind of
                                   file or from an incompatible
                                   library version. */
    RS_UNIMPLEMENTED =  105,    /**< Author is lazy. */
    RS_CORRUPT =        106,    /**< Unbelievable value in stream. */
    RS_INTERNAL_ERROR = 107,    /**< Probably a library bug. */
    RS_PARAM_ERROR =    108     /**< Bad value passed in to library,
                                 * probably an application bug. */
} rs_result;


/**
 * Return an English description of a ::rs_result value.
 */
char const *rs_strerror(rs_result r);


/**
 * \brief Performance statistics from a librsync encoding or decoding
 * operation.
 *
 * \sa rs_format_stats(), rs_log_stats()
 */
typedef struct rs_stats {
    char const     *op;     /**< Human-readable name of current
                             * operation.  For example, "delta". */
    int             lit_cmds;   /**< Number of literal commands. */
    rs_long_t       lit_bytes;  /**< Number of literal bytes. */
    rs_long_t       lit_cmdbytes; /**< Number of bytes used in literal
                                   * command headers. */

    rs_long_t       copy_cmds, copy_bytes, copy_cmdbytes;
    rs_long_t       sig_cmds, sig_bytes;
    int             false_matches;

    rs_long_t       sig_blocks; /**< Number of blocks described by the
                                   signature. */

    size_t          block_len;

    rs_long_t       in_bytes;   /**< Total bytes read from input. */
    rs_long_t       out_bytes;  /**< Total bytes written to output. */
} rs_stats_t;


/** \typedef struct rs_mdfour rs_mdfour_t
 *
 * \brief MD4 message-digest accumulator.
 *
 * \sa rs_mdfour(), rs_mdfour_begin(), rs_mdfour_update(),
 * rs_mdfour_result()
 */
typedef struct rs_mdfour rs_mdfour_t;

extern const int RS_MD4_SUM_LENGTH, RS_BLAKE2_SUM_LENGTH;

#define RS_MAX_STRONG_SUM_LENGTH 32

typedef unsigned int rs_weak_sum_t;
typedef unsigned char rs_strong_sum_t[RS_MAX_STRONG_SUM_LENGTH];

void            rs_mdfour(unsigned char *out, void const *in, size_t);
void            rs_mdfour_begin(/* @out@ */ rs_mdfour_t * md);

/**
 * Feed some data into the MD4 accumulator.
 *
 * \param md  MD4 accumulator.
 * \param in_void Data to add.
 * \param n   Number of bytes fed in.
 */
void            rs_mdfour_update(rs_mdfour_t * md, void const *in_void,
				 size_t n);
void rs_mdfour_result(rs_mdfour_t * md, unsigned char *out);

char *rs_format_stats(rs_stats_t const *, char *, size_t);

int rs_log_stats(rs_stats_t const *stats);


/**
 * \typedef rs_signature_t
 */
typedef struct rs_signature rs_signature_t;

void rs_free_sumset(rs_signature_t *);
void rs_sumset_dump(rs_signature_t const *);


/**
 * Stream through which the calling application feeds data to and from the
 * library.
 *
 * On each call to ::rs_job_iter(), the caller can make available
 *
 *  - #avail_in bytes of input data at #next_in
 *  - #avail_out bytes of output space at #next_out
 *  - some of both
 *
 * Buffers must be allocated and passed in by the caller.  This
 * routine never allocates, reallocates or frees buffers.
 *
 * Pay attention to the meaning of the returned pointer and length
 * values.  They do \b not indicate the location and amount of
 * returned data.  Rather, if #next_out was originally set to \c
 * out_buf, then the output data begins at \c out_buf, and has length
 * <code>*next_out - \p out_buf</code>.
 *
 * Note also that if *#avail_in is nonzero on return, then not all of
 * the input data has been consumed.  The caller should either provide
 * more output buffer space and call ::rs_job_iter() again passing the same
 * #next_in and #avail_in, or put the remaining input data into some
 * persistent buffer and call rs_job_iter() with it again when there is
 * more output space.
 *
 * \sa \ref api_buffers
 */
struct rs_buffers_s {
    /** \brief Next input byte.
     * References a pointer which on entry should point to
     * the start of the data to be encoded.  Updated to point to the byte
     * after the last one consumed.
     **/
    char *next_in;
    
    /**
     * \brief Number of bytes available at next_in
     * References the length of available input.  Updated to
     * be the number of unused data bytes, which will be zero if all the
     * input was consumed.  May be zero if there is no new input, but the
     * caller just wants to drain output.
     */
    size_t avail_in;
    
     /**
      * \brief True if there is no more data after this.
      */
    int eof_in;
    
    /**
     * \brief Next output byte should be put there
     * References a pointer which on entry points to the
     * start of the output buffer.  Updated to point to the byte after the
     * last one filled.
     */
    char *next_out;
    
    /**
     * \brief Remaining free space at next_out
     *
     * References the size of available output buffer.
     * Updated to the size of unused output buffer.
     */
    size_t avail_out;
};

/**
 * Stream through which the calling application feeds data to and from the
 * library.
 *
 * \sa struct rs_buffers_s
 * \sa \ref api_buffers
 */
typedef struct rs_buffers_s rs_buffers_t;

/** Default block length, if not determined by any other factors. */
#define RS_DEFAULT_BLOCK_LEN 2048


/** \typedef rs_job_t
 *
 * \brief Job of work to be done.
 *
 * Created by functions such as rs_sig_begin(), and then iterated
 * over by ::rs_job_iter(). */
typedef struct rs_job rs_job_t;

/**
 * Bitmask values that may be passed to the options parameter of
 * rs_work().
 */
typedef enum rs_work_options {
    RS_END = 0x01               /**< End of input file; please finish
                                 * up. */
} rs_work_options;


rs_result       rs_job_iter(rs_job_t *, rs_buffers_t *);

typedef rs_result rs_driven_cb(rs_job_t *job, rs_buffers_t *buf,
                               void *opaque);

rs_result rs_job_drive(rs_job_t *job, rs_buffers_t *buf,
                       rs_driven_cb in_cb, void *in_opaque,
                       rs_driven_cb out_cb, void *out_opaque);

const rs_stats_t * rs_job_statistics(rs_job_t *job);

rs_result       rs_job_free(rs_job_t *);

int             rs_accum_value(rs_job_t *, char *sum, size_t sum_len);

/**
 * \brief Start generating a signature.
 *
 * \return A new rs_job_t into which the old file data can be passed.
 *
 * \param sig_magic Indicates the version of signature file to generate,
 * see rs_magic_number.
 *
 * \param new_block_len Size of checksum blocks.  Larger values make the
 * signature shorter, and the delta longer.
 *
 * \param strong_sum_len If non-zero, truncate the strong signatures to this
 * many bytes, to make the signature shorter.  It's recommended you leave this
 * at zero to get the full strength.
 **/
rs_job_t *rs_sig_begin(size_t new_block_len,
		       size_t strong_sum_len,
		       rs_magic_number sig_magic);

rs_job_t *rs_delta_begin(rs_signature_t *);


/**
 * \brief Read a signature from a file into an ::rs_signature structure
 * in memory.
 *
 * Once there, it can be used to generate a delta to a newer version of
 * the file.
 *
 * \note After loading the signatures, you must call
 * \ref rs_build_hash_table() before you can use them.
 */
rs_job_t *rs_loadsig_begin(rs_signature_t **);


/**
 * Call this after loading a signature to index it.
 */
rs_result rs_build_hash_table(rs_signature_t* sums);


/**
 * \brief Callback used to retrieve parts of the basis file.
 *
 * \param pos Position where copying should begin.
 *
 * \param len On input, the amount of data that should be retrieved.
 * Updated to show how much is actually available.
 *
 * \param buf On input, a buffer of at least \p *len bytes.  May be
 * updated to point to a buffer allocated by the callback if it
 * prefers.
 */
typedef rs_result rs_copy_cb(void *opaque, rs_long_t pos,
                             size_t *len, void **buf);



rs_job_t *rs_patch_begin(rs_copy_cb *, void *copy_arg);




#ifndef RSYNC_NO_STDIO_INTERFACE
/**
 * Buffer sizes for file IO.
 *
 * You probably only need to change these in testing.
 */
extern int rs_inbuflen, rs_outbuflen;


/**
 * Calculate the MD4 sum of a file.
 *
 * \param in_file File to read from.
 * \param result Binary (not hex) MD4 of the whole contents of the
 * file.
 */
void rs_mdfour_file(FILE *in_file, char *result);

/**
 * Generate the signature of a basis file, and write it out to
 * another.
 *
 * \param old_file Stdio readable file whose signature will be generated.
 *
 * \param sig_file Writable stdio file to which the signature will be written./
 *
 * \param block_len block size for signature generation, in bytes
 *
 * \param strong_len truncated length of strong checksums, in bytes
 *
 * \param sig_magic A signature magic number indicating
 * what format to use.
 *
 * \param stats Optional pointer to receive statistics.
 *
 * \sa \ref api_whole
 */
rs_result rs_sig_file(FILE *old_file, FILE *sig_file,
                      size_t block_len, size_t strong_len,
		      rs_magic_number sig_magic,
		      rs_stats_t *stats);

/**
 * Load signatures from a signature file into memory.  Return a
 * pointer to the newly allocated structure in \p sumset.
 *
 * \sa \ref api_whole
 */
rs_result rs_loadsig_file(FILE *sig_file, rs_signature_t **sumset,
    rs_stats_t *stats);

rs_result rs_file_copy_cb(void *arg, rs_long_t pos, size_t *len, void **buf);

rs_result rs_delta_file(rs_signature_t *, FILE *new_file, FILE *delta_file, rs_stats_t *);

rs_result rs_patch_file(FILE *basis_file, FILE *delta_file, FILE *new_file, rs_stats_t *);
#endif /* ! RSYNC_NO_STDIO_INTERFACE */

#ifdef __cplusplus
}
#endif

#endif /* ! _RSYNC_H */
