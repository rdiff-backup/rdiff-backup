/*=                                     -*- c-file-style: "linux" -*-
 *
 * libhsync -- the library for network deltas
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool <mbp@linuxcare.com.au>
 * 
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public License
 * as published by the Free Software Foundation; either version 2.1 of
 * the License, or (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 * 
 * You should have received a copy of the GNU Lesser General Public
 * License along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */




/*
 * High-level file-based interfaces.  One end of the task is connected
 * to a stdio file stream, and the other to your program.
 */


/*
 * Buffer sizes for file IO.  You probably only need to change these
 * in testing.
 */
extern int hs_inbuflen, hs_outbuflen;


/* stdio-like file type */
typedef void HSFILE;

/*
 * Open a patch file, supplying the basis.  Reading from this will
 * return the newly patched file.
 */
HSFILE *hs_patch_open(FILE *basis, FILE *delta);

enum hs_result hs_patch_read(HSFILE *, void *buf, size_t *len);

enum hs_result hs_patch_close(HSFILE *);

enum hs_result hs_file_copy_cb(void *, size_t *, void **);


/*
 * Accept data written in, and write its signature out to a file.
 */
HSFILE *hs_mksum_open(FILE *sigfile, int block_len, int strong_sum_len);

enum hs_result hs_mksum_write(HSFILE *, void *buf, size_t len);

enum hs_result hs_mksum_close(HSFILE *);


/*
 * Calculate the MD4 sum of IN_FILE into RESULT.  RESULT is binary,
 * not hex.
 */
void hs_mdfour_file(FILE *in_file, char *result);



/*
 * rdiff-style whole-file commands.
 */
enum hs_result hs_rdiff_signature(int argc, char *argv[]);
enum hs_result hs_rdiff_delta(int argc, char *argv[]);
enum hs_result hs_rdiff_patch(int argc, char *argv[]);
enum hs_result hs_rdiff_md4(int argc, char *argv[]);
