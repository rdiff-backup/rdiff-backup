/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * Copyright (C) 2000, 2001 by Martin Pool <mbp@sourcefrog.net>
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

#include "config.h"

#include <assert.h>
#include <sys/types.h>
#ifdef HAVE_INTTYPES_H
#  include <inttypes.h>
#endif
#include <stdlib.h>
#include <stdio.h>

#include "librsync.h"

void rs_hexify(char *to_buf, void const *from, int from_len)
{
    static const char hex_chars[] = "0123456789abcdef";
    unsigned char const *from_buf = (unsigned char const *)from;

    while (from_len-- > 0) {
        *(to_buf++) = hex_chars[((*from_buf) >> 4) & 0xf];
        *(to_buf++) = hex_chars[(*from_buf) & 0xf];
        from_buf++;
    }

    *to_buf = 0;
}
