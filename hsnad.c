/*				       	-*- c-file-style: "bsd" -*-
 *
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool
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

static void usage(char const *progname)
{
    fprintf(stderr,
	    "Usage: %s OLDSIG [OPTIONS]\n"
	    "\n"
            "Computes difference/signature of stdin and "
            "writes it to stdout."
            "\n"
            "Options:\n"
            "  -D           show debugging trace if compiled in\n"
            "  -h           show help\n",
	    progname
        );
}


static void process_args(int argc, char **argv)
{
    int			c;
    
    hs_trace_to(NULL);		/* may turn it on later */
    while ((c = getopt(argc, argv, "D")) != -1) {
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
	    hs_trace_to(hs_trace_to_stderr);
	    break;
	}
    }
}


int main(int argc, char **argv)
{
    hs_encode_job_t    *job;
    hs_filebuf_t       *out;
    hs_result_t		result;
    hs_stats_t		stats;
    hs_filebuf_t       *sig_fb;
    hs_sum_set_t       *sum_set = NULL;

    process_args(argc, argv);

    out = hs_filebuf_from_fd(STDOUT_FILENO);
    if (!out) {
	_hs_fatal("couldn't create a filebuf on stdout");
	return 1;
    }

    if (optind < argc) {
	sig_fb = hs_filebuf_open(argv[optind], O_RDONLY);
	sum_set = _hs_read_sum_set(hs_filebuf_read, sig_fb);
    }

    job = hs_encode_begin(STDIN_FILENO, hs_filebuf_write, out,
			  sum_set, &stats,
			  1024);
    do {
	result = hs_encode_iter(job);
    } while (result == HS_AGAIN);

    return result == HS_DONE ? 0 : 2;
}
