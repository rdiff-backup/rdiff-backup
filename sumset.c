/*				       	-*- c-file-style: "bsd" -*-
 * rproxy -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 1999, 2000 by Martin Pool
 * Copyright (C) 1999 by Andrew Tridgell
 * 
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

/* sumset -- Manipulate and do IO on sets of checksums. */

#include "includes.h"

/* Read and remember all the signatures from last time.  Return null * if
   there are no signatures. */

hs_sumset_t    *
hs_read_sumset(hs_read_fn_t sigread_fn, void *sigread_priv)
{
    int             ret = 0;
    int             block_len;
    hs_sum_buf_t   *asignature;
    int             n = 0;
    int             checksum1;
    hs_sumset_t    *sumbuf;
    uint32_t	    tmp32;


    ret = _hs_check_sig_version(sigread_fn, sigread_priv);
    if (ret <= 0)
	return NULL;

    if (_hs_read_blocksize(sigread_fn, sigread_priv, &block_len) < 0)
	return NULL;

    sumbuf = _hs_alloc_struct(hs_sumset_t);

    sumbuf->block_len = block_len;

    sumbuf->sums = NULL;
    /* XXX: It's perhaps a bit inefficient to realloc each time. We could
       prealloc, but for now we'll give realloc the benefit of the doubt. */

    while (1) {
	ret = _hs_read_netint(sigread_fn, sigread_priv, &tmp32);
	checksum1 = tmp32;

	if (ret == 0)
	    break;
	if (ret < 0) {
	    _hs_error("IO error while reading in signatures");
	    goto fail;
	}
	assert(ret == 4);

	sumbuf->sums = realloc(sumbuf->sums, (n + 1) * sizeof(hs_sum_buf_t));
	if (sumbuf->sums == NULL) {
	    errno = ENOMEM;
	    ret = -1;
	    break;
	}
	asignature = &(sumbuf->sums[n]);

	asignature->sum1 = checksum1;
	asignature->i = ++n;

	/* read in the long sum */
	ret = _hs_must_read(sigread_fn, sigread_priv,
			    asignature->strong_sum, DEFAULT_SUM_LENGTH);
	if (ret != DEFAULT_SUM_LENGTH) {
	    _hs_error("IO error while reading strong signature %d", n);
	    break;
	}
    }
    if (ret < 0) {
	_hs_error("error reading checksums");
	goto fail;
    }

    sumbuf->count = n;
    _hs_trace("Read %d sigs", n);

    if (_hs_build_hash_table(sumbuf) < 0) {
	_hs_error("error building checksum hashtable");
	goto fail;
    }

    return sumbuf;

  fail:
    if (sumbuf)
	free(sumbuf);
    return NULL;
}


void
hs_free_sumset(hs_sumset_t * psums)
{
    if (psums->sums)
	free(psums->sums);

    assert(psums->tag_table);
    free(psums->tag_table);

    if (psums->targets)
	free(psums->targets);

    hs_bzero(psums, sizeof *psums);
    free(psums);
}
