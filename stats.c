/* -*- mode: c; c-file-style: "bsd" -*-  */

/* hsencode.c -- Generate combined encoded form
   
   Copyright (C) 2000 by Martin Pool.

   This program is free software; you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation; either version 2 of the License, or
   (at your option) any later version.
   
   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.
   
   You should have received a copy of the GNU General Public License
   along with this program; if not, write to the Free Software
   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA */

#include "includes.h"

/* Return a newly-allocated string containing a human-readable form of
   the transfer statistics. */   
char *
hs_format_stats(hs_stats_t const *  stats)
{
     char *buf = malloc(256);
     if (!buf)
	  return NULL;

     if (!stats)
	  return NULL;
     
     sprintf(buf, "literal[%d cmds, %d bytes], "
	     "signature[%d cmds, %d bytes], "
	     "copy[%d cmds, %d bytes, %d false]",
	     stats->lit_cmds, stats->lit_bytes,
	     stats->sig_cmds, stats->sig_bytes,
	     stats->copy_cmds, stats->copy_bytes,
	     stats->false_matches);
     return buf;
}
