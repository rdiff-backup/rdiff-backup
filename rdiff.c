/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * libhsync -- the library for network deltas
 * $Id$
 * 
 * Copyright (C) 1999, 2000, 2001 by Martin Pool <mbp@samba.org>
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
 * rdiff.c -- Command-line network-delta tool.
 */

#include <config.h>

#include <stdlib.h>
#include <stdio.h>
#include <getopt.h>
#include <fcntl.h>
#include <popt.h>

#include "hsync.h"
#include "hsyncfile.h"
#include "fileutil.h"
#include "util.h"
#include "trace.h"
#include "isprefix.h"


#define PROGRAM "rdiff"

static size_t block_len = HS_DEFAULT_BLOCK_LEN;
static size_t strong_len = HS_DEFAULT_STRONG_LEN;


/*
 * This little declaration is dedicated to Stephen Kapp and Reaper
 * Technologies, who by all appearances redistributed a modified but
 * unacknowledged version of GNU Keyring in violation of the licence
 * and all laws of politeness and good taste.
 */

static char const *version_str =
"rdiff (%s)\n"
"Copyright (C) 1997-2001 by Martin Pool, Andrew Tridgell and others.\n"
"http://rproxy.samba.org/\n"
"\n"
"libhsync comes with NO WARRANTY, to the extent permitted by law.\n"
"You may redistribute copies of libhsync under the terms of the GNU\n"
"Lesser General Public License.  For more information about these\n"
"matters, see the files named COPYING.\n";


const struct poptOption opts[] = {
    { "verbose",     'v', POPT_ARG_NONE, 0,             'v' },
    { "version",     'V', POPT_ARG_NONE, 0,             'V' },
    { "input-size",  'I', POPT_ARG_INT,  &hs_inbuflen },
    { "output-size", 'O', POPT_ARG_INT,  &hs_outbuflen },
    { "help",        '?', POPT_ARG_NONE, 0,             'h' },
    { "block-size",  'b', POPT_ARG_INT,  &block_len },
    { "sum-size",    's', POPT_ARG_INT,  &strong_len },

    { 0 }
};


static void rdiff_usage(const char *error)
{
    fprintf(stderr, "%s: %s\n"
            "Try `%s --help' for more information.\n",
            PROGRAM, error, PROGRAM);
}


static void bad_option(poptContext opcon, int error)
{
    fprintf(stderr, "%s: %s: %s\n",
            PROGRAM, poptStrerror(error), poptBadOption(opcon, 0));
    exit(HS_SYNTAX_ERROR);
}


static void help(void) {
    printf("Usage: rdiff [OPTIONS] signature [BASIS [SIGNATURE]]\n"
           "             [OPTIONS] delta SIGNATURE [NEWFILE [DELTA]]\n"
           "             [OPTIONS] patch BASIS [DELTA [NEWFILE]]\n"
           "\n"
           "Options:\n"
           "  -v, --verbose             trace internal processing\n"
           "  -b, --block-size=BYTES    signature block size\n"
           "  -s, --sum-size=BYTES      set signature strength\n"
           "  -I, --input-size=BYTES    input buffer size\n"
           "  -O, --output-size=BYTES   output buffer size\n"
           "  -V, --version             show program version\n"
           "  -?, --help                Show this help message\n"
           );
}


static void rdiff_options(poptContext opcon)
{
    int c;
    
    while ((c = poptGetNextOpt(opcon)) != -1) {
        switch (c) {
        case 'h':
            help();
            exit(HS_DONE);
        case 'V':
            printf(version_str, hs_libhsync_version);
            exit(HS_DONE);
        case 'v':
            if (!hs_supports_trace()) {
                hs_error("library does not support trace");
            }
            hs_trace_set_level(HS_LOG_DEBUG);
            break;
        default:
            bad_option(opcon, c);
        }
    }
}


/**
 * Generate signature from remaining command line arguments.
 */
static hs_result rdiff_sig(poptContext opcon)
{
    FILE            *basis_file, *sig_file;
    const char      *basis_name, *sig_name;
    
    basis_name = poptGetArg(opcon);
    sig_name = poptGetArg(opcon);

    basis_file = hs_file_open(basis_name, "rb");
    sig_file = hs_file_open(sig_name, "wb");

    return hs_sig_file(basis_file, sig_file, block_len, strong_len);
}


static hs_result rdiff_delta(poptContext opcon)
{
    FILE            *sig_file, *new_file, *delta_file;
    char const      *sig_name;
    hs_result       result;
    hs_sumset_t     *sumset;

    if (!(sig_name = poptGetArg(opcon))) {
        rdiff_usage("delta: must specify the signature filename");
        return HS_SYNTAX_ERROR;
    }

    sig_file = hs_file_open(sig_name, "rb");
    new_file = hs_file_open(poptGetArg(opcon), "rb");
    delta_file = hs_file_open(poptGetArg(opcon), "wb");

    result = hs_loadsig_file(sig_file, &sumset);
    if (result != HS_DONE)
        return result;

    result = hs_delta_file(sumset, new_file, delta_file);

    return result;
}


static hs_result rdiff_action(poptContext opcon)
{
    const char      *action;

    action = poptGetArg(opcon);
    if (!action) 
        ;
    else if (isprefix(action, "signature")) 
        return rdiff_sig(opcon);
    else if (isprefix(action, "delta")) 
        return rdiff_delta(opcon);
    
    rdiff_usage("You must specify an action: `signature', `delta', or `patch'.");
    return HS_SYNTAX_ERROR;
}


int main(const int argc, const char *argv[])
{
    poptContext     opcon;
    hs_result       result;

    opcon = poptGetContext(PROGRAM, argc, argv, opts, 0);
    rdiff_options(opcon);
    result = rdiff_action(opcon);
    
    return result;
}
