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

#include "hsync.h"
#include "nozzle.h"
#include "stream.h"
#include "streamcpy.h"


/*
 * Copy until EOF.  This is only used for testing.
 */
void _hs_stream_copy_file(hs_stream_t *stream, hs_nozzle_t *in_iobuf,
			  hs_nozzle_t *out_iobuf)
{
    int seen_eof = 0;
    
    do {
        if (!seen_eof)
            seen_eof = !_hs_nozzle_in(in_iobuf);
        _hs_stream_copy(stream, INT_MAX);
        _hs_nozzle_out(out_iobuf);
    } while (!seen_eof || !_hs_stream_is_empty(stream));
}
