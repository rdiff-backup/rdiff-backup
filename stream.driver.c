/*=                                     -*- c-file-style: "bsd" -*-
 * libhsync -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool <mbp@humbug.org.au>
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


/*
 * Test driver for libhsync stream functions.
 */

#include <stdlib.h>
#include <getopt.h>
#include <stdio.h>
#include <stdint.h>
#include <unistd.h>
#include <limits.h>

#include "includes.h"
#include "private.h"
#include "util.h"
#include "stream.h"
#include "file.h"


static void do_copy(int in_fd, int out_fd, int inbuflen, int outbuflen)
{
    hs_nozzle_t *in_iobuf, *out_iobuf;
    hs_stream_t stream;

    hs_stream_init(&stream);

    in_iobuf = hs_nozzle_new(in_fd, &stream, inbuflen, 'r');
    out_iobuf = hs_nozzle_new(out_fd, &stream, outbuflen, 'w');

    _hs_stream_copy_file(&stream, in_iobuf, out_iobuf);

    hs_nozzle_delete(in_iobuf);
    hs_nozzle_delete(out_iobuf);
}



int main(int argc, char **argv)
{
    int inbuflen, outbuflen;
    
    if (argc != 3) {
        fprintf(stderr, "usage: dstream INBUF OUTBUF\n");
        return 1;
    }

    inbuflen = atoi(argv[1]);
    outbuflen = atoi(argv[2]);
    
    do_copy(STDIN_FILENO, STDOUT_FILENO, inbuflen, outbuflen);
    
    return 0;
}
