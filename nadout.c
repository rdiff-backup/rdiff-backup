/*=				       	-*- c-file-style: "bsd" -*-
 * rproxy -- dynamic caching and delta update in HTTP
 * $Id$
 *
 * Copyright (C) 1999, 2000 by Martin Pool <mbp@humbug.org.au>
 * Copyright (C) 1999 by Andrew Tridgell
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
 * TODO: Use the copyq and literal buffer to send stuff out, rather
 * than writing it a bit at a time in this fashion.
 */

#include "includes.h"
#include "mapptr.h"
#include "nad_p.h"
#include "command.h"
#include "emit.h"


void
_hs_nad_flush_literal(hs_encode_job_t *job)
{
    size_t              len;
    byte_t const       *p;

    assert(job->literal_cursor <= job->search_cursor);
    len = job->search_cursor - job->literal_cursor;

    if (len == 0)
        return;                 /* no literal data at the moment */

    /* XXX: These members don't exist yet!! */
    p = job->map_p + job->literal_cursor - job->map_off;

    _hs_trace("flush out %ld bytes of literal data @%ld",
              (long) len, (long) job->literal_cursor);

    _hs_send_literal(job->write_fn, job->write_priv, op_kind_literal,
                     p, len);
    job->stats->lit_cmds++;
    job->stats->lit_bytes += len;

    job->literal_cursor = job->search_cursor;
}





void
_hs_nad_got_copy(hs_encode_job_t *job,
                 off_t off,
                 size_t len)
{
    if (job->literal_cursor < job->search_cursor) {
        _hs_nad_flush_literal(job);
    }

    _hs_emit_copy(job->write_fn, job->write_priv,
                  off, len,
                  job->stats);

    job->search_cursor += len;
    job->literal_cursor = job->search_cursor;
}


