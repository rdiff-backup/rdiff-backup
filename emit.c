/*=				       	-*- c-file-style: "linux" -*-
 *
 * libhsync -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool <mbp@linuxcare.com.au>
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
                               * [almost sobbing] They don't sleep
                               * anymore on the beach.  They don't
                               * sleep on the beach anymore.
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
#include "command.h"
#include "protocol.h"
#include "trace.h"
#include "emit.h"
#include "prototab.h"
#include "netint.h"


int
_hs_fits_in_n8(size_t val)
{
    return val <= UINT8_MAX;
}


int
_hs_fits_in_n16(size_t val)
{
    return val <= UINT16_MAX;
}


int
_hs_fits_in_n32(size_t val)
{
    return val <= UINT32_MAX;
}


int
_hs_int_len(off_t val)
{
        if (_hs_fits_in_n8(val))
                return 1;
        else if (_hs_fits_in_n16(val))
                return 2;
        else if (_hs_fits_in_n32(val))
                return 4;
        else {
                _hs_fatal("can't handle integer this long yet");
        }
}


/*
 * Write the magic for the start of a delta.
 */
void
_hs_emit_delta_header(hs_stream_t *stream)
{
    _hs_trace("emit DELTA");
    _hs_squirt_n32(stream, HS_DELTA_MAGIC);
}



/* Write a LITERAL command. */
void
_hs_emit_literal_cmd(hs_stream_t *stream, int len)
{
    _hs_trace("emit LITERAL(%d)", len);
    _hs_squirt_n8(stream, HS_OP_LITERAL_N32);
    _hs_squirt_n32(stream, len);
}
