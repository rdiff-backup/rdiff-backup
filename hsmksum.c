/*=				       	-*- c-file-style: "bsd" -*-
 * libhsync -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 1999, 2000 by Martin Pool <mbp@humbug.org.au>
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

#include "includes.h"


#include <unistd.h>
#include <stdio.h>
#include <sys/file.h>
#include <string.h>
#include <syslog.h>

#include "trace.h"

static void
usage(char const *progname)
{
    fprintf(stderr,
	    "Usage: %s [OPTIONS]\n"
	    "\n"
	    "Computes a per-block signature of stdin and "
	    "writes it to stdout."
	    "\n"
	    "Options:\n"
	    "  -D           show debugging trace if compiled in\n"
	    "  -h           show help\n", progname);
}


static void
process_args(int argc, char **argv)
{
    int             c;

    while ((c = getopt(argc, argv, "D")) != -1) {
	switch (c) {
	case '?':
	case ':':
            usage(argv[0]);
	    exit(1);
	case 'h':
	    usage(argv[0]);
	    exit(0);
	case 'D':
	    if (!hs_supports_trace()) {
		_hs_error("library does not support trace");
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

    hs_mksum_files(STDIN_FILENO, STDOUT_FILENO, 1024, 16, 16);

    return 0;
}
