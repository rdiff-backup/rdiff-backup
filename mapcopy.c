/*=                                     -*- c-file-style: "bsd" -*-
 * rproxy -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool <mbp@humbug.org.au>
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


                                        /*
                                         | BRRRM!
                                         */

#include "includes.h"
#include "mapptr.h"

/* XXX: Too many parameters to this function!  Maybe just a single
 * callback which can be configured to do the mdfour as well would
 * help. */

/*
 * Copy a region from MAP into another file.  Integrating this with
 * the map lets us be smart about processing however much data is
 * available at any point.
 *
 * POS is moved forward after the copy is complete.
 *
 * NB: Because this function might issue many mapptr calls to complete
 * the copy, you in general cannot go back to the start of the region
 * after this call, because it may have been discarded from the
 * buffer.  If you want to keep it in the buffer, then you must issue
 * a single big mapptr for the whole thing.
 */
hs_result_t
_hs_map_copy(hs_map_t *map, size_t length, off_t *pos,
             hs_write_fn_t write_fn, void *write_priv, hs_mdfour_t * newsum)
{
    byte_t const  *p;
    size_t         map_len;
    int            reached_eof;
    int            result;

    _hs_trace("copy @%ld+%ld", (long) *pos, (long) length);

    while (length > 0) {
        map_len = length;
        /* TODO: handle nonblocking input */
        p = hs_map_ptr(map, *pos, &map_len, &reached_eof);
        if (!p) {
            _hs_fatal("error in map");
        }
        if (map_len == 0  &&  reached_eof) {
            _hs_trace("no more data, at end of file");
            return HS_DONE;
        }

        /* don't write too much! */
        if (map_len > length)
            map_len = length;
        
        if (newsum)
            hs_mdfour_update(newsum, p, map_len);
        
        result = _hs_write_loop(write_fn, write_priv, p, map_len);
        if ((unsigned) result != map_len)
            return HS_FAILED;

        *pos += map_len;
        length -= map_len;
    }

    return HS_DONE;
}


