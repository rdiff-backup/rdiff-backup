/*				       	-*- c-file-style: "bsd" -*-
 * rproxy -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 1999, 2000 by Martin Pool <mbp@humbug.org.au>
 * Copyright (C) 1999 by Andrew Tridgell
 * 
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU Lesser General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
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

/* Private header for file maps. */

/*
 * HS_MAP structure:
 * 
 * TAG is a dogtag, and always equal to HS_MAP_TAG if the structure is valid. 
 * FD is of course the file descriptor we're using for input.
 * 
 * P points to the start of the allocated data buffer.  P_SIZE is the amount
 * of allocated buffer at P, not all of which necessarily contains valid file 
 * data.
 * 
 * P_FD_OFFSET is the current absolute position of the file cursor. We use
 * this to avoid doing seeks if we're already in the right position.
 * P_OFFSET is the absolute position in the file covered by P[0].  P_LEN is
 * the number of bytes after that point that are valid in P.
 */
#define HS_MAP_TAG  189901

struct hs_map
{
    int                 godtag;
    byte_t             *p;
    int                 fd;
    size_t              p_size, p_len;
    hs_off_t            p_offset, p_fd_offset;
};


/* mapptr private implementation functions */
void *
_hs_map_from_cache(hs_map_t * map, hs_off_t offset, size_t *len);
