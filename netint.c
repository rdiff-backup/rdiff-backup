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
 *
 * All the netint operations are done in a fairly simpleminded way,
 * since we don't want to rely on stdint types that may not be
 * available on some platforms.
 */

/*
 * TODO: If we don't have <stdint.h> (or perhaps even if we do),
 * determine endianness and integer size by hand and use that to do
 * our own conversion routines.  We possibly need this anyhow to do
 * 64-bit integers, since there seems to be no ntohs() analog.
 */

#include <config.h>

#include <assert.h>
#include <sys/types.h>
#include <stdlib.h>
#include <stdio.h>

#include <string.h>

#include "hsync.h"
#include "netint.h"
#include "trace.h"
#include "stream.h"

#define HS_MAX_INT_BYTES 8


/**
 * \brief Write a single byte to a stream output.
 */
hs_result
hs_squirt_byte(hs_stream_t *stream, unsigned char d)
{
    hs_blow_literal(stream, &d, 1);
    return HS_DONE;
}


/**
 * \brief Write a variable-length integer to a stream.
 *
 * \param stream Stream of data.
 *
 * \param d Datum to write out.
 *
 * \param len Length of integer, in bytes.
 */
hs_result
hs_squirt_netint(hs_stream_t *stream, off_t d, int len)
{
    unsigned char       buf[HS_MAX_INT_BYTES];
    int                 i, j;

    if (len <= 0 || len > HS_MAX_INT_BYTES) {
        hs_error("Illegal integer length %d", len);
        return HS_INTERNAL_ERROR;
    }

    /* Fill the output buffer with a bigendian representation of the
     * number. */
    for (i = 0, j = len-1; i < len; i++, j--) {
        buf[j] = d;             /* truncated */
        d >>= 8;
    }

    hs_blow_literal(stream, buf, len);

    return HS_DONE;
}



hs_result
hs_squirt_n4(hs_stream_t *stream, int val)
{
    return hs_squirt_netint(stream, val, 4);
}



hs_result
hs_suck_netint(hs_stream_t *stream, off_t *v, int len)
{
    unsigned char       *buf;
    int                 i;
    hs_result           result;

    if (len <= 0 || len > HS_MAX_INT_BYTES) {
        hs_error("Illegal integer length %d", len);
        return HS_INTERNAL_ERROR;
    }

    if ((result = hs_scoop_read(stream, len, (void **) &buf)) != HS_DONE)
        return result;

    *v = 0;

    for (i = 0; i < len; i++) {
        *v = *v<<8 | buf[i];
    }

    return HS_DONE;
}


hs_result
hs_suck_byte(hs_stream_t *stream, unsigned char *v)
{
    void *inb;
    hs_result result;
    
    if ((result = hs_scoop_read(stream, 1, &inb)) == HS_DONE)
        *v = *((unsigned char *) inb);

    return result;
}


hs_result
hs_suck_n4(hs_stream_t *stream, int *v)
{
    hs_result result;
    off_t       d;

    result = hs_suck_netint(stream, &d, 4);
    *v = d;
    return result;
}        


int hs_int_len(off_t val)
{
    if (!(val & ~0xffL))
        return 1;
    else if (!(val & ~0xffffL))
        return 2;
    else if (!(val & ~0xffffffffL))
        return 4;
    else if (!(val & ~0xffffffffffffffffL))
        return 8;
    else {
        hs_fatal("can't encode integer %lld yet", (long long int) val);
    }
}

