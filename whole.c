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
 * whole.c -- This module contains routines for processing whole files
 * at a time.  These are normally called from rdiff, but if for some
 * reason you should want that functionality in your application here
 * they are.
 */

#include "config.h"

#include <assert.h>
#include <sys/types.h>
#include <stdlib.h>
#include <unistd.h>
#include <stdio.h>
#include <sys/file.h>
#include <string.h>
#include <syslog.h>
#include <errno.h>

#include "trace.h"
#include "fileutil.h"
#include "hsync.h"
#include "hsyncfile.h"

/* This should probably be a parameter to all functions instead, but
 * I'm not sure I want to keep it. */
extern int output_mode;

enum hs_result
hs_rdiff_delta(int argc, char **argv)
{
    FILE *new_file, *sig_file, *delta_file;
    
    if (argc != 4) {
	_hs_error("Delta operation needs three filenames: "
		  "SIGNATURE NEWFILE DELTA");
	return 1;
    }
    
    _hs_fatal("no longer implemented");
}


enum hs_result hs_rdiff_sum(int argc, char **argv)
{
#if 0
    unsigned char          result[HS_MD4_LENGTH];
    char            result_str[HS_MD4_LENGTH * 3];
    FILE *in_file;

    if (argc != 2) {
	_hs_error("Sum operation needs one filename");
	return 1;
    }
    
    in_file = _hs_file_open(argv[1], O_RDONLY);
    
    hs_mdfour_file(in_file, result);
    hs_hexify(result_str, result, HS_MD4_LENGTH);

    printf("%s\n", result_str);

    return 0;
#else
    _hs_fatal("not implemented");
#endif
}



enum hs_result hs_rdiff_patch(int argc, char *argv[])
{
        FILE *old_file, *delta_file, *new_file;
        char *outbuf;
        HSFILE *patch;
        enum hs_result result;
        size_t len;

        if (argc != 4) {
                _hs_error("Patch operation needs three filenames: "
                          "OLDFILE DELTA NEWFILE");
                return 1;
        }

        old_file = _hs_file_open(argv[1], O_RDONLY);
        delta_file = _hs_file_open(argv[2], O_RDONLY);
        new_file = _hs_file_open(argv[3], output_mode);

        outbuf = malloc(hs_outbuflen);
        assert(outbuf);
        patch = hs_patch_open(old_file, delta_file);

        do {
                len = hs_outbuflen;
                result = hs_patch_read(patch, outbuf, &len);
                fwrite(outbuf, len, 1, new_file);
        } while (result == HS_BLOCKED);

        if (result != HS_OK)
                goto failed;

        return 0;

 failed:
        _hs_error("patch failed: %s", hs_strerror(result));
    
        return 1;
}




enum hs_result hs_rdiff_signature(int argc, char *argv[])
{
        FILE *old_file, *sig_file;
        char *inbuf;
        HSFILE *mksum;
        int len;
        enum hs_result result;
    
        if (argc != 3) {
                _hs_error("Signature operation needs two filenames");
                return 1;
        }
    
        old_file = _hs_file_open(argv[1], O_RDONLY);
        sig_file = _hs_file_open(argv[2], output_mode);

        inbuf = malloc(hs_inbuflen);
        mksum = hs_mksum_open(sig_file, HS_DEFAULT_BLOCK_LEN,
                              HS_DEFAULT_STRONG_LEN);

        do {
                len = fread(inbuf, 1, hs_inbuflen, old_file);
                if (len < 0) {
                        _hs_error("%s: %s", argv[1], strerror(errno));
                        return 1;
                } 

                _hs_trace("got %d bytes from input file", len);
                result = hs_mksum_write(mksum, inbuf, len);
                if (result != HS_BLOCKED && result != HS_OK)
                        goto failed;
        } while (!feof(old_file));

        result = hs_mksum_close(mksum);
        if (result != HS_OK)
                goto failed;

        return 0;

 failed:
        _hs_error("signature failed: %s", hs_strerror(result));
    
        return 1;
}
