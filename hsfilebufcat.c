/*=                                     -*- c-file-style: "bsd" -*-
 * rproxy -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool <mbp@humbug.org.au>
 * 
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public License
 * as published by the Free Software Foundation; either version 2.1 of
 * the License, or (at your option) any later version.
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


/* hsfilebufcat: write stdin to stdout, using an hs_filebuf_t to do * the
 * input.  */


int
main(int argc, char *argv[])
{
    hs_filebuf_t           *infb;
    int                     buf_len = 1000;
    byte_t                 *buf;
    char                   *tail_ptr;
    int                     len;
    int                     c;
    int                     filebuf_loop = 0;

    while ((c = getopt(argc, argv, "lb:")) != -1) {
        switch (c) {
        case '?':
        case ':':
            return 1;
        case 'l':
            filebuf_loop = 1;
            break;
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

    infb = hs_filebuf_from_fd(STDIN_FILENO);
    assert(infb);

    while (1) {
        if (filebuf_loop) {
            len = _hs_read_loop(hs_filebuf_read, infb, buf, buf_len);
        } else {
            len = hs_filebuf_read(infb, buf, buf_len);
        }

        if (len < 0) {
            perror("error in read");
            return 1;
        } else if (len == 0) {
            break;
        } else {
            write(STDOUT_FILENO, buf, len);
        }
    }

    return 0;
}
