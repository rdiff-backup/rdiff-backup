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
#include <assert.h>


static char const *usage =
"Usage: genmaptest SERIES NUMTESTS CMDS EXPECT INPUT\n";


static int
open_all(char const *cmds_name,
	 char const *expect_name,
	 char const *input_name,
	 char **buf, size_t *size,
	 FILE **expect, FILE **cmds)
{
    struct stat		 stat_buf;
    FILE		*in;

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


static void
emit(char const *buf, size_t len, off_t off, size_t size,
     FILE *expect, FILE *cmds)
{
    assert(off >= 0);
    assert((size_t) off < len);
    
    fprintf(cmds, "%ld,%ld ", (long) off, (long) size);

    /* But we truncate at the end. */
    if (off + size > len) {
	size = len - off;
    }
    
    fwrite(buf+off, 1, size, expect);
}


/* Generate random maps within the file. */
static void
gen_map(int ntests, char const *buf, size_t size,
	FILE *expect, FILE *cmds)
{
    int i;
    off_t		off;
    size_t		len, remain;

    for (i = 0; i < ntests; i++) {
	off = rand() % size;
	remain = size - off;
	len = 1 + (rand() % remain);
	emit(buf, size, off, len, expect, cmds);
    }				     
}


/* Generate random maps possibly overlapping the end of the file. */
static void
gen_mapover(int ntests, char const *buf, size_t size,
	    FILE *expect, FILE *cmds)
{
    int i;
    off_t		off;
    size_t		len, remain;

    for (i = 0; i < ntests; i++) {
	off = rand() % size;
	remain = size - off;
	len = rand() % size + 1;
	emit(buf, size, off, len, expect, cmds);
    }
}


static void
gen_forward(int ntests, char const *buf, size_t size,
	    FILE *expect, FILE *cmds)
{
    int i;
    off_t		off;
    size_t		len;

    i = 0; off = 0;
    while ((size_t) off < size  &&  i < ntests) {
	len = rand() % 8192 + 1;
	emit(buf, size, off, len, expect, cmds);

	off += rand() % len;
	i++;
    }
}


int
main(int argc, char **argv) {
    char const		*series;
    FILE		*expect, *cmds;
    char		*buf;
    size_t		size;
    int			numtests;
    
    if (argc != 6) {
	fputs(usage, stderr);
	return 1;
    }

    if (open_all(argv[3], argv[4],argv[5], &buf, &size, &expect, &cmds))
	return 1;
    
    series = argv[1];
    numtests = atoi(argv[2]);

    if (!strcmp(series, "map")) {
	gen_map(numtests, buf, size, expect, cmds);
    } else if (!strcmp(series, "mapover")) {
	gen_mapover(numtests, buf, size, expect, cmds);
    } else if (!strcmp(series, "forward")) {
	gen_forward(numtests, buf, size, expect, cmds);
    } else {
	fprintf(stderr, "unknown series %s\n", series);
	return 1;
    }

    return 0;
}
