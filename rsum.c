/*=                                     -*- c-file-style: "linux" -*-
 *
 * libhsync -- the library for network deltas
 * $Id$
 * 
 * Copyright (C) 2001 by Martin Pool <mbp@linuxcare.com.au>
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
 * rsum.c -- Command line tool to generate rsync signatures for a file.
 */

#include <config.h>

#include <stdlib.h>
#include <stdio.h>
#include <getopt.h>
#include <syslog.h>
#include <fcntl.h>
#include <popt.h>

#include "hsync.h"
#include "hsyncfile.h"
#include "fileutil.h"
#include "util.h"
#include "trace.h"


#define PROGRAM "rsum"


/* Overwrite existing files. */
int force = 0;
size_t block_len, sum_len;


const struct poptOption opts[] = {
        POPT_AUTOHELP
        { "version", 'V', POPT_ARG_NONE, 0, 'V', "show program version" },
        { NULL, '\0', 0, 0 }
};



static void show_usage(void)
{
    printf("Usage: %s [OPTIONS] OLDFILE SIGNATURE\n"
           "\n"
           "Compute rsync file signature.\n"
           "\n"
           "  -v, --verbose             trace internal processing\n"
           "  -I, --input-buffer=BYTES  input buffer size\n"
           "  -O, --output-buffer=BYTES output buffer size\n"
           "      --help                display this help and exit\n"
           "      --version             output version information and exit\n"
           "      --licence             show summary copying terms and exit\n"
           ,
           PROGRAM);
}


static void process_args(int argc, char **argv)
{
        int             c, longind;

        while ((c = getopt_long(argc, argv, "vfI:O:", longopts, &longind)) != -1) {
                switch (c) {
                case '?':
                case ':':
                        exit(1);
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
                case 'b':
                        
                case 'v':
                        if (!hs_supports_trace()) {
                                hs_error("library does not support trace");
                        }
                        hs_trace_set_level(LOG_DEBUG);
                        break;
                }
        }
}


int main(int argc, char *argv[])
{
        FILE *old_file, *sig_file;
        hs_result result;

        process_args(argc, argv);

        argc -= optind;
        argv += optind;

        if (argc != 3) {
                hs_error("Signature operation needs two filenames");
                return 1;
        }
    
        old_file = hs_file_open(argv[1], O_RDONLY);
        sig_file = hs_file_open(argv[2], O_WRONLY|O_CREAT|O_TRUNC);

        result = hs_whole_signature(old_file, sig_file);
        
        if (result != HS_OK)
                hs_error("signature failed: %s", hs_strerror(result));
    
        return result;
}
