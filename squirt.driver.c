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


/*
 * Test driver for network-endian output through a tube.
 */


#include "config.h"

#include <assert.h>

#ifdef HAVE_STDINT_H
#include <stdint.h>
#endif

#include <inttypes.h>
#include <stdlib.h>

#include "hsync.h"


int main(void)
{
    hs_nozzle_t *in_iobuf, *out_iobuf;
    hs_stream_t stream;
    int input_done = 0, result;

    hs_stream_init(&stream);

    out_iobuf = hs_nozzle_new(STDOUT_FILENO, &stream, hs_outbuflen, 'w');

    _hs_trace("generate checksum from fd%d to fd%d", in_fd, out_fd);
    
    do {
	int i;

	for (i = 0; i < 100; i++) {
	    _hs_squirt_n32(stream, i);
	}

	_hs_tube_catchup();
	_hs_nozzle_out(out_iobuf);
    } while (!_hsinput_done || (result != HS_COMPLETE));
    
    hs_nozzle_delete(out_iobuf);
}


