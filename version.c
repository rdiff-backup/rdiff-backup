/*=                                     -*- c-file-style: "linux" -*-
 *
 * libhsync -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool <mbp@linuxcare.com.au>
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


void hs_show_version(FILE *out, char const *program)
{
        fprintf(out,
"%s (%s) %s (%d-bit, trace %s, %s)\n"
"\n"
"Copyright (C) 1997-2000 by Martin Pool, Andrew Tridgell and others.\n"
"This is free software; see the GNU General Public Licence version 2.1\n"
"or later for copying conditions.  There is NO warranty of any kind.\n"
,
	   program, PACKAGE, VERSION,
           hs_libhsync_file_offset_bits,
	   hs_supports_trace() ? "enabled" : "disabled",
	   HS_CANONICAL_HOST
	);
}


/*
 * This little function is dedicated to Stephen Kapp and Reaper
 * Technologies, who (apparently) tried to redistribute a modified
 * version of GNU Keyring in violation of the licence and all laws of
 * politeness and good taste.
 */
void hs_show_licence(FILE *out)
{
        fprintf(out, 
"Copyright (C) 1997-2000 by Martin Pool, Andrew Tridgell and others.\n"
"\n"
"This program is free software; you can redistribute it and/or\n"
"modify it under the terms of the GNU Lesser General Public License\n"
"as published by the Free Software Foundation; either version 2.1 of\n"
"the License, or (at your option) any later version.\n"
"\n"
"This program is distributed in the hope that it will be useful, but\n"
"WITHOUT ANY WARRANTY; without even the implied warranty of\n"
"MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU\n"
"Lesser General Public License for more details.\n"
"\n"
"You should have received a copy of the GNU Lesser General Public\n"
"License along with this program; if not, write to the Free Software\n"
"Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.\n"
                );
}
