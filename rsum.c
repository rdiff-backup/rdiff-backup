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
size_t block_len = HS_DEFAULT_BLOCK_LEN, strong_len = HS_DEFAULT_STRONG_LEN;


const struct poptOption opts[] = {
        { "verbose", 'v', POPT_ARG_NONE, 0, 'v',
          "trace internal processing", NULL },
        { "version", 'V', POPT_ARG_NONE, 0, 'V',
          "show program version", NULL },
        { "licence",  0 , POPT_ARG_NONE, 0, 'L',
          "show copying conditions", NULL },
        { "block-size", 'b', POPT_ARG_INT, &block_len, 0,
          "block size for generated signature", "bytes" },
        { "sum-size", 's', POPT_ARG_INT, &strong_len, 0,
          "strong checksum length", "bytes" },
        { "input-size", 'I', POPT_ARG_INT, &hs_inbuflen, 0,
          "input buffer size", "bytes" },
        { "output-size", 'O', POPT_ARG_INT, &hs_outbuflen, 0,
          "output buffer size", "bytes" },
        POPT_AUTOHELP
        { NULL, '\0', 0, 0, 0, 0, 0 }
};


static void usage(poptContext optCon, int exitcode,
                  const char *error, const char *addl)
{
        poptPrintUsage(optCon, stderr, 0);
        if (error)
                fprintf(stderr, "%s: %s\n", error, addl);
        exit(exitcode);
}


int main(int argc, char *argv[])
{
        int             c;
        poptContext     cont;
        FILE            *old_file, *sig_file;
        hs_result       result;
        const char      *old_name, *sig_name;

        cont = poptGetContext(PROGRAM, argc, (const char **) argv, opts, 0);
        poptSetOtherOptionHelp(cont, "BASIS SIGNATURE");

        while ((c = poptGetNextOpt(cont)) > 0) {
                switch (c) {
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

        old_name = poptGetArg(cont);
        sig_name = poptGetArg(cont);

        if (!old_name || !sig_name) {
                usage(cont, 1, PROGRAM,
                      "must specify basis and signature filenames");
        }

        poptFreeContext(cont);                     

        old_file = hs_file_open(old_name, O_RDONLY);
        sig_file = hs_file_open(sig_name, O_WRONLY|O_CREAT|O_TRUNC);

        result = hs_whole_signature(old_file, sig_file,
                                    block_len, strong_len);
        
        if (result != HS_OK)
                hs_error("signature failed: %s", hs_strerror(result));
    
        return result;
}
