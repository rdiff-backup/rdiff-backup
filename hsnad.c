/*				       	-*- c-file-style: "bsd" -*-
 * rproxy -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 1999, 2000 by Martin Pool
 * Copyright (C) 1999 by Andrew Tridgell
 * 
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#include "includes.h"


#include <unistd.h>
#include <stdio.h>
#include <sys/file.h>
#include <string.h>

int             show_stats = 0;

static void
usage(char const *progname)
{
    fprintf(stderr,
	    "Usage: %s OLDSIG [OPTIONS]\n"
	    "\n"
	    "Computes difference/signature of stdin and "
	    "writes it to stdout."
	    "\n"
	    "Options:\n"
	    "  -D           show debugging trace if compiled in\n"
	    "  -S           show statistics\n"
	    "  -h           show help\n", progname);
}


static void
process_args(int argc, char **argv)
{
    int             c;

    while ((c = getopt(argc, argv, "DS")) != -1) {
	switch (c) {
	case '?':
	case ':':
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
	case 'S':
	    show_stats = 1;
	    break;
	}
    }
}


int
main(int argc, char **argv)
{
    hs_encode_job_t *job;
    hs_filebuf_t   *out;
    hs_result_t     result;
    hs_stats_t      stats;
    hs_filebuf_t   *sig_fb;
    hs_sumset_t    *sums = NULL;

    process_args(argc, argv);

    out = hs_filebuf_from_fd(STDOUT_FILENO);
    if (!out) {
	_hs_fatal("couldn't create a filebuf on stdout");
	return 1;
    }

    if (optind < argc) {
	sig_fb = hs_filebuf_open(argv[optind], O_RDONLY);
	sums = hs_read_sumset(hs_filebuf_read, sig_fb);
    }

    job = hs_encode_begin(STDIN_FILENO, hs_filebuf_write, out,
			  sums, &stats, 1024);
    do {
	result = hs_encode_iter(job);
    } while (result == HS_AGAIN);

    if (sums)
	hs_free_sumset(sums);

    if (show_stats)
	hs_write_stats(&stats, STDIN_FILENO);

    return result == HS_DONE ? 0 : 2;
}
