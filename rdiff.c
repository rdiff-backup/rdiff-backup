/*=				       	-*- c-file-style: "linux" -*-
 *
 * rdiff -- generate and apply rsync signatures and deltas
 * $Id$
 * 
 * Copyright (C) 1999, 2000, 2001 by Martin Pool <mbp@linuxcare.com.au>
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

			      /* .. after a year and a day, mourning is
			       * dangerous to the survivor and troublesome
			       * to the dead.
			       *	      -- Harold Bloom		    */

#include <config.h>

#include <assert.h>
#include <sys/types.h>
#include <stdlib.h>
#include <unistd.h>
#include <stdio.h>
#include <sys/file.h>
#include <string.h>
#include <syslog.h>
#include <errno.h>
#include <getopt.h>

#include "hsync.h"
#include "trace.h"
#include "isprefix.h"
#include "fileutil.h"
#include "util.h"
#include "hsyncfile.h"


int block_len = 2048;

/* Overwrite existing files. */
int force = 0;
int output_mode = O_WRONLY|O_CREAT|O_TRUNC|O_EXCL;

/*
 * TODO: Refuse to write binary data to terminals unless --forced.
 *
 * TODO: Perhaps change to using popt rather than getopt?  Do this if
 * we ever add arguments requiring more tricky parsing.
 */

#define PROGRAM "rdiff"


const struct option longopts[] = {
        { "help", no_argument, 0, 'h' },
        { "version", no_argument, 0, 'V' },
        { "licence", no_argument, 0, 'L' },
        { "verbose", no_argument, 0, 'v' },
        { "force", no_argument, 0, 'f' },
        { "input-buffer", required_argument, 0, 'I' },
        { "output-buffer", required_argument, 0, 'O' },
        { NULL, 0, 0, 0 }
};


static void show_usage(void)
{
    printf("Usage: %s [OPTIONS] signature OLDFILE SIGNATURE\n"
           "   or: %s [OPTIONS] delta SIGNATURE NEWFILE DELTA\n"
           "   or: %s [OPTIONS] patch OLDFILE DELTA NEWFILE\n"
           "   or: %s [OPTIONS] sum INPUT\n"
           "\n"
           "Compute rsync checksums or deltas, or apply a delta.\n"
           "\n"
           "  -f, --force               overwrite existing files\n"
           "  -v, --verbose             trace internal processing\n"
           "  -I, --input-buffer=BYTES  input buffer size\n"
           "  -O, --output-buffer=BYTES output buffer size\n"
           "      --help                display this help and exit\n"
           "      --version             output version information and exit\n"
           "      --licence             show summary copying terms and exit\n"
           ,
           PROGRAM, PROGRAM, PROGRAM, PROGRAM);
}


static void process_args(int argc, char **argv)
{
    int             c, longind;

    while ((c = getopt_long(argc, argv, "vfI:O:", longopts, &longind)) != -1) {
	switch (c) {
	case '?':
	case ':':
	    exit(1);
	case 'f':
	    force = 1;
	    output_mode &= ~O_EXCL;
	    break;
	case 'h':
	    show_usage();
	    exit(0);
	case 'I':
	    hs_readintarg(argv[optind], optarg, &hs_inbuflen);
	    break;
	case 'O':
	    hs_readintarg(argv[optind], optarg, &hs_outbuflen);
	    break;
	case 'V':
                printf("%s (%s)\n", PROGRAM, hs_libhsync_version);
                exit(0);
        case 'L':
                puts(hs_licence_string);
                exit(0);
	case 'v':
	    if (!hs_supports_trace()) {
		hs_error("library does not support trace");
	    }
	    hs_trace_set_level(LOG_DEBUG);
	    break;
	}
    }
}


int
main(int argc, char **argv)
{
        process_args(argc, argv);

        argc -= optind;
        argv += optind;
    
        if (argc <= 0) {
                ;
        } else if (strisprefix(argv[0], "signature")) {
                return hs_rdiff_signature(argc, argv);
        } else if (strisprefix(argv[0], "delta")) {
                return hs_rdiff_delta(argc, argv);
        } else if (strisprefix(argv[0], "patch")) {
                return hs_rdiff_patch(argc, argv);
        } else if (strisprefix(argv[0], "sum")) {
                return hs_rdiff_sum(argc, argv);
        }
    
        hs_error("You must specify one of the signature, delta, "
                 "patch or sum operations"
                 ", or try --help.");
        return 1;
}



/* This should probably be a parameter to all functions instead, but
 * I'm not sure I want to keep it. */
extern int output_mode;

enum hs_result hs_rdiff_sum(int argc, char **argv)
{
#if 0
    unsigned char          result[HS_MD4_LENGTH];
    char            result_str[HS_MD4_LENGTH * 3];
    FILE *in_file;

    if (argc != 2) {
	hs_error("Sum operation needs one filename");
	return 1;
    }
    
    in_file = hs_file_open(argv[1], O_RDONLY);
    
    hs_mdfour_file(in_file, result);
    hs_hexify(result_str, result, HS_MD4_LENGTH);

    printf("%s\n", result_str);

    return 0;
#else
    hs_fatal("not implemented at the moment, back soon");
#endif
}



hs_result
hs_rdiff_delta(int argc, char **argv)
{
#if 0
        FILE *new_file, *sig_file, *delta_file;
        hs_job_t *job;
        hs_stream_t             *stream;
        char *inbuf, *outbuf;
        hs_result result;
    
        if (argc != 4) {
                hs_error("Delta operation needs three filenames: "
                          "SIGNATURE NEWFILE DELTA");
                return 1;
        }

        sig_file = hs_file_open(argv[1], O_RDONLY);
        new_file = hs_file_open(argv[2], O_RDONLY);
        delta_file = hs_file_open(argv[3], output_mode);

        job = hs_delta_begin(stream);

        /* TODO: read signatures; then close signature file. */
        return result;
#else
    hs_fatal("not implemented at the moment, back soon");
#endif
}



enum hs_result
hs_rdiff_patch(int argc, char *argv[])
{
#if 0
        FILE *old_file, *delta_file, *new_file;
        char *outbuf;
        HSFILE *patch;
        enum hs_result result;
        size_t len;

        if (argc != 4) {
                hs_error("Patch operation needs three filenames: "
                          "OLDFILE DELTA NEWFILE");
                return 1;
        }

        old_file = hs_file_open(argv[1], O_RDONLY);
        delta_file = hs_file_open(argv[2], O_RDONLY);
        new_file = hs_file_open(argv[3], output_mode);

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
        hs_error("patch failed: %s", hs_strerror(result));
    
        return 1;
#else
    hs_fatal("not implemented at the moment, back soon");
#endif
}




hs_result hs_rdiff_signature(int argc, char *argv[])
{
        FILE *old_file, *sig_file;
        hs_result result;
    
        if (argc != 3) {
                hs_error("Signature operation needs two filenames");
                return 1;
        }
    
        old_file = hs_file_open(argv[1], O_RDONLY);
        sig_file = hs_file_open(argv[2], output_mode);

        result = hs_whole_signature(old_file, sig_file);
        
        if (result != HS_OK)
                hs_error("signature failed: %s", hs_strerror(result));
    
        return result;
}
