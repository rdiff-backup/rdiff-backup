/*=                                     -*- c-file-style: "linux" -*-
 *
 * libhsync -- the library for network deltas
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool <mbp@linuxcare.com.au>
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
                               * This is Tranquility.
                               */


#include "config.h"

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


const int HS_PATCH_TAG = 201210;


enum hs_patch_state {
        hs_s_header,
        hs_s_run
};


struct hs_patch_job {
        int          dogtag;
	hs_stream_t *stream;
        int         (*statefn)(hs_patch_job_t *);
};



/* Local prototypes for state functions. */
static int _hs_patch_s_complete(hs_patch_job_t *UNUSED(job));



static void _hs_patch_check(const hs_patch_job_t *job)
{
        assert(job->dogtag == HS_PATCH_TAG);
}




/*
 * Called when we're trying to read the first byte of a command.  Once
 * we've taken that in, we can know how much data to read to get the
 * arguments.
 */
static int _hs_patch_s_cmd(hs_patch_job_t *job)
{
        int op;
        enum hs_result result;
        enum hs_op_kind kind;

        if ((result = _hs_suck_n8(job->stream, &op)) != HS_OK)
                return result;

        assert(op >= 0 && op <= 0xff);
        kind = _hs_prototab[op].kind;
        _hs_trace("got command byte 0x%02x (%s)", op, _hs_op_kind_name(kind));

        switch (kind) {
        case HS_KIND_EOF:
                job->statefn = _hs_patch_s_complete;
                return HS_OK;
                break;
        default:
                _hs_error("bogus command byte 0x%02x", op);
                return HS_BAD_MAGIC;
        }
}



/*
 * Called after encountering EOF on the patch.
 */
static int _hs_patch_s_complete(hs_patch_job_t *UNUSED(job))
{
        return HS_OK;
}


/*
 * Called while we're trying to read the header of the patch.
 */
static int _hs_patch_s_header(hs_patch_job_t *job)
{
        int v;
        int result;

        if ((result =_hs_suck_n32(job->stream, &v)) != HS_OK)
                return result;

        if (v != HS_DELTA_MAGIC)
                return HS_BAD_MAGIC;

        _hs_trace("got patch magic %#10x", v);

        job->statefn = _hs_patch_s_cmd;

        return HS_RUN_OK;
}



/*
 * Begin the job of applying a patch.  This gives you back a JOB
 * object, which can be cranked by calling hs_patch_iter and updating
 * the stream pointers.  When finished, call hs_patch_finish to
 * dispose of it.
 */
hs_patch_job_t *hs_patch_begin(hs_stream_t *stream)
{
	hs_patch_job_t *job = _hs_alloc_struct(hs_patch_job_t);

        job->statefn = _hs_patch_s_header;
        job->dogtag = HS_PATCH_TAG;
        job->stream = stream;

        return job;
}


/*
 * Patch iterator, called by the client as more input data or output space
 * becomes available.
 *
 * Calls whatever code is appropriate to the current state.
 *
 * When the state function is called, it knows the tube is empty, and so
 * it can go ahead and blow output as required.  It might have to return
 * early if not enough input data is available.
 */
int hs_patch_iter(hs_patch_job_t *job)
{
        int result;
        
        _hs_patch_check(job);

        do {
                result = job->statefn(job);
        } while (result == HS_RUN_OK);

        return result;
}


/*
 * Free memory used by applying a patch.  This doesn't finish the work.
 * It just drops it wherever it was.
 */
int hs_patch_finish(hs_patch_job_t *job)
{
        _hs_patch_check(job);
        
	_hs_bzero(job, sizeof *job);
	free(job);

        return HS_OK;
}
