/*=                                     -*- c-file-style: "linux" -*-
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

#include <stdio.h>
#include <stdlib.h>

#include "isprefix.h"

static void usage(void)
{
    fprintf(stderr, "Usage: isprefix.driver TIP ICEBERG\n");
    exit(2);
}

/*
 * Test driver for strisprefix.  Compares the two parameters; returns
 * true (0) if a prefix, false (1) otherwise.
 */
int main(int argc, char **argv)
{
    if (argc < 3) {
	usage();
    }

    if (strcmp(argv[1], "!")) { 
	return !strisprefix(argv[1], argv[2]);
    } else {
	/* inverted */
	if (argc < 4) {
	    usage();
	}
	return strisprefix(argv[2], argv[3]);
    }
}
