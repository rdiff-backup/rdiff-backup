/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
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

                              /*=
                               | You should never wear your best
                               | trousers when you go out to fight for
                               | freedom and liberty.
                               |        -- Henrik Ibsen
                               */

/** \file librsync.h Public header for librsync. */

#ifndef _RSYNC_H
#  define _RSYNC_H

#  include <sys/types.h>
#  include <stdio.h>
#  include <stdint.h>
#  include <time.h>

#  ifdef __cplusplus
extern "C" {
#  endif

/** Library version string.
 *
 * \sa \ref versioning */
extern char const rs_librsync_version[];

/** Summary of the licence for librsync. */
extern char const rs_licence_string[];

typedef uint8_t rs_byte_t;
typedef intmax_t rs_long_t;

                          /*=
                           | "The IETF already has more than enough
                           | RFCs that codify the obvious, make
                           | stupidity illegal, support truth,
                           | justice, and the IETF way, and generally
                           | demonstrate the author is a brilliant and
                           | valuable Contributor to The Standards
                           | Process."
                           |     -- Vernon Schryver
                           */

/** A uint32 magic number, emitted in bigendian/network order at the start of
 * librsync files. */
typedef enum {
    /** A delta file.
     *
     * At present, there's only one delta format.
     *
     * The four-byte literal \c "rs\x026". */
    RS_DELTA_MAGIC = 0x72730236,

    /** A signature file with MD4 signatures.
     *
     * Backward compatible with librsync < 1.0, but strongly deprecated because
     * it creates a security vulnerability on files containing partly untrusted
     * data. See <https://github.com/librsync/librsync/issues/5>.
     *
     * The four-byte literal \c "rs\x016".
     *
     * \sa rs_sig_begin() */
    RS_MD4_SIG_MAGIC = 0x72730136,

    /** A signature file using the BLAKE2 hash. Supported from librsync 1.0.
     *
     * The four-byte literal \c "rs\x017".
     *
     * \sa rs_sig_begin() */
    RS_BLAKE2_SIG_MAGIC = 0x72730137
} rs_magic_number;

/** Log severity levels.
 *
 * These are the same as syslog, at least in glibc.
 *
 * \sa rs_trace_set_level() \sa \ref api_trace */
typedef enum {
    RS_LOG_EMERG = 0,           /**< System is unusable */
    RS_LOG_ALERT = 1,           /**< Action must be taken immediately */
    RS_LOG_CRIT = 2,            /**< Critical conditions */
    RS_LOG_ERR = 3,             /**< Error conditions */
    RS_LOG_WARNING = 4,         /**< Warning conditions */
    RS_LOG_NOTICE = 5,          /**< Normal but significant condition */
    RS_LOG_INFO = 6,            /**< Informational */
    RS_LOG_DEBUG = 7            /**< Debug-level messages */
} rs_loglevel;

/** \typedef rs_trace_fn_t Callback to write out log messages.
 *
 * \param level a syslog level.
 *
 * \param msg message to be logged.
 *
 * \sa \ref api_trace */
typedef void rs_trace_fn_t(rs_loglevel level, char const *msg);

/** Set the least important message severity that will be output.
 *
 * \sa \ref api_trace */
void rs_trace_set_level(rs_loglevel level);

/** Set trace callback.
 *
 * \sa \ref api_trace */
void rs_trace_to(rs_trace_fn_t *);

/** Default trace callback that writes to stderr.
 *
 * Implements ::rs_trace_fn_t, and may be passed to rs_trace_to().
 *
 * \sa \ref api_trace */
void rs_trace_stderr(rs_loglevel level, char const *msg);

/** Check whether the library was compiled with debugging trace.
 *
 * \returns True if the library contains trace code; otherwise false.
 *
 * If this returns false, then trying to turn trace on will achieve nothing.
 *
 * \sa \ref api_trace */
int rs_supports_trace(void);

/** Convert \p from_len bytes at \p from_buf into a hex representation in \p
 * to_buf, which must be twice as long plus one byte for the null terminator. */
void rs_hexify(char *to_buf, void const *from_buf, int from_len);

/** Decode a base64 buffer in place.
 *
 * \returns The number of binary bytes. */
size_t rs_unbase64(char *s);

/** Encode a buffer as base64. */
void rs_base64(unsigned char const *buf, int n, char *out);

/** \enum rs_result Return codes from nonblocking rsync operations.
 *
 * \sa rs_strerror() \sa api_callbacks */
typedef enum rs_result {
    RS_DONE = 0,                /**< Completed successfully. */
    RS_BLOCKED = 1,             /**< Blocked waiting for more data. */
    RS_RUNNING = 2,             /**< The job is still running, and not yet
                                 * finished or blocked. (This value should
                                 * never be seen by the application.) */
    RS_TEST_SKIPPED = 77,       /**< Test neither passed or failed. */
    RS_IO_ERROR = 100,          /**< Error in file or network IO. */
    RS_SYNTAX_ERROR = 101,      /**< Command line syntax error. */
    RS_MEM_ERROR = 102,         /**< Out of memory. */
    RS_INPUT_ENDED = 103,       /**< Unexpected end of input file, perhaps due
                                 * to a truncated file or dropped network
                                 * connection. */
    RS_BAD_MAGIC = 104,         /**< Bad magic number at start of stream.
                                 * Probably not a librsync file, or possibly
                                 * the wrong kind of file or from an
                                 * incompatible library version. */
    RS_UNIMPLEMENTED = 105,     /**< Author is lazy. */
    RS_CORRUPT = 106,           /**< Unbelievable value in stream. */
    RS_INTERNAL_ERROR = 107,    /**< Probably a library bug. */
    RS_PARAM_ERROR = 108        /**< Bad value passed in to library, probably
                                 * an application bug. */
} rs_result;

/** Return an English description of a ::rs_result value. */
char const *rs_strerror(rs_result r);

/** Performance statistics from a librsync encoding or decoding operation.
 *
 * \sa api_stats \sa rs_format_stats() \sa rs_log_stats() */
typedef struct rs_stats {
    char const *op;             /**< Human-readable name of current operation.
                                 * For example, "delta". */
    int lit_cmds;               /**< Number of literal commands. */
    rs_long_t lit_bytes;        /**< Number of literal bytes. */
    rs_long_t lit_cmdbytes;     /**< Number of bytes used in literal command
                                 * headers. */

    rs_long_t copy_cmds, copy_bytes, copy_cmdbytes;
    rs_long_t sig_cmds, sig_bytes;
    int false_matches;

    rs_long_t sig_blocks;       /**< Number of blocks described by the
                                 * signature. */

    size_t block_len;

    rs_long_t in_bytes;         /**< Total bytes read from input. */
    rs_long_t out_bytes;        /**< Total bytes written to output. */

    time_t start, end;
} rs_stats_t;

/** \typedef struct rs_mdfour rs_mdfour_t
 *
 * \brief MD4 message-digest accumulator.
 *
 * \sa rs_mdfour(), rs_mdfour_begin(), rs_mdfour_update(), rs_mdfour_result() */
typedef struct rs_mdfour rs_mdfour_t;

extern const int RS_MD4_SUM_LENGTH, RS_BLAKE2_SUM_LENGTH;

#  define RS_MAX_STRONG_SUM_LENGTH 32

typedef uint32_t rs_weak_sum_t;
typedef unsigned char rs_strong_sum_t[RS_MAX_STRONG_SUM_LENGTH];

void rs_mdfour(unsigned char *out, void const *in, size_t);
void rs_mdfour_begin( /* @out@ */ rs_mdfour_t *md);

/** Feed some data into the MD4 accumulator.
 *
 * \param md MD4 accumulator.
 *
 * \param in_void Data to add.
 *
 * \param n Number of bytes fed in. */
void rs_mdfour_update(rs_mdfour_t *md, void const *in_void, size_t n);
void rs_mdfour_result(rs_mdfour_t *md, unsigned char *out);

/** Return a human-readable representation of statistics.
 *
 * The string is truncated if it does not fit. 100 characters should be
 * sufficient space.
 *
 * \param stats Statistics from an encoding or decoding operation.
 *
 * \param buf Buffer to receive result.
 *
 * \param size Size of buffer.
 *
 * \return \p buf.
 *
 * \sa \ref api_stats */
char *rs_format_stats(rs_stats_t const *stats, char *buf, size_t size);

/** Write statistics into the current log as text.
 *
 * \sa \ref api_stats \sa \ref api_trace */
int rs_log_stats(rs_stats_t const *stats);

/** \typedef rs_signature_t */
typedef struct rs_signature rs_signature_t;

/** Deep deallocation of checksums. */
void rs_free_sumset(rs_signature_t *);

/** Dump signatures to the log. */
void rs_sumset_dump(rs_signature_t const *);

/** Description of input and output buffers.
 *
 * On each call to ::rs_job_iter(), the caller can make available
 *
 * - #avail_in bytes of input data at #next_in
 *
 * - #avail_out bytes of output space at #next_out
 *
 * - or some of both
 *
 * Buffers must be allocated and passed in by the caller.
 *
 * On input, the buffers structure must contain the address and length of the
 * input and output buffers. The library updates these values to indicate the
 * amount of \b remaining buffer. So, on return, #avail_out is not the amount
 * of output data produced, but rather the amount of output buffer space still
 * available.
 *
 * This means that the values on return are consistent with the values on
 * entry, and suitable to be passed in on a second call, but they don't
 * directly tell you how much output data was produced.
 *
 * Note also that if *#avail_in is nonzero on return, then not all of the input
 * data has been consumed. The caller should either provide more output buffer
 * space and call ::rs_job_iter() again passing the same #next_in and
 * #avail_in, or put the remaining input data into some persistent buffer and
 * call rs_job_iter() with it again when there is more output space.
 *
 * \sa rs_job_iter() */
struct rs_buffers_s {
    /** Next input byte.
     *
     * References a pointer which on entry should point to the start of the
     * data to be encoded. Updated to point to the byte after the last one
     * consumed. */
    char *next_in;

    /** Number of bytes available at next_in.
     *
     * References the length of available input. Updated to be the number of
     * unused data bytes, which will be zero if all the input was consumed. May
     * be zero if there is no new input, but the caller just wants to drain
     * output. */
    size_t avail_in;

    /** True if there is no more data after this. */
    int eof_in;

    /** Next output byte should be put there.
     *
     * References a pointer which on entry points to the start of the output
     * buffer. Updated to point to the byte after the last one filled. */
    char *next_out;

    /** Remaining free space at next_out.
     *
     * References the size of available output buffer. Updated to the size of
     * unused output buffer. */
    size_t avail_out;
};

/** \sa ::rs_buffers_s */
typedef struct rs_buffers_s rs_buffers_t;

/** Default block length, if not determined by any other factors. */
#  define RS_DEFAULT_BLOCK_LEN 2048

/** Job of work to be done.
 *
 * Created by functions such as rs_sig_begin(), and then iterated over by
 * rs_job_iter().
 *
 * The contents are opaque to the application, and instances are always
 * allocated by the library.
 *
 * \sa \ref api_streaming \sa rs_job */
typedef struct rs_job rs_job_t;

/** Run a ::rs_job state machine until it blocks (::RS_BLOCKED), returns an
 * error, or completes (::RS_DONE).
 *
 * \param job Description of job state.
 *
 * \param buffers Pointer to structure describing input and output buffers.
 *
 * \return The ::rs_result that caused iteration to stop.
 *
 * \c buffers->eof_in should be true if there is no more data after what's in
 * the input buffer. The final block checksum will run across whatever's in
 * there, without trying to accumulate anything else.
 *
 * \sa \ref api_streaming */
rs_result rs_job_iter(rs_job_t *job, rs_buffers_t *buffers);

/** Type of application-supplied function for rs_job_drive().
 *
 * \sa \ref api_pull */
typedef rs_result rs_driven_cb(rs_job_t *job, rs_buffers_t *buf,
                               void *opaque);

/** Actively process a job, by making callbacks to fill and empty the buffers
 * until the job is done. */
rs_result rs_job_drive(rs_job_t *job, rs_buffers_t *buf, rs_driven_cb in_cb,
                       void *in_opaque, rs_driven_cb out_cb, void *out_opaque);

/** Return a pointer to the statistics in a job. */
const rs_stats_t *rs_job_statistics(rs_job_t *job);

/** Deallocate job state. */
rs_result rs_job_free(rs_job_t *);

/** Start generating a signature.
 *
 * \return A new rs_job_t into which the old file data can be passed.
 *
 * \param sig_magic Indicates the version of signature file format to generate.
 * See ::rs_magic_number.
 *
 * \param new_block_len Size of checksum blocks. Larger values make the
 * signature shorter, and the delta longer.
 *
 * \param strong_sum_len If non-zero, truncate the strong signatures to this
 * many bytes, to make the signature shorter. It's recommended you leave this
 * at zero to get the full strength.
 *
 * \sa rs_sig_file() */
rs_job_t *rs_sig_begin(size_t new_block_len, size_t strong_sum_len,
                       rs_magic_number sig_magic);

/** Prepare to compute a streaming delta.
 *
 * \todo Add a version of this that takes a ::rs_magic_number controlling the
 * delta format. */
rs_job_t *rs_delta_begin(rs_signature_t *);

/** Read a signature from a file into an ::rs_signature structure in memory.
 *
 * Once there, it can be used to generate a delta to a newer version of the
 * file.
 *
 * \note After loading the signatures, you must call \ref rs_build_hash_table()
 * before you can use them. */
rs_job_t *rs_loadsig_begin(rs_signature_t **);

/** Call this after loading a signature to index it.
 *
 * Use rs_free_sumset() to release it after use. */
rs_result rs_build_hash_table(rs_signature_t *sums);

/** Callback used to retrieve parts of the basis file.
 *
 * \param pos Position where copying should begin.
 *
 * \param len On input, the amount of data that should be retrieved. Updated to
 * show how much is actually available, but should not be greater than the
 * input value.
 *
 * \param buf On input, a buffer of at least \p *len bytes. May be updated to
 * point to a buffer allocated by the callback if it prefers. */
typedef rs_result rs_copy_cb(void *opaque, rs_long_t pos, size_t *len,
                             void **buf);

/** Apply a \a delta to a \a basis file to recreate the \a new file.
 *
 * This gives you back a ::rs_job_t object, which can be cranked by calling
 * rs_job_iter() and updating the stream pointers. When finished, call
 * rs_job_free() to dispose of it.
 *
 * \param copy_cb Callback used to retrieve content from the basis file.
 *
 * \param copy_arg Opaque environment pointer passed through to the callback.
 *
 * \todo As output is produced, accumulate the MD4 checksum of the output. Then
 * if we find a CHECKSUM command we can check it's contents against the output.
 *
 * \todo Implement COPY commands.
 *
 * \sa rs_patch_file() \sa \ref api_streaming */
rs_job_t *rs_patch_begin(rs_copy_cb * copy_cb, void *copy_arg);

#  ifndef RSYNC_NO_STDIO_INTERFACE
#    include <stdio.h>

/** Buffer sizes for file IO.
 *
 * The default 0 means use the recommended buffer size for the operation being
 * performed, any other value will override the recommended sizes. You probably
 * only need to change these in testing. */
extern int rs_inbuflen, rs_outbuflen;

/** Generate the signature of a basis file, and write it out to another.
 *
 * \param old_file Stdio readable file whose signature will be generated.
 *
 * \param sig_file Writable stdio file to which the signature will be written./
 *
 * \param block_len block size for signature generation, in bytes
 *
 * \param strong_len truncated length of strong checksums, in bytes
 *
 * \param sig_magic A signature magic number indicating what format to use.
 *
 * \param stats Optional pointer to receive statistics.
 *
 * \sa \ref api_whole */
rs_result rs_sig_file(FILE *old_file, FILE *sig_file, size_t block_len,
                      size_t strong_len, rs_magic_number sig_magic,
                      rs_stats_t *stats);

/** Load signatures from a signature file into memory.
 *
 * \param sig_file Readable stdio file from which the signature will be read.
 *
 * \param sumset on return points to the newly allocated structure.
 *
 * \param stats Optional pointer to receive statistics.
 *
 * \sa \ref api_whole */
rs_result rs_loadsig_file(FILE *sig_file, rs_signature_t **sumset,
                          rs_stats_t *stats);

/** ::rs_copy_cb that reads from a stdio file. */
rs_result rs_file_copy_cb(void *arg, rs_long_t pos, size_t *len, void **buf);

/** Generate a delta between a signature and a new file into a delta file.
 *
 * \sa \ref api_whole */
rs_result rs_delta_file(rs_signature_t *, FILE *new_file, FILE *delta_file,
                        rs_stats_t *);

/** Apply a patch, relative to a basis, into a new file.
 *
 * \sa \ref api_whole */
rs_result rs_patch_file(FILE *basis_file, FILE *delta_file, FILE *new_file,
                        rs_stats_t *);
#  endif                        /* !RSYNC_NO_STDIO_INTERFACE */

#  ifdef __cplusplus
}                               /* extern "C" */
#  endif

#endif                          /* !_RSYNC_H */
