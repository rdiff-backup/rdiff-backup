/*=                                     -*- c-file-style: "bsd" -*-
 *
 * libhsync -- library for network deltas
 * $Id$
 *
 * Copyright (C) 2000 by Martin Pool <mbp@samba.org>
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

                                /*
                                 | Let's climb to the TOP of that
                                 | MOUNTAIN and think about STRIP
                                 | MINING!!
                                 */



/*
 * Generate a delta from a set of signatures and a new file.
 */


#include "config.h"

#include <assert.h>

#ifdef HAVE_STDINT_H
#include <stdint.h>
#endif

#include <sys/types.h>
#include <limits.h>
#include <inttypes.h>
#include <stdlib.h>
#include <stdio.h>

#include "hsync.h"
#include "private.h"
#include "emit.h"
#include "stream.h"
#include "tube.h"



/*
 * Prepare to compute a delta on a stream.
 */
int hs_delta_begin(hs_stream_t *stream)
{
    _hs_emit_delta_header(stream);
    
    return HS_OK;
}


/*
 * Consume and produce data to generate a delta.
 */
int hs_delta(hs_stream_t *stream, int UNUSED(ending))
{
    int avail;
    
/*      _hs_stream_swallow(stream);  */

    /* Find out how much input is available.  Write it out as one big
     * command, and remove it from the input stream. */

    if (!_hs_tube_catchup(stream))
	return HS_OK;

    avail = stream->avail_in;
    _hs_emit_literal_cmd(stream, avail);
    _hs_blow_copy(stream, avail);

    if (_hs_stream_is_empty(stream))
	return HS_COMPLETE;
    else
	return HS_OK;
}
