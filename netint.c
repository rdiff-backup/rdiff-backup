/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * libhsync -- library for network deltas
 * $Id$
 * 
 * Copyright (C) 1999, 2000, 2001 by Martin Pool <mbp@samba.org>
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

/*
 * Network-byte-order output to the tube.
 *
 * All the `suck' routines return a result code.  The most common
 * values are HS_DONE if they have enough data, or HS_BLOCKED if there
 * is not enough input to proceed.
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

#ifndef __LCLINT__
/* On Linux/glibc this file contains constructs that confuse
 * lclint. */
#  include <netinet/in.h>		/* ntohs, etc */
#endif /* __LCLINT__ */

#include <string.h>

#include "hsync.h"
#include "netint.h"
#include "trace.h"
#include "stream.h"


void hs_squirt_n32(hs_stream_t *stream, int d)
{
    uint32_t nd = htonl(d);
        
    hs_blow_literal(stream, &nd, sizeof nd);
}



void
hs_squirt_n16(hs_stream_t *stream, int d)
{
    uint16_t nd = htons(d);

    hs_blow_literal(stream, &nd, sizeof nd);
}


void
hs_squirt_n8(hs_stream_t *stream, int d)
{
    uint8_t nd = d;

    hs_blow_literal(stream, &nd, sizeof nd);
}



hs_result hs_suck_n32(hs_stream_t *stream, int *v)
{
    void *p;
    int result;

    if ((result = hs_scoop_read(stream, sizeof (uint32_t), &p)) != HS_DONE)
        return result;

    *v = ntohl(* (uint32_t const *) p);

    return result;
}


hs_result hs_suck_n8(hs_stream_t *stream, int *v)
{
    void *p;
    int result;

    if ((result = hs_scoop_read(stream, sizeof (uint8_t), &p)) != HS_DONE)
        return result;

    *v = * (uint8_t const *) p;

    return result;
}



hs_result hs_suck_netint(hs_stream_t *stream, int len, int *v)
{
    switch (len) {
    case 1:
        return hs_suck_n8(stream, v);
    case 4:
        return hs_suck_n32(stream, v);
    default:
        hs_fatal("kaboom! len=%d", len);
    }
}




int hs_fits_in_n8(size_t val)
{
    return val <= UINT8_MAX;
}


int hs_fits_in_n16(size_t val)
{
    return val <= UINT16_MAX;
}


int hs_fits_in_n32(size_t val)
{
    return val <= UINT32_MAX;
}


int hs_int_len(off_t val)
{
    if (hs_fits_in_n8(val))
        return 1;
    else if (hs_fits_in_n16(val))
        return 2;
    else if (hs_fits_in_n32(val))
        return 4;
    else {
        hs_fatal("can't handle integer this long yet");
    }
}

