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


/* genmaptest -- Make up a test case and expected output for hsmapread.
 */

#include "config.h"

#include <stdlib.h>
#include <stdio.h>
#include <sys/stat.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>


char const *usage =
"Usage: genmaptest SERIES CMDS EXPECT INPUT\n";


int
open_all(char **argv, char **buf, size_t *size,
	 FILE **expect, FILE **cmds)
{
    char const *cmds_name, *expect_name, *input_name;
    struct stat		 stat_buf;
    FILE		*in;

    /* Open all files. */
    cmds_name = argv[2];
    expect_name = argv[3];
    input_name = argv[4];

    if (!(in = fopen(input_name, "rb"))) {
	perror(input_name);
	return 1;
    }

    if (fstat(fileno(in), &stat_buf) < 0) {
	perror(input_name);
	return 1;
    }

    if (!(*expect = fopen(expect_name, "wb"))) {
	perror(expect_name);
	return 1;
    }

    if (!(*cmds = fopen(cmds_name, "wt"))) {
	perror(cmds_name);
	return 1;
    }


    /* Read all input. */
    *size = stat_buf.st_size;
    if (!(*buf = malloc(*size))) {
	perror("malloc"); return 1;
    }
    if (fread(*buf, 1, *size, in) != *size) {
	perror("read"); return 1;
    }

    return 0;
}


int
main(int argc, char **argv) {
    char const		*series;
    FILE		*expect, *cmds;
    char		*buf;
    size_t		size;
    
    if (argc != 5) {
	fputs(usage, stderr);
	return 1;
    }

    if (open_all(argv, &buf, &size, &expect, &cmds))
	return 1;
    
    series = argv[1];

    fwrite(buf, 1, size, expect);

    return 0;
}
