/*=                                     -*- c-file-style: "java" -*-
 *
 * libhsync -- library for network deltas
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool <mbp@samba.org>
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

/* Test driver for libhsync.  This one reads commands from standard
 * input and generates a delta as specified. */


#include "config.h"

#include <assert.h>

#ifdef HAVE_STDINT_H
#include <stdint.h>
#endif

#include <fcntl.h>
#include <sys/types.h>
#include <limits.h>
#include <inttypes.h>
#include <stdlib.h>
#include <stdio.h>
#include <stdarg.h>

#include "hsync.h"
#include "tube.h"
#include "emit.h"
#include "stream.h"
#include "fileutil.h"
#include "nozzle.h"
#include "trace.h"


static int
process_commands(hs_stream_t *stream, hs_nozzle_t *in_nozzle,
		 hs_nozzle_t *out_nozzle)
{
    int             ret, off, len;
    char            cmd[20];



    while (1) {
	_hs_nozzle_siphon(stream, in_nozzle, out_nozzle);
	
	ret = scanf("%20s", cmd);
	if (ret == EOF)
	    return 0;
	
	if (!strcmp(cmd, "DELTA")) {
	    _hs_emit_delta_header(stream);
	} else if (!strcmp(cmd, "LITERAL")) {
	    if (scanf("%d", &len) != 1)
		return 1;

	    _hs_emit_literal_cmd(stream, len);
	    _hs_blow_copy(stream, len);
	} 
#if 0
	else if (!strcmp(cmd, "EOF")) {
	    ret = _hs_emit_eof(hs_filebuf_write, outfb, &stats);
	    if (ret < 0)
		return 1;
	} else if (!strcmp(cmd, "SIGNATURE")) {
	    if (scanf("%d", &len) != 1)
		return 1;

	    ret = _hs_emit_signature_cmd(hs_filebuf_write, outfb, len);
	    if (ret < 0)
		return 1;
	} else if (!strcmp(cmd, "CHECKSUM")) {
	    if (scanf("%d", &len) != 1)
		return 1;

	    ret = _hs_emit_checksum_cmd(hs_filebuf_write, outfb, len);
	    if (ret < 0)
		return 1;
	}
#endif
	    else {
		_hs_fatal("can't understand command `%s'\n", cmd);
		return 1;
	    }
    }
    return 0;
}


int main(int argc, char *argv[])
{
    hs_nozzle_t *out_nozzle, *in_nozzle;
    hs_stream_t stream;
    FILE *in_file, *out_file;

    if (!strcmp(argv[1], "-v")) {
	hs_trace_set_level(LOG_DEBUG);
	
	argc--; argv++;
    }

    hs_stream_init(&stream);

    if (argc != 3) {
	fprintf(stderr, "Usage: emit.driver [-v] LITERALS OUTFILE\n"
		"Generates a binary delta from commands on stdin and\n"
		"literal data.\n");
	return 1;
    }

    in_file = _hs_file_open(argv[1], O_RDONLY);
    out_file = _hs_file_open(argv[2], O_WRONLY|O_EXCL|O_CREAT|O_TRUNC);

    in_nozzle = _hs_nozzle_new(in_file, &stream, hs_inbuflen, "r");
    out_nozzle = _hs_nozzle_new(out_file, &stream, hs_inbuflen, "w");

    return process_commands(&stream, in_nozzle, out_nozzle);
}
