/*=                                     -*- c-file-style: "bsd" -*-
 * rproxy -- dynamic caching and delta update in HTTP
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


#include "includes.h"

#include "varint.h"

#ifndef __LCLINT__
/* On Linux/glibc this file contains constructs that confuse lclint. */
#  include <netinet/in.h>		/* ntohs, etc */
#endif /* __LCLINT__ */


int
_hs_read_varint(byte_t const *p, int len)
{
    uint16_t tmp16;
    uint32_t tmp32;

    /* XXX: Do any machine still care about unaligned access to
     * integers? */
    switch (len) {
    case 1:
        return *p;
    case 2:
	memcpy(&tmp16, p, sizeof tmp16);
	return ntohs(tmp16);
    case 4:
	memcpy(&tmp32, p, sizeof tmp32);
	return ntohl(tmp32);
    default:
        _hs_fatal("don't know how to read integer of length %d", len);
        return 0;               /* UNREACHABLE */
    }
}

