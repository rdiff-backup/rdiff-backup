/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * libhsync -- library for network deltas
 * $Id$
 * 
 * Copyright (C) 1999, 2000, 2001 by Martin Pool <mbp@samba.org>
 * Copyright (C) 1999 by Andrew Tridgell <tridge@samba.org>
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

#ifdef HAVE_STDINT_H
#  include <stdint.h>
#endif

#include <assert.h>
#include <stdlib.h>
#include <unistd.h>
#include <stdio.h>
#include <fcntl.h>
#include <sys/file.h>
#include <string.h>
#include <errno.h>

#include "hsync.h"
#include "fileutil.h"
#include "trace.h"



/**
 * \brief Open a file, with special handling for `-' or unspecified
 * parameters on input and output.
 *
 * \param fopen-style mode string.
 */
FILE *
hs_file_open(char const *filename, char const *mode)
{
    FILE           *f;
    int		    is_write;

    is_write = mode[0] == 'w';

    if (!filename  ||  !strcmp("-", filename)) {
	if (is_write)
	    return stdout;
	else
	    return stdin;
    }

    if (!(f = fopen(filename, mode))) {
	hs_error("Error opening \"%s\" for %s: %s", filename,
		  is_write ? "write" : "read",
		  strerror(errno));
	exit(HS_IO_ERROR);
    }
    
    return f;
}
