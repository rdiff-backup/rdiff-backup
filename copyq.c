/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- the library for network deltas
 * $Id$
 * 
 * Copyright (C) 1999, 2000, 2001 by Martin Pool <mbp@samba.org>
 * Copyright (C) 1999 by Andrew Tridgell
 * Copyright (C) 1999-2000 by Peter Barker.
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

#include <stdio.h>
#include <stdlib.h>

#include "rsync.h"

#include "emit.h"

/* If possible, append this copy command to the end of the previous
 * one.  If not, flush the existing command and begin a new one.  */
int
rs_queue_copy(rs_write_fn_t write_fn, void *write_priv,
               rs_copyq_t * copyq,
               rs_long_t start, size_t len, rs_stats_t * stats)
{
    int             ret;

    assert(start >= 0);

    if (copyq->len == 0) {
        copyq->start = start;
        copyq->len = len;
        return 0;
    } else if (copyq->start + copyq->len == (size_t) start) {
        copyq->len += len;
        return 0;
    } else {
        /* Of course, COPY commands don't *have* to follow each other.  If we
           get two non-contiguous ones, then we flush and start again. */
        ret = rs_copyq_push(write_fn, write_priv, copyq, stats);
        copyq->start = start;
        copyq->len = len;
        return ret;
    }
}


/*
 * If any copy commands are still waiting in the queue, then flush
 * them out.
 */
int
rs_copyq_push(rs_write_fn_t write_fn, void *write_priv,
               rs_copyq_t * copyq, rs_stats_t * stats)
{
    int             ret;

    if (copyq->len == 0)
        return 0;
    assert(copyq->len > 0);

    ret = rs_emit_copy(write_fn, write_priv,
                        copyq->start, copyq->len, stats);
    copyq->len = 0;

    return ret;
}
