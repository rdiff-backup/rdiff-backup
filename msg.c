/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * libhsync -- the library for network deltas
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

#include <stdio.h>

#include "hsync.h"


/* TODO: Translate from hs_result to human-readable messages. */
char const *hs_strerror(hs_result r)
{
        switch (r) {
        case HS_DONE:
                return "OK";
        case HS_RUNNING:
                return "still running";
        case HS_BAD_MAGIC:
                return "bad magic or stream corrupt";
        case HS_BLOCKED:
                return "blocked waiting for input";
        case HS_SHORT_STREAM:
                return "unexpected end of file";
        default:
                return "unknown error";
        }
}
