/*=                                     -*- c-file-style: "bsd" -*-
 * rproxy -- dynamic caching and delta update in HTTP
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

#include "includes.h"

#include "mapptr.h"

#include <unistd.h>
#include <stdio.h>
#include <sys/file.h>
#include <string.h>


int
main(int argc, char *argv[])
{
    hs_mdfour_t     sum;
    hs_map_t       *map;
    byte_t          result[MD4_LENGTH];
    char            result_str[MD4_LENGTH * 3];
    byte_t const   *buf;
    char           *tail_ptr;
    off_t           pos;
    size_t          len;
    size_t          max_len = 4096;
    int             c;
    int at_eof;

    while ((c = getopt(argc, argv, "b:")) != -1) {
        switch (c) {
        case '?':
        case ':':
            return 1;
        case 'b':
            max_len = strtol(optarg, &tail_ptr, 10);
            if (*tail_ptr || max_len < 1) {
                fprintf(stderr, "-b must have a positive integer argument\n");
                return 1;
            }
            break;
        }
    }

    hs_mdfour_begin(&sum);

    map = hs_map_file(STDIN_FILENO);
    assert(map);

    pos = 0;
    while (1) {
        len = max_len;
        buf = hs_map_ptr(map, pos, &len, &at_eof);
        if (!buf) {
            perror("couldn't map!");
            return 1;
        } else if (len == 0 && at_eof) {
            break;
        } else {
            /* restrict len to the desired amount, even though
             * it's likely we got more */
            if (max_len < len)
                len = max_len;
            hs_mdfour_update(&sum, buf, len);
            pos += len;
        }
    }

    /* XXX: Something is wrong here: when I type in interactively, I
     * have to press C-d twice to make the program exit. */

    hs_mdfour_result(&sum, result);
    hs_hexify_buf(result_str, result, MD4_LENGTH);

    write(STDOUT_FILENO, result_str, strlen(result_str));
    write(STDOUT_FILENO, "\n", 1);

    return 0;
}
