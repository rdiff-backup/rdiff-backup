/*=                                     -*- c-file-style: "linux" -*-
 *
 * libhsync -- the library for network deltas
 * $Id$
 * 
 * Copyright (C) 2000, 2001 by Martin Pool <mbp@linuxcare.com.au>
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

/*
 * TODO: As output is produced, accumulate the MD4 checksum of the
 * output.  Then if we find a CHECKSUM command we can check it's
 * contents against the output.
 *
 * TODO: Implement COPY commands.
 */


#include <assert.h>
#include <stdlib.h>
#include <stdio.h>

#include "hsync.h"
#include "util.h"
#include "trace.h"
#include "protocol.h"
#include "netint.h"
#include "command.h"
#include "prototab.h"
#include "stream.h"
#include "job.h"



const int HS_PATCH_TAG = 201210;


/* Local prototypes for state functions. */
static enum hs_result hs_patch_s_complete(hs_job_t *);
static enum hs_result hs_patch_s_cmdbyte(hs_job_t *);
static enum hs_result hs_patch_s_params(hs_job_t *);
static enum hs_result hs_patch_s_run(hs_job_t *);
static enum hs_result hs_patch_s_literal(hs_job_t *);



/*
 * Called when we're trying to read the first byte of a command.  Once
 * we've taken that in, we can know how much data to read to get the
 * arguments.
 */
static enum hs_result hs_patch_s_cmdbyte(hs_job_t *job)
{
        enum hs_result result;
        
        if ((result = hs_suck_n8(job->stream, &job->op)) != HS_OK)
                return result;

        assert(job->op >= 0 && job->op <= 0xff);
        job->cmd = &hs_prototab[job->op];
        
        hs_trace("got command byte 0x%02x (%s)", job->op,
                  hs_op_kind_name(job->cmd->kind));

        if (job->cmd->len_1)
                job->statefn = hs_patch_s_params;
        else
                job->statefn = hs_patch_s_run;

        return HS_RUN_OK;
}


/*
 * Called after reading a command byte to pull in its parameters and
 * then setup to execute the command.
 */
static enum hs_result hs_patch_s_params(hs_job_t *job)
{
        enum hs_result result;
        int len = job->cmd->len_1 + job->cmd->len_2;
        void *p;

        assert(len);

        result = hs_scoop_readahead(job->stream, len, &p);
        if (result != HS_OK)
                return result;

        /* we now must have LEN bytes buffered */
        result = hs_suck_netint(job->stream, job->cmd->len_1, &job->param1);
        /* shouldn't fail, since we already checked */
        assert(result == HS_OK);

        if (job->cmd->len_2) {
                result = hs_suck_netint(job->stream, job->cmd->len_2, 
                                        &job->param2);
                assert(result == HS_OK);
        }

        job->statefn = hs_patch_s_run;

        return HS_RUN_OK;
}



/*
 * Called when we've read in the whole command and we need to execute it.
 */
static enum hs_result hs_patch_s_run(hs_job_t *job)
{
        hs_trace("running command 0x%x, kind %d", job->op, job->cmd->kind);

        switch (job->cmd->kind) {
        case HS_KIND_LITERAL:
                job->statefn = hs_patch_s_literal;
                return HS_RUN_OK;
        case HS_KIND_EOF:
                job->statefn = hs_patch_s_complete;
                return HS_OK;
                /* so we exit here; trying to continue causes an error */
        default:
                hs_error("bogus command 0x%02x", job->op);
                return HS_BAD_MAGIC;
        }
}


/*
 * Called when trying to copy through literal data.
 */
static enum hs_result hs_patch_s_literal(hs_job_t *job)
{
        int len;
        if (job->cmd->len_1)
                len = job->param1;
        else
                len = job->cmd->immediate;
        
        hs_trace("copying %d bytes of literal data", len);

        hs_blow_copy(job->stream, len);

        job->statefn = hs_patch_s_cmdbyte;
        return HS_RUN_OK;
}


/*
 * Called after encountering EOF on the patch.
 */
static enum hs_result hs_patch_s_complete(hs_job_t *UNUSED(job))
{
        hs_fatal("the patch has already finished");
}


/*
 * Called while we're trying to read the header of the patch.
 */
static enum hs_result hs_patch_s_header(hs_job_t *job)
{
        int v;
        int result;

        if ((result =hs_suck_n32(job->stream, &v)) != HS_OK)
                return result;

        if (v != HS_DELTA_MAGIC)
                return HS_BAD_MAGIC;

        hs_trace("got patch magic %#10x", v);

        job->statefn = hs_patch_s_cmdbyte;

        return HS_RUN_OK;
}



/*
 * Begin the job of applying a patch.  This gives you back a JOB
 * object, which can be cranked by calling hs_patch_iter and updating
 * the stream pointers.  When finished, call hs_patch_finish to
 * dispose of it.
 */
hs_job_t *hs_patch_begin(hs_stream_t *stream, hs_copy_cb *copy_cb,
                         void *copy_arg)
{
	hs_job_t *job = hs_job_new(stream);

        job->statefn = hs_patch_s_header;
        job->stream = stream;
        
        job->copy_cb = copy_cb;
        job->copy_arg = copy_arg;

	hs_mdfour_begin(&job->output_md4);

        return job;
}

