/*				       	-*- c-file-style: "bsd" -*-
 *
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool
 * 
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */


#include "includes.h"


void
hs_print_stats(FILE *f, hs_stats_t const *stats)
{
    char buf[256];
    
    hs_format_stats(stats, buf, sizeof buf-1);
    fprintf(f, "%.*s\n", (int) sizeof buf, buf);
}


/* Return a newly-allocated string containing a human-readable form of
   the transfer statistics. */   
char *
hs_format_stats(hs_stats_t const * stats,
		char *buf, size_t size)
{
    snprintf(buf, size,
	     "%s/%s literal[%d cmds, %d bytes], "
	     "signature[%d cmds, %d bytes], "
	     "copy[%d cmds, %d bytes, %d false]",
	     stats->op, stats->algorithm,
	     stats->lit_cmds, stats->lit_bytes,
	     stats->sig_cmds, stats->sig_bytes,
	     stats->copy_cmds, stats->copy_bytes,
	     stats->false_matches);
    return buf;
}
