/*=                    -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 2000, 2001 by Martin Pool <mbp@samba.org>
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
                               * [almost sobbing] They don't sleep
                               * anymore on the beach.  They don't
                               * sleep on the beach anymore.
                               */


#include <config.h>

#include <assert.h>
#include <stdlib.h>
#include <stdio.h>

#include "rsync.h"
#include "command.h"
#include "protocol.h"
#include "trace.h"
#include "emit.h"
#include "prototab.h"
#include "netint.h"
#include "sumset.h"
#include "job.h"


/*
 * Write the magic for the start of a delta.
 */
void
rs_emit_delta_header(rs_job_t *job)
{
    rs_trace("emit DELTA magic");
    rs_squirt_n4(job, RS_DELTA_MAGIC);
}



/* Write a LITERAL command. */
void
rs_emit_literal_cmd(rs_job_t *job, int len)
{
    int cmd;
    int bytes;

    switch (bytes = rs_int_len(len)) {
    case 1:
        cmd = RS_OP_LITERAL_N1;
        break;
    case 2:
        cmd = RS_OP_LITERAL_N2;
        break;
    case 4:
        cmd = RS_OP_LITERAL_N4;
        break;
    default:
        rs_fatal("What?");
    }
    
    rs_trace("emit LITERAL_N%d(len=%d), cmd_byte=%#x", bytes, len, cmd);
    rs_squirt_byte(job, cmd);
    rs_squirt_netint(job, len, bytes);

    job->stats.lit_cmds++;
    job->stats.lit_bytes += len;
}


/** Write an END command. */
void
rs_emit_end_cmd(rs_job_t *job)
{
    int cmd = RS_OP_END;
    
    rs_trace("emit END, cmd_byte=%#x", cmd);
    rs_squirt_byte(job, cmd);
}
