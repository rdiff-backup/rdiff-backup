/*=                                     -*- c-file-style: "bsd" -*-
 * libhsync -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 1999, 2000 by Martin Pool <mbp@humbug.org.au>
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

#include <unistd.h>
#include <stdio.h>
#include <sys/file.h>
#include <string.h>
#include <stdlib.h>
#include <assert.h>
#include <errno.h>

#include <hsync.h>

static void
usage(void)
{
    fprintf(stderr, "usage: hsmdfour [-b LEN]\n");
}

int
main(int argc, char *argv[])
{
    byte_t          result[HS_MD4_LENGTH];
    char            result_str[HS_MD4_LENGTH * 3];
    char           *tail_ptr;
    size_t          inbuflen = 4096;
    int             c;

    while ((c = getopt(argc, argv, "b:")) != -1) {
        switch (c) {
        case '?':
        case ':':
            return 1;
        case 'b':
            inbuflen = strtol(optarg, &tail_ptr, 10);
            if (*tail_ptr || inbuflen < 1) {
                fprintf(stderr, "-b must have a positive integer argument\n");
                return 1;
            }
            break;
        }
    }
    if (argv[optind]) {
        usage();
        return 1;
    }

    hs_mdfour_file(STDIN_FILENO, result, inbuflen);
    hs_hexify(result_str, result, HS_MD4_LENGTH);

    write(STDOUT_FILENO, result_str, strlen(result_str));
    write(STDOUT_FILENO, "\n", 1);

    return 0;
}
