/*=                    -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * libhsync -- the library for network deltas
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


#define PROGRAM "rdiff"


/* Overwrite existing files. */
int force = 0;


const struct poptOption opts[] = {
        { "verbose", 'v', POPT_ARG_NONE, 0, 'v',
          "trace internal processing", NULL },
        { "version", 'V', POPT_ARG_NONE, 0, 'V',
          "show program version", NULL },
        { "licence",  0 , POPT_ARG_NONE, 0, 'L',
          "show copying conditions", NULL },
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
    FILE            *patch_file, *sig_file, *new_file;
    hs_result       result;
    const char      *patch_name, *sig_name, *new_name;
    hs_sumset_t     *sumset;

    cont = poptGetContext(PROGRAM, argc, (const char **) argv, opts, 0);
    poptSetOtherOptionHelp(cont, "SIGNATURE NEW PATCH");

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

    sig_name = poptGetArg(cont);
    new_name = poptGetArg(cont);
    patch_name = poptGetArg(cont);

    if (!new_name || !sig_name || !patch_name) {
        usage(cont, 1, PROGRAM,
              "must specify new, signature and patch filenames");
    }

    poptFreeContext(cont);                     

    sig_file = hs_file_open(sig_name, O_RDONLY);

    result = hs_file_readsums(sig_file, &sumset);
        
    if (result != HS_OK)
        hs_error("readsums failed: %s", hs_strerror(result));
    
    return result;
}
