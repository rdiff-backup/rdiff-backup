/*				       	-*- c-file-style: "bsd" -*-
 * rproxy -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool <mbp@humbug.org.au>
 * 
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU Lesser General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
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


static void
print_cmd(int kind, uint32_t len, uint32_t off)
{
    char const     *kind_str;

    switch (kind) {
    case op_kind_eof:
	printf("EOF\n");
	return;
    case op_kind_copy:
	printf("COPY %d %d\n", off, len);
	return;
    }

    switch (kind) {
    case op_kind_signature:
	kind_str = "SIGNATURE";
	break;
    case op_kind_literal:
	kind_str = "LITERAL";
	break;
    case op_kind_checksum:
	kind_str = "CHECKSUM";
	break;
    default:
	fprintf(stderr, "bugger!  unexpected opcode kind\n");
	abort();
    }

    printf("%s %d\n", kind_str, len);
}


static int
parse_args(int argc, char **argv)
{
    int             c;

    

    while ((c = getopt(argc, argv, "D")) != -1) {
	switch (c) {
	case '?':
	case ':':
	    return 1;
	case 'D':
	    hs_trace_set_level(LOG_DEBUG);
	    break;
	}
    }

    return 0;
}



int
main(int argc, char **argv)
{
    int             ret, kind;
    uint32_t        off, len;
    hs_filebuf_t   *infb;

    if ((ret = parse_args(argc, argv)) != 0)
	return ret;

    setvbuf(stdout, NULL, _IONBF, 0);

    infb = hs_filebuf_from_fd(STDIN_FILENO);

    do {
	ret = _hs_inhale_command(hs_filebuf_read, infb, &kind, &len, &off);

	if (ret < 0)
	    return 1;
	else if (ret == 0)
	    return 1;

	print_cmd(kind, len, off);
    } while (kind != op_kind_eof);

    return 0;
}
