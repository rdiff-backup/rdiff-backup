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

int show_stats = 0;

static void usage(char *progname)
{
     fprintf(stderr, "Usage: %s OLDFILE NEWSIGFILE [OUTFILE [LT_FILE]]\n"
	     "\n"
	     "Apply the changes specified in LT_FILE (default stdin)\n"
	     "to OLDFILE to produce OUTFILE (default stdout).\n"
	     "OLDFILE must be seekable.  Write a server-generated signature\n"
	     "into NEWSIGFILE\n", progname);
     exit(1);
}


int main(int argc, char *argv[])
{
     return 0;
}
