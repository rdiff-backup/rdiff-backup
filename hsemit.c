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
    int             ret, off, len;
    char            cmd[20];
    hs_filebuf_t   *outfb;
    hs_stats_t      stats;

    if ((ret = parse_args(argc, argv)) != 0)
	return ret;

    outfb = hs_filebuf_from_fd(STDOUT_FILENO);

    while (1) {
	ret = scanf("%20s", cmd);
	if (ret == EOF)
	    return 0;

	if (!strcmp(cmd, "COPY")) {
	    if (scanf("%d %d", &off, &len) != 2)
		return 1;
	    ret = _hs_emit_copy(hs_filebuf_write, outfb, off, len, &stats);
	    if (ret < 0)
		return 1;
	} else if (!strcmp(cmd, "EOF")) {
	    ret = _hs_emit_eof(hs_filebuf_write, outfb, &stats);
	    if (ret < 0)
		return 1;
	} else if (!strcmp(cmd, "LITERAL")) {
	    if (scanf("%d", &len) != 1)
		return 1;

	    ret = _hs_emit_literal_cmd(hs_filebuf_write, outfb, len);
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
	} else {
	    fprintf(stderr, "can't understand command `%s'\n", cmd);
	    return 1;
	}
    }
}
