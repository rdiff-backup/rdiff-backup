/* -*- mode: c; c-file-style: "stroustrup" -*- * * $Id: filebuf.c,v 1.16
 * 2000/04/25 03:33:28 mbp Exp $ *
 * 
 * Copyright (C) 1999, 2000 by Martin Pool. Copyright (C) 1999 by
 * tridge@samba.org.
 * 
 * This program is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by the Free 
 * Software Foundation; either version 2 of the License, or (at your option)
 * any later version.
 * 
 * This program is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY 
 * or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
 * for more details.
 * 
 * You should have received a copy of the GNU General Public License along
 * with this program; if not, write to the Free Software Foundation, Inc., 59 
 * Temple Place, Suite 330, Boston, MA  02111-1307  USA */

#include "includes.h"
#include "hsync.h"
#include "private.h"

int
hs_file_open(char const *filename, int mode)
{
    int             fd;

    fd = open(filename, mode, 0666);
    if (fd == -1) {
	_hs_fatal("error opening %s for mode %#x: %s", filename, mode,
		  strerror(errno));
    }
    return fd;
}
