/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- library for network deltas
 *
 * Copyright (C) 1999, 2000, 2001 by Martin Pool <mbp@sourcefrog.net>
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

                            /*=
                             | Ummm, well, OK.  The network's the
                             | network, the computer's the
                             | computer.  Sorry for the confusion.
                             |        -- Sun Microsystems
                             */

/** \file netint.c Network-byte-order output to the tube.
 *
 * All the `suck' routines return a result code. The most common values are
 * RS_DONE if they have enough data, or RS_BLOCKED if there is not enough input
 * to proceed.
 *
 * All the netint operations are done in a fairly simpleminded way, since we
 * don't want to rely on stdint types that may not be available on some
 * platforms.
 *
 * \todo If we don't have <stdint.h> (or perhaps even if we do), determine
 * endianness and integer size by hand and use that to do our own conversion
 * routines. We possibly need this anyhow to do 64-bit integers, since there
 * seems to be no ntohs() analog. */

#include "config.h"

#include <assert.h>
#include <sys/types.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#include "librsync.h"

#include "job.h"
#include "netint.h"
#include "trace.h"
#include "stream.h"

#define RS_MAX_INT_BYTES 8

/** Write a single byte to a stream output. */
rs_result rs_squirt_byte(rs_job_t *job, unsigned char d)
{
    rs_tube_write(job, &d, 1);
    return RS_DONE;
}

/** Write a variable-length integer to a stream.
 *
 * \param job Job of data.
 *
 * \param d Datum to write out.
 *
 * \param len Length of integer, in bytes. */
rs_result rs_squirt_netint(rs_job_t *job, rs_long_t d, int len)
{
    unsigned char buf[RS_MAX_INT_BYTES];
    int i;

    if (len <= 0 || len > RS_MAX_INT_BYTES) {
        rs_error("Illegal integer length %d", len);
        return RS_INTERNAL_ERROR;
    }

    /* Fill the output buffer with a bigendian representation of the number. */
    for (i = len - 1; i >= 0; i--) {
        buf[i] = d;             /* truncated */
        d >>= 8;
    }

    rs_tube_write(job, buf, len);

    return RS_DONE;
}

rs_result rs_squirt_n4(rs_job_t *job, int val)
{
    return rs_squirt_netint(job, val, 4);
}

rs_result rs_suck_netint(rs_job_t *job, rs_long_t *v, int len)
{
    unsigned char *buf;
    int i;
    rs_result result;

    if (len <= 0 || len > RS_MAX_INT_BYTES) {
        rs_error("Illegal integer length %d", len);
        return RS_INTERNAL_ERROR;
    }

    if ((result = rs_scoop_read(job, len, (void **)&buf)) != RS_DONE)
        return result;

    *v = 0;

    for (i = 0; i < len; i++) {
        *v = *v << 8 | buf[i];
    }

    return RS_DONE;
}

rs_result rs_suck_byte(rs_job_t *job, unsigned char *v)
{
    void *inb;
    rs_result result;

    if ((result = rs_scoop_read(job, 1, &inb)) == RS_DONE)
        *v = *((unsigned char *)inb);

    return result;
}

rs_result rs_suck_n4(rs_job_t *job, int *v)
{
    rs_result result;
    rs_long_t d;

    result = rs_suck_netint(job, &d, 4);
    *v = d;
    return result;
}

int rs_int_len(rs_long_t val)
{
    if (!(val & ~(rs_long_t)0xff))
        return 1;
    else if (!(val & ~(rs_long_t)0xffff))
        return 2;
    else if (!(val & ~(rs_long_t)0xffffffff))
        return 4;
    else if (!(val & ~(rs_long_t)0xffffffffffffffff))
        return 8;
    else {
        rs_fatal("can't encode integer " FMT_LONG " yet", val);
        return -1;
    }
}
