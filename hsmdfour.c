/*				       	-*- c-file-style: "bsd" -*-
 * rproxy -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 1999, 2000 by Martin Pool
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


int
main(int argc, char *argv[])
{
    hs_mdfour_t     sum;
    hs_filebuf_t   *infb;
    byte_t          result[MD4_LENGTH];
    char            result_str[MD4_LENGTH * 3];
    int             buf_len = 1000;
    byte_t         *buf;
    char           *tail_ptr;
    int             len;
    int             c;

    while ((c = getopt(argc, argv, "b:")) != -1) {
	switch (c) {
	case '?':
	case ':':
	    return 1;
	case 'b':
	    buf_len = strtol(optarg, &tail_ptr, 10);
	    if (*tail_ptr || buf_len < 1) {
		fprintf(stderr, "-b must have an integer argument\n");
		return 1;
	    }
	    break;
	}
    }

    buf = malloc(buf_len);
    assert(buf);
    hs_mdfour_begin(&sum);

    infb = hs_filebuf_from_fd(STDIN_FILENO);
    assert(infb);

    while (1) {
	len = hs_filebuf_read(infb, buf, buf_len);
	if (len < 0) {
	    perror("error in read");
	    return 1;
	} else if (len == 0) {
	    break;
	} else {
	    hs_mdfour_update(&sum, buf, len);
	}
    }

    hs_mdfour_result(&sum, result);
    hs_hexify_buf(result_str, result, MD4_LENGTH);

    write(STDOUT_FILENO, result_str, strlen(result_str));
    write(STDOUT_FILENO, "\n", 1);

    return 0;
}
