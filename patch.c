/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * libhsync -- the library for network deltas
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
                               * This is Tranquility Base.
                               */


#include <config.h>

#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <stdint.h>

#include "hsync.h"
#include "util.h"
#include "trace.h"
#include "protocol.h"
#include "netint.h"
#include "command.h"
#include "sumset.h"
#include "prototab.h"
#include "stream.h"
#include "job.h"



static hs_result hs_patch_s_cmdbyte(hs_job_t *);
static hs_result hs_patch_s_params(hs_job_t *);
static hs_result hs_patch_s_run(hs_job_t *);
static hs_result hs_patch_s_literal(hs_job_t *);



/**
 * State of trying to read the first byte of a command.  Once we've
 * taken that in, we can know how much data to read to get the
 * arguments.
 */
static hs_result hs_patch_s_cmdbyte(hs_job_t *job)
{
    hs_result result;
        
    if ((result = hs_suck_n1(job->stream, &job->op)) != HS_DONE)
        return result;

    assert(job->op >= 0 && job->op <= 0xff);
    job->cmd = &hs_prototab[job->op];
        
    hs_trace("got command byte 0x%02x (%s), len_1=%d", job->op,
             hs_op_kind_name(job->cmd->kind),
             job->cmd->len_1);

    if (job->cmd->len_1)
        job->statefn = hs_patch_s_params;
    else
        job->statefn = hs_patch_s_run;

    return HS_RUNNING;
}


/**
 * Called after reading a command byte to pull in its parameters and
 * then setup to execute the command.
 */
static hs_result hs_patch_s_params(hs_job_t *job)
{
        hs_result result;
        int len = job->cmd->len_1 + job->cmd->len_2;
        void *p;

        assert(len);

        result = hs_scoop_readahead(job->stream, len, &p);
        if (result != HS_DONE)
                return result;

        /* we now must have LEN bytes buffered */
        result = hs_suck_netint(job->stream, job->cmd->len_1, &job->param1);
        /* shouldn't fail, since we already checked */
        assert(result == HS_DONE);

        if (job->cmd->len_2) {
                result = hs_suck_netint(job->stream, job->cmd->len_2, 
                                        &job->param2);
                assert(result == HS_DONE);
        }

        job->statefn = hs_patch_s_run;

        return HS_RUNNING;
}



/**
 * Called when we've read in the whole command and we need to execute it.
 */
static hs_result hs_patch_s_run(hs_job_t *job)
{
        hs_trace("running command 0x%x, kind %d", job->op, job->cmd->kind);

        switch (job->cmd->kind) {
        case HS_KIND_LITERAL:
                job->statefn = hs_patch_s_literal;
                return HS_RUNNING;
        case HS_KIND_END:
                return HS_DONE;
                /* so we exit here; trying to continue causes an error */
        default:
                hs_error("bogus command 0x%02x", job->op);
                return HS_BAD_MAGIC;
        }
}


/**
 * Called when trying to copy through literal data.
 */
static hs_result hs_patch_s_literal(hs_job_t *job)
{
    int len;
    if (job->cmd->len_1)
        len = job->param1;
    else
        len = job->cmd->immediate;
        
    hs_trace("copying %d bytes of literal data", len);

    job->stats.lit_cmds++;
    job->stats.lit_bytes += len;

    hs_blow_copy(job->stream, len);

    job->statefn = hs_patch_s_cmdbyte;
    return HS_RUNNING;
}


/**
 * Called while we're trying to read the header of the patch.
 */
static hs_result hs_patch_s_header(hs_job_t *job)
{
        int v;
        int result;

        
        if ((result =hs_suck_n4(job->stream, &v)) != HS_DONE)
                return result;

        if (v != HS_DELTA_MAGIC)
                return HS_BAD_MAGIC;

        hs_trace("got patch magic %#10x", v);

        job->statefn = hs_patch_s_cmdbyte;

        return HS_RUNNING;
}



/**
 * \brief Apply a \ref gloss_delta to a \ref gloss_basis to recreate
 * the new file.
 *
 * This gives you back a ::hs_job_t object, which can be cranked by
 * calling hs_job_iter() and updating the stream pointers.  When
 * finished, call hs_job_finish() to dispose of it.
 *
 * \param stream Contains pointers to input and output buffers, to be
 * adjusted by caller on each iteration.
 *
 * \param copy_cb Callback used to retrieve content from the basis
 * file.
 *
 * \param copy_arg Opaque environment pointer passed through to the
 * callback.
 *
 * \todo As output is produced, accumulate the MD4 checksum of the
 * output.  Then if we find a CHECKSUM command we can check it's
 * contents against the output.
 *
 * \todo Implement COPY commands.
 *
 * \sa hs_patch_file()
 */
hs_job_t *hs_patch_begin(hs_stream_t *stream, hs_copy_cb *copy_cb,
                         void *copy_arg)
{
    hs_job_t *job = hs_job_new(stream, "patch");

    job->statefn = hs_patch_s_header;
    job->stream = stream;
        
    job->copy_cb = copy_cb;
    job->copy_arg = copy_arg;

    hs_mdfour_begin(&job->output_md4);

    return job;
}
