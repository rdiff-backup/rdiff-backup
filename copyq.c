/* -*- mode: c; c-file-style: "bsd" -*- */
/* $Id$ */
/* libhsync/copyq.c -- Queue outgoing copy commands.

   Copyright (C) 1999-2000 by Martin Pool. Copyright (C) 1999-2000 by Peter
   Barker. Copyright (C) 1999 by Andrew Tridgell

   This program is free software; you can redistribute it and/or modify it
   under the terms of the GNU General Public License as published by the Free 
   Software Foundation; either version 2 of the License, or (at your option)
   any later version.

   This program is distributed in the hope that it will be useful, but
   WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY 
   or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
   for more details.

   You should have received a copy of the GNU General Public License along
   with this program; if not, write to the Free Software Foundation, Inc., 59 
   Temple Place, Suite 330, Boston, MA 02111-1307 USA */


#include "includes.h"

/* If possible, append this copy command to the end of the previous one.  If
   not, flush the existing command and begin a new one.  */
int
_hs_queue_copy(hs_write_fn_t write_fn, void *write_priv,
	       _hs_copyq_t * copyq,
	       off_t start, size_t len, hs_stats_t * stats)
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
	ret = _hs_copyq_push(write_fn, write_priv, copyq, stats);
	copyq->start = start;
	copyq->len = len;
	return ret;
    }
}


int
_hs_copyq_push(hs_write_fn_t write_fn, void *write_priv,
	       _hs_copyq_t * copyq, hs_stats_t * stats)
{
    int             ret;

    if (copyq->len == 0)
	return 0;
    assert(copyq->len > 0);

    ret =
	_hs_emit_copy(write_fn, write_priv, copyq->start, copyq->len, stats);
    copyq->len = 0;

    return ret;
}
