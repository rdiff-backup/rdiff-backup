/*=				       	-*- c-file-style: "bsd" -*-
 *
 * libhsync -- library for network deltas
 * $Id$
 * 
 * Copyright (C) 1999, 2000 by Martin Pool <mbp@samba.org>
 * Copyright (C) 1999 by Andrew Tridgell <tridge@samba.org>
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
 * You should have received a copy of the GNU Lesser General Public
 * License along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

                            /*
                             | Ummm, well, OK.  The network's the
                             | network, the computer's the
                             | computer.  Sorry for the confusion.
                             |        -- Sun Microsystems
                             */

/* Network-byte-order output to the tube. */

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

#ifndef __LCLINT__
/* On Linux/glibc this file contains constructs that confuse
 * lclint. */
#  include <netinet/in.h>		/* ntohs, etc */
#endif /* __LCLINT__ */

#include <string.h>

#include "hsync.h"
#include "private.h"
#include "tube.h"
#include "netint.h"

void
_hs_squirt_n32(hs_stream_t *stream, int d)
{
    uint32_t nd = htonl(d);

    _hs_blow_literal(stream, &nd, sizeof nd);
}



void
_hs_squirt_n8(hs_stream_t *stream, int d)
{
    uint8_t nd = d;

    _hs_blow_literal(stream, &nd, sizeof nd);
}

