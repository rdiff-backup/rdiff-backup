/*=                                     -*- c-file-style: "bsd" -*-
 *
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


                                        /*
                                         | `It is easier to fight for our
                                         | principles than to live up to
                                         | them' -- Alfred Adler
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


/*
 * SIZE is the total length of the file; all of it is copied into the
 * newly allocated BUF.
 */
static int
open_all(char const *cmds_name,
         char const *expect_name,
         char const *input_name,
         char **buf, size_t *size,
         FILE **expect, FILE **cmds)
{
    struct stat          stat_buf;
    FILE                *in;

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
emit(char const *buf, size_t size, off_t off, size_t len,
     FILE *expect, FILE *cmds)
{
    assert(off >= 0);

    fprintf(cmds, "%ld,%ld ", (long) off, (long) len);

    /* if this starts after the end, do nothing */
    if (off < size) {
        /* if this runs past the end, truncate */
        if (off + len > size) {
            len = size - off;
        }

        fwrite(buf+off, 1, len, expect);
    }
}


/* Generate random maps within the file. */
static void
gen_map(int ntests, char const *buf, size_t size,
        FILE *expect, FILE *cmds)
{
    int i;
    off_t               off;
    size_t              len, remain;

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
    off_t               off;
    size_t              len, remain;

    for (i = 0; i < ntests; i++) {
        off = rand() % (2 * size);
        remain = size - off;
        len = rand() % (2 * size) + 1;
        emit(buf, size, off, len, expect, cmds);
    }
}


static void
gen_forward(int ntests, char const *buf, size_t size,
            FILE *expect, FILE *cmds)
{
    int i;
    off_t               off;
    size_t              len;

    i = 0; off = 0;
    while ((size_t) off < size  &&  i < ntests) {
        len = rand() % 8192 + 1;
        emit(buf, size, off, len, expect, cmds);

        off += rand() % len;
        i++;
    }
}


/*
 * Read the first NTESTS bytes one at a time, then the rest in one big
 * chunk.
 */
static void
gen_ones(int ntests, char const *buf, size_t size,
         FILE *expect, FILE *cmds)
{
    int                 i;

    for (i = 0; (size_t) i < size  &&  i < ntests; i++) {
        emit(buf, size, i, 1, expect, cmds);
    }

    if ((size_t) i < size)
        emit(buf, size, i, size - i, expect, cmds);
}


/*
 * Generate instructions walking forward through the file in small
 * steps, similarly to nad encoding.
 */
static void
gen_stepping(int ntests, char const *buf, size_t size,
             FILE *expect, FILE *cmds)
{
    int                 i;
    size_t              c;

    i = 0;
    while (ntests--) {
        c = rand() % 64 + 1;
        emit(buf, size, i, c, expect, cmds);
        i += rand() % c;
    }

    /* finally read any remaining data */
    emit(buf, size, i, size-i, expect, cmds);
}


static const struct {
    char const *name;
    void (*fn)(int ntests, char const *buf, size_t size,
               FILE *expect, FILE *cmds);
} all_tests[] = {
    { "map", gen_map },
    { "mapover", gen_mapover },
    { "forward", gen_forward },
    { "ones", gen_ones },
    { "stepping", gen_stepping },
    { NULL, NULL }
};


int
main(int argc, char **argv) {
    char const          *series;
    FILE                *expect, *cmds;
    char                *buf;
    size_t              size;
    int                 numtests;
    int                 i;

    if (argc != 6) {
        fputs(usage, stderr);
        return 1;
    }

    if (open_all(argv[3], argv[4],argv[5], &buf, &size, &expect, &cmds))
        return 1;

    series = argv[1];
    numtests = atoi(argv[2]);

    for (i = 0; all_tests[i].name; i++) {
        if (!strcmp(series, all_tests[i].name)) {
            all_tests[i].fn(numtests, buf, size, expect, cmds);
            return 0;
        }
    }
        
    fprintf(stderr, "unknown series %s\n", series);
    return 1;
}
