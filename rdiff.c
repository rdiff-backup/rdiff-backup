/*=				       	-*- c-file-style: "bsd" -*-
 *
 * rdiff -- generate and apply rsync signatures and deltas
 * $Id$
 * 
 * Copyright (C) 1999, 2000 by Martin Pool <mbp@samba.org>
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
			       *              -- Harold Bloom               */

#include "config.h"

#include <assert.h>

#include <sys/types.h>
#include <limits.h>
#include <inttypes.h>
#include <stdlib.h>

#include <unistd.h>
#include <stdio.h>
#include <sys/file.h>
#include <string.h>
#include <syslog.h>

#include <getopt.h>

#include "hsync.h"
#include "trace.h"
#include "isprefix.h"
#include "fileutil.h"
#include "util.h"


int block_len = 2048;

/* Overwrite existing files. */
int force = 0;
int output_mode = O_WRONLY|O_CREAT|O_TRUNC|O_EXCL;

/*
 * TODO: Refuse to write binary data to terminals unless --forced.
 */

#define PROGRAM "rdiff"


const struct option longopts[] = {
    { "help", no_argument, 0, 'h' },
    { "version", no_argument, 0, 'V' },
    { "verbose", no_argument, 0, 'v' },
    { "force", no_argument, 0, 'f' },
    { "input-buffer", required_argument, 0, 'I' },
    { "output-buffer", required_argument, 0, 'O' },
    { NULL, 0, 0, 0 }
};


static void
show_usage(void)
{
    printf(
	    "Usage: %s [OPTIONS] signature OLDFILE SIGNATURE\n"
	    "   or: %s [OPTIONS] delta SIGNATURE NEWFILE DELTA\n"
	    "   or: %s [OPTIONS] patch OLDFILE DELTA NEWFILE\n"
	    "   or: %s [OPTIONS] sum INPUT\n"
	    "Compute rsync checksums or deltas, or apply a delta.\n"
	    "\n"
	    "  -f, --force               overwrite existing files\n"
	    "  -v, --verbose             trace internal processing\n"
	    "  -I, --input-buffer=BYTES  input buffer size\n"
	    "  -O, --output-buffer=BYTES output buffer size\n"
	    "      --help                display this help and exit\n"
	    "      --version             output version information and exit\n"
	    ,
	    PROGRAM, PROGRAM, PROGRAM, PROGRAM);
}


static void
process_args(int argc, char **argv)
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
	    _hs_readintarg(argv[optind], optarg, &hs_inbuflen);
	    break;
	case 'O':
	    _hs_readintarg(argv[optind], optarg, &hs_outbuflen);
	    break;
	case 'V':
	    hs_show_version(PROGRAM);
	    exit(0);
	case 'v':
	    if (!hs_supports_trace()) {
		_hs_error("library does not support trace");
	    }
	    hs_trace_set_level(LOG_DEBUG);
	    break;
	}
    }
}


static int
do_signature(int argc, char **argv)
{
    FILE *old_file, *sig_file;
    
    if (argc != 3) {
	_hs_error("Signature operation needs two filenames");
	return 1;
    }
    
    old_file = _hs_file_open(argv[1], O_RDONLY);
    sig_file = _hs_file_open(argv[2], output_mode);

    hs_mksum_files(old_file, sig_file, block_len);
    
    return 0;
}


static int
do_delta(int argc, char **argv)
{
    FILE *new_file, *sig_file, *delta_file;
    
    if (argc != 4) {
	_hs_error("Delta operation needs three filenames: "
		  "SIGNATURE NEWFILE DELTA");
	return 1;
    }
    
    sig_file = _hs_file_open(argv[1], O_RDONLY);
    new_file = _hs_file_open(argv[2], O_RDONLY);
    delta_file = _hs_file_open(argv[3], output_mode);

    hs_delta_files(new_file, delta_file);

    fclose(delta_file);
    
    return 0;
}


static int
do_sum(int argc, char **argv)
{
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
}


#if 0
static int
do_patch(int argc, char **argv)
{
    _hs_error("sorry, not implemented!");
    return 1;
}
#endif

int
main(int argc, char **argv)
{
    process_args(argc, argv);

    argc -= optind;
    argv += optind;
    
    if (argc <= 0) {
	;
    } else if (strisprefix(argv[0], "signature")) {
	return do_signature(argc, argv);
    } else if (strisprefix(argv[0], "delta")) {
	return do_delta(argc, argv);
/*      } else if (strisprefix(argv[0], "patch")) { */
/*  	return do_patch(argc, argv); */
    } else if (strisprefix(argv[0], "sum")) {
	return do_sum(argc, argv);
    }
    
    _hs_error("You must specify one of the signature, delta, "
	      "patch or sum operations"
	      ", or try --help.");
    return 1;
}
