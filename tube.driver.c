/*=                                     -*- c-file-style:"linux" -*-
 *
 * libhsync -- library for network deltas
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
#include "stream.h"
#include "file.h"
#include "streamfile.h"


static void _drain_tube(hs_stream_t *stream, char *outbuf, int len, FILE *out)
{
        do {
                _hs_tube_catchup(stream);
                _hs_drain_to_file(stream, outbuf, len, out);
        } while (!_hs_tube_is_idle(stream));
}


int main(void)
{
        hs_stream_t stream;
        char inbuf[2], outbuf[2];

        hs_stream_init(&stream);

        _hs_blow_literal(&stream, "hello ", 6);
        _drain_tube(&stream, outbuf, sizeof outbuf, stdout);

        while (!feof(stdin)) {
                _hs_fill_from_file(&stream, inbuf, sizeof inbuf, stdin);
                _hs_stream_copy(&stream, 200);
                _hs_drain_to_file(&stream, outbuf, sizeof outbuf, stdout);
        }
    
        _hs_blow_literal(&stream, "world\n", 6);
        _drain_tube(&stream, outbuf, sizeof outbuf, stdout);
    
        return 0;
}
