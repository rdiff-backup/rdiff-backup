/*				       	-*- c-file-style: "bsd" -*-
 *
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool <mbp@humbug.org.au>
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


#include "includes.h"

#include <unistd.h>
#include <stdio.h>
#include <sys/file.h>
#include <string.h>


int
hs_log_stats(hs_stats_t const *stats)
{
    char buf[1000];

    hs_format_stats(stats, buf, sizeof buf - 1);
    _hs_log(LOG_INFO, "%s", buf);
    return 0;
}


/*
 * Return a newly-allocated string containing a human-readable form of
 * the transfer statistics.
 */
char *
hs_format_stats(hs_stats_t const * stats,
		char *buf, size_t size)
{
    char const *op = stats->op;
    char const *alg = stats->algorithm;

    if (!op)
        op = "noop";
    if (!alg)
        alg = "none";
    
#ifdef HAVE_SNPRINTF
    snprintf(buf, size,
	     "%s/%s literal[%d cmds, %d bytes], "
	     "signature[%d cmds, %d bytes], "
	     "copy[%d cmds, %d bytes, %d false]",
	     op, alg,
	     stats->lit_cmds, stats->lit_bytes,
	     stats->sig_cmds, stats->sig_bytes,
	     stats->copy_cmds, stats->copy_bytes,
	     stats->false_matches);
#else

    sprintf(buf,
	     "%s/%s literal[%d cmds, %d bytes], "
	     "signature[%d cmds, %d bytes], "
	     "copy[%d cmds, %d bytes, %d false]",
	     op, alg,
	     stats->lit_cmds, stats->lit_bytes,
	     stats->sig_cmds, stats->sig_bytes,
	     stats->copy_cmds, stats->copy_bytes,
	     stats->false_matches);
#endif

    return buf;
}
