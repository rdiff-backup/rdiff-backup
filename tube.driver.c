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


#include <config.h>

#include <assert.h>

#ifdef HAVE_STDINT_H
#include <stdint.h>
#endif

#include <sys/types.h>
#include <limits.h>
#include <inttypes.h>
#include <stdlib.h>
#include <stdio.h>
#include <unistd.h>

#include "hsync.h"
#include "private.h"
#include "stream.h"
#include "tube.h"
#include "file.h"


static void drain(hs_nozzle_t *out_nozzle, hs_stream_t *stream)
{
    do {
        _hs_tube_drain(stream);
        hs_nozzle_out(out_nozzle);
    } while (!_hs_tube_empty(stream));
}


int main(int UNUSED(argc), char UNUSED(** argv))
{
    hs_nozzle_t *out_nozzle, *in_nozzle;
    hs_stream_t stream;

    hs_stream_init(&stream);

    out_nozzle = hs_nozzle_new(STDOUT_FILENO, &stream, 2, 'w');
    in_nozzle = hs_nozzle_new(STDIN_FILENO, &stream, 3, 'r');

    _hs_tube_blow(&stream, "hello ", 6);
    drain(out_nozzle, &stream);

    _hs_stream_copy_file(&stream, in_nozzle, out_nozzle);

    _hs_tube_blow(&stream, "world\n", 6);
    drain(out_nozzle, &stream);
    
    hs_nozzle_delete(out_nozzle);
    hs_nozzle_delete(in_nozzle);
    
    return 0;
}
