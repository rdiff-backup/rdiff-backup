/*=				       	-*- c-file-style: "bsd" -*-
 * libhsync -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 1999, 2000 by Martin Pool <mbp@humbug.org.au>
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

#include <config.h>

#include <assert.h>

#ifdef HAVE_STDINT_H
#include <stdint.h>
#endif

#include <sys/types.h>
#include <limits.h>
#include <inttypes.h>
#include <stdlib.h>

#ifndef __LCLINT__
/* On Linux/glibc this file contains constructs that confuse
 * lclint. */
#  include <netinet/in.h>		/* ntohs, etc */
#endif /* __LCLINT__ */

#include <string.h>

#include "hsync.h"
#include "private.h"
#include "tube.h"
 
int
_hs_write_netint(hs_write_fn_t write_fn, void *write_priv, uint32_t out)
{
    uint32_t        net_out = htonl(out);

    return hs_must_write(write_fn, write_priv, &net_out, sizeof net_out);
}


int
_hs_write_netshort(hs_write_fn_t write_fn, void *write_priv, uint16_t out)
{
    uint16_t        net_out = htons(out);

    return hs_must_write(write_fn, write_priv, &net_out, sizeof net_out);
}


int
_hs_write_netbyte(hs_write_fn_t write_fn, void *write_priv, uint8_t out)
{
    return hs_must_write(write_fn, write_priv, &out, sizeof out);
}


int
_hs_read_netshort(hs_read_fn_t read_fn, void *read_priv, uint16_t * result)
{
    uint16_t        buf;
    int             ret;

    ret = _hs_must_read(read_fn, read_priv, (byte_t *) &buf, sizeof buf);
    *result = ntohs(buf);

    return ret;
}


int
_hs_read_netint(hs_read_fn_t read_fn, void *read_priv, uint32_t * result)
{
    uint32_t        buf;
    int             ret;

    ret = _hs_must_read(read_fn, read_priv, (byte_t *) &buf, sizeof buf);
    *result = ntohl(buf);

    return ret;
}


int
_hs_read_netbyte(hs_read_fn_t read_fn, void *read_priv, uint8_t * result)
{
    uint8_t         buf;
    int             ret;
    const int       len = sizeof buf;

    ret = _hs_must_read(read_fn, read_priv, (byte_t *) &buf, len);
    *result = buf;

    return len;
}



int
_hs_write_netvar(hs_write_fn_t write_fn, void *write_priv,
		 uint32_t value, int type)
{
    if (type == 1)
	return _hs_write_netbyte(write_fn, write_priv, value);
    else if (type == 2)
	return _hs_write_netshort(write_fn, write_priv, value);
    else if (type == 4)
	return _hs_write_netint(write_fn, write_priv, value);
    else
	assert(0);
    return 0;			/* as if! */
}
