/*				       	-*- c-file-style: "bsd" -*-
 * rproxy -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 1999, 2000 by Martin Pool.
 * Copyright (C) 1999 by tridge@samba.org.
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

int
_hs_file_open(char const *filename, int mode)
{
    int             fd;

    fd = open(filename, mode, 0666);
    if (fd == -1) {
	_hs_fatal("error opening %s for mode %#x: %s", filename, mode,
		  strerror(errno));
    }
    return fd;
}


int
_hs_file_copy_all(int from_fd, int to_fd)
{
    ssize_t len, total_len = 0, wlen, off;
    char buf[32768];

    do {
        len = read(from_fd, buf, sizeof buf);
        if (len < 0) {
            _hs_error("read: %s", strerror(errno));
            return -1;
        }
        _hs_trace("read %ld bytes", (long) len);
        total_len += len;
        off = 0;
        while (off < len) {
            wlen = write(to_fd, buf + off, len - off);
            if (wlen < 0) {
                _hs_error("write: %s", strerror(errno));
                return -1;
            }
            _hs_trace("wrote %ld bytes", (long) wlen);
            off += wlen;
        }            
    } while (len > 0);

    _hs_trace("reached eof");

    return total_len;
}
