/*=                     -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * libhsync -- the library for network deltas
 * $Id$
 * 
 * Copyright (C) 1999, 2000, 2001 by Martin Pool <mbp@linuxcare.com.au>
 * Copyright (C) 1999 by Andrew Tridgell <tridge@linuxcare.com.au>
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



#include <config.h>

#include <assert.h>

#ifdef HAVE_STDINT_H
#include <stdint.h>
#endif

#include <sys/types.h>
#include <limits.h>
#include <inttypes.h>
#include <stdlib.h>

#include "hsync.h"
#include "sumset.h"
#include "job.h"
#include "trace.h"
#include "netint.h"
#include "protocol.h"
#include "util.h"


static hs_result hs_readsum_s_header(hs_job_t *job)
{
    int                 magic;
    hs_result           result;

    if ((result = hs_suck_n32(job->stream, &magic)) != HS_OK)
        return result;

    if (magic != HS_SIG_MAGIC) {
        hs_error("wrong magic number %#10x for signature", magic);
        return HS_BAD_MAGIC;
    } else {
        hs_trace("got magic %#10x", magic);
    }

    /* TODO: Get block size; store in sumset. */

    job->statefn = hs_job_s_complete;
    
    return HS_OK;
}


/*
 * Read in nonblocking mode the input of STREAM, and interpret it into
 * a signature set stored in SUMSET.
 */
hs_job_t *hs_readsum_begin(hs_stream_t *stream, hs_sumset_t **sumset)
{
    hs_job_t *job;

    job = hs_job_new(stream);
    job->sumset = *sumset = hs_alloc_struct(hs_sumset_t);
    job->statefn = hs_readsum_s_header;
        
    return job;
}


#if 0
/*
 * readsums.c -- Read a signature file into a memory structure.  A
 * nonblocking state machine to be run through the job architecture.
 */
hs_sumset_t *
hs_read_sumset(hs_read_fn_t sigread_fn, void *sigread_priv)
{
        int             ret = 0;
        int             block_len;
        hs_sum_buf_t   *asignature;
        int             n = 0;
        int             checksum1;
        hs_sumset_t    *sumbuf;
        uint32_t	    tmp32;


        ret = hs_check_sig_version(sigread_fn, sigread_priv);
        if (ret <= 0)
                return NULL;

        if (hs_read_blocksize(sigread_fn, sigread_priv, &block_len) < 0)
                return NULL;

        sumbuf = hs_alloc_struct(hs_sumset_t);

        sumbuf->block_len = block_len;

        sumbuf->block_sums = NULL;
        /* XXX: It's perhaps a bit inefficient to realloc each time. We could
           prealloc, but for now we'll give realloc the benefit of the doubt. */

        while (1) {
                ret = hs_read_netint(sigread_fn, sigread_priv, &tmp32);
                checksum1 = tmp32;

                if (ret == 0)
                        break;
                if (ret < 0) {
                        hs_error("IO error while reading in signatures");
                        goto fail;
                }
                assert(ret == 4);

                sumbuf->block_sums = realloc(sumbuf->block_sums, (n + 1) * sizeof(hs_sum_buf_t));
                if (sumbuf->block_sums == NULL) {
                        errno = ENOMEM;
                        ret = -1;
                        break;
                }
                asignature = &(sumbuf->block_sums[n]);

                asignature->weak_sum = checksum1;
                asignature->i = ++n;

                /* read in the long sum */
                ret = hs_must_read(sigread_fn, sigread_priv,
                                   asignature->strong_sum, DEFAULT_SUM_LENGTH);
                if (ret != DEFAULT_SUM_LENGTH) {
                        hs_error("IO error while reading strong signature %d", n);
                        break;
                }
        }
        if (ret < 0) {
                hs_error("error reading checksums");
                goto fail;
        }

        sumbuf->count = n;
        hs_trace("Read %d sigs", n);

        if (hs_build_hash_table(sumbuf) < 0) {
                hs_error("error building checksum hashtable");
                goto fail;
        }

        return sumbuf;

 fail:
        if (sumbuf)
                free(sumbuf);
        return NULL;
}

#endif
