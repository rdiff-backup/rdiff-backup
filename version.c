/*=                                     -*- c-file-style: "bsd" -*-
 *
 * libhsync -- dynamic caching and delta update in HTTP
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

#include "config.h"

#include <stdio.h>

#include "hsync.h"


char const * const hs_libhsync_version = PACKAGE " " VERSION;


void
hs_show_version(char const *program)
{
    printf("%s (%s) %s (%d-bit, trace %s, %s)\n"
	   "\n"
"Copyright (C) 1997-2000 by Martin Pool, Andrew Tridgell and others.\n"
"This is free software; see the GNU General Public Licence version 2\n"
"or later for copying conditions.  There is NO warranty of any kind.\n"
,
	   program, PACKAGE, VERSION,
           hs_libhsync_file_offset_bits,
	   hs_supports_trace() ? "enabled" : "disabled",
	   HS_CANONICAL_HOST
	);
}


