/*=                                     -*- c-file-style: "bsd" -*-
 *
 * libhsync -- library for network deltas
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool <mbp@samba.org>
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


#include "config.h"

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
#include "nozzle.h"
#include "streamcpy.h"



int main(int UNUSED(argc), char UNUSED(** argv))
{
    hs_nozzle_t *out_nozzle, *in_nozzle;
    hs_stream_t stream;

    hs_stream_init(&stream);

    out_nozzle = _hs_nozzle_new(stdout, &stream, 2, "w");
    in_nozzle = _hs_nozzle_new(stdin, &stream, 3, "r");

    _hs_blow_literal(&stream, "hello ", 6);
    _hs_nozzle_drain(out_nozzle, &stream);

    _hs_stream_copy_file(&stream, in_nozzle, out_nozzle);

    _hs_blow_literal(&stream, "world\n", 6);
    _hs_nozzle_drain(out_nozzle, &stream);
    
    _hs_nozzle_delete(out_nozzle);
    _hs_nozzle_delete(in_nozzle);
    
    return 0;
}
