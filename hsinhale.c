/*=				       	-*- c-file-style: "bsd" -*-
 * rproxy -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool <mbp@humbug.org.au>
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


#include <unistd.h>
#include <stdio.h>
#include <sys/file.h>
#include <string.h>

#include "includes.h"
#include "command.h"
#include "inhale.h"

static void
print_cmd(int kind, uint32_t param1, uint32_t param2)
{
    char const     *kind_str;

    switch (kind) {
    case op_kind_eof:
	printf("EOF\n");
	return;
    case op_kind_copy:
	printf("COPY %d %d\n", param1, param2);
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

    printf("%s %d\n", kind_str, param1);
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
    hs_op_kind_t    kind;
    int             param2, param1;
    hs_map_t       *map;
    off_t           pos;
    hs_result_t     result;
    int             rc;

    if ((rc = parse_args(argc, argv)) != 0)
	return rc;

    setvbuf(stdout, NULL, _IONBF, 0);

    map = hs_map_file(STDIN_FILENO);
    pos = 0;
    do {
	result = _hs_inhale_command_map(map, &pos, &kind, &param1, &param2);

        if (result == HS_FAILED)
	    return 1;
        else if (result == HS_AGAIN)
            continue;

	print_cmd(kind, param1, param2);
    } while (kind != op_kind_eof);

    return 0;
}
