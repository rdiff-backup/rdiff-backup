/*				       	-*- c-file-style: "linux" -*-
 *
 * libhsync -- library for network deltas
 * $Id$
 * 
 * Copyright (C) 1999, 2000 by Martin Pool <mbp@samba.org>
 * Copyright (C) 1999 by mbp@samba.org.
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


void
hs_file_close(int fd)
{
    if (fd == -1)
        hs_error("warning: close called with fd of -1");
    
    if (close(fd) == -1) {
        hs_error("error closing fd %d: %s",
                  fd, strerror(errno));
    }
}


/*
 * Open a file, with special handling for `-' on input and output.
 */
FILE *
hs_file_open(char const *filename, int mode)
{
    int             fd;
    FILE           *f;
    int		    is_write;

    if ((mode & O_ACCMODE) == O_WRONLY) {
	is_write = 1;
    } else {
	is_write = 0;
	assert((mode & O_ACCMODE) == O_RDONLY);
    }

    if (!strcmp("-", filename)) {
	if (is_write)
	    return stdout;
	else
	    return stdin;
    }

    fd = open(filename, mode, 0666);
    if (fd == -1) {
	hs_error("Error opening \"%s\" for %s: %s", filename,
		  (mode & O_WRONLY) ? "write" : "read",
		  strerror(errno));
	exit(1);
    }

    f = fdopen(fd, is_write ? "w" : "r");
    if (!f) {
	hs_error("Error opening stream on fd%d: %s", fd,
		  strerror(errno));
	exit(1);
    }
    
    return f;
}
