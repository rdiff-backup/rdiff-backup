/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 * rproxy -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 2000, 2001 by Martin Pool <mbp@samba.org>
 * 
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU Lesser General Public License as published by
 * the Free Software Foundation; either version 2.1 of the License, or
 * (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Lesser General Public License for more details.
 * 
 * You should have received a copy of the GNU Lesser General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#include <config.h>

#include <assert.h>
#include <sys/types.h>
#include <inttypes.h>
#include <stdlib.h>
#include <stdio.h>

#include "rsync.h"


void
rs_hexify(char *to_buf, void const *from, int from_len)
{
    static const char hex_chars[] = "0123456789abcdef";
    char const *from_buf = (unsigned char const *) from;

    while (from_len-- > 0) {
	*(to_buf++) = hex_chars[((*from_buf) >> 4) & 0xf];
	*(to_buf++) = hex_chars[(*from_buf) & 0xf];
	from_buf++;
    }

    *to_buf = 0;
}
