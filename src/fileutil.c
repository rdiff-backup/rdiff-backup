/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- library for network deltas
 * $Id$
 * 
 * Copyright (C) 1999, 2000, 2001 by Martin Pool <mbp@sourcefrog.net>
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

#include "config.h"

#include <assert.h>
#include <stdlib.h>
#ifdef HAVE_UNISTD_H
#include <unistd.h>
#endif
#include <stdio.h>
#ifdef HAVE_FCNTL_H
#include <fcntl.h>
#endif
#ifdef HAVE_SYS_FILE_H
#include <sys/file.h>
#endif
#include <string.h>
#include <errno.h>

#include "librsync.h"
#include "fileutil.h"
#include "trace.h"



/**
 * \brief Open a file, with special handling for `-' or unspecified
 * parameters on input and output.
 *
 * \param fopen-style mode string.
 */
FILE *
rs_file_open(char const *filename, char const *mode)
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
	rs_error("Error opening \"%s\" for %s: %s", filename,
		  is_write ? "write" : "read",
		  strerror(errno));
	exit(RS_IO_ERROR);
    }
    
    return f;
}

int rs_file_close(FILE * f)
{
    if ((f == stdin) || (f == stdout)) return 0;
    return fclose(f);
}
