/*=                                     -*- c-file-style: "linux" -*-
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


/*
 * Test driver for network-endian output through a tube.  This test case
 * hopes to catch hangup or data loss errors in the tube buffer.  It's
 * not very scientific about this but just hopes that writing
 * sufficiently large amounts of data will make the bugs come out.
 */


#include "config.h"

#include <assert.h>
#include <stdio.h>
#include <inttypes.h>
#include <stdlib.h>

#include "hsync.h"
#include "netint.h"
#include "tube.h"
#include "streamfile.h"
#include "tube.h"


int main(void)
{
        hs_stream_t stream;
        char outbuf[37];
        int j;

        hs_stream_init(&stream);

        for (j = 0; j < 20; j++) {
                int i;

                for (i = 0; i < 4; i++) {
                        _hs_squirt_n32(&stream, i);
                }

                while (!_hs_tube_is_idle(&stream)) { 
                        _hs_tube_catchup(&stream);
                        _hs_drain_to_file(&stream, outbuf, sizeof outbuf,
                                          stdout);
                }
        }

        return 0;
}


