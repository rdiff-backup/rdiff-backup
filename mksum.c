/*				       	-*- c-file-style: "bsd" -*-
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
 * Generate a checksum set, using the newstyle nonblocking
 * arrangement and mapptrs.
 */

#include "includes.h"

#include "mapptr.h"

const int       hs_mksum_job_magic = 123123;

struct hs_mksum_job {
    int             dogtag;
    hs_map_t       *in_map;
    int             in_fd;
    hs_write_fn_t   write_fn;
    void           *write_priv;
    size_t          block_len;
    hs_stats_t      stats;
    int             sent_header;

    /* On next call, we will try to calculate the sum of the block * starting 
       at CURSOR. */
    off_t        cursor;

    size_t          strong_sum_len;
};


/* Set up a new encoding job. */
hs_mksum_job_t *
hs_mksum_begin(int in_fd,
	       hs_write_fn_t write_fn, void *write_priv,
	       size_t new_block_len, size_t strong_sum_len)
{
    hs_mksum_job_t *job;

    job = _hs_alloc_struct(hs_mksum_job_t);

    job->in_fd = in_fd;
    job->write_fn = write_fn;
    job->write_priv = write_priv;
    job->block_len = new_block_len;
    job->dogtag = hs_mksum_job_magic;

    assert(strong_sum_len > 0 && strong_sum_len <= MD4_LENGTH);
    job->strong_sum_len = strong_sum_len;

    if (!(job->in_map = hs_map_file(in_fd))) {
	_hs_fatal("can't map input file");
    }

    return job;
}


static void
_hs_mksum_finish(hs_mksum_job_t * job)
{
    assert(job->dogtag == hs_mksum_job_magic);
    _hs_unmap_file(job->in_map);
    /* We don't close or flush the files because they belong to the * caller. 
     */
    hs_bzero(job, sizeof *job);
    free(job);
}


/* 
 * Generate and write out the checksums of a block.
 */
void
_hs_mksum_of_block(byte_t const *p, ssize_t len,
		   hs_write_fn_t write_fn, void *write_priv,
		   size_t strong_sum_len)
{
    uint32_t        weak_sum;
    byte_t            strong_sum[MD4_LENGTH];

#ifdef DO_HS_TRACE
    char            strong_hex[MD4_LENGTH * 2 + 2];
#endif

    weak_sum = _hs_calc_weak_sum(p, len);
    _hs_calc_strong_sum(p, len, strong_sum, strong_sum_len);

#ifdef DO_HS_TRACE
    hs_hexify_buf(strong_hex, strong_sum, strong_sum_len);
    _hs_trace("calculated weak sum %08lx, strong sum %s",
	      (long) weak_sum, strong_hex);
#endif

    _hs_write_netint(write_fn, write_priv, weak_sum);
    _hs_write_loop(write_fn, write_priv, strong_sum, strong_sum_len);
}


/* 
 * Nonblocking iteration interface for making up a file sum.  Returns
 * HS_AGAIN, HS_DONE or HS_FAILED.  Unless it returns HS_AGAIN, then
 * the job is closed on return.
 */
hs_result_t
hs_mksum_iter(hs_mksum_job_t * job)
{
    int             ret;
    byte_t const     *p;
    size_t         map_len;
    int             saw_eof;

    assert(job->dogtag = hs_mksum_job_magic);

    if (!job->sent_header) {
	ret = _hs_newsig_header(job->block_len,
				job->write_fn, job->write_priv);
	if (ret < 0) {
	    _hs_fatal("error writing new sum signature");
	    return HS_FAILED;
	}
	job->sent_header = 1;
    }

    /* Map a block of data */
    map_len = job->block_len;
    saw_eof = 0;
    p = hs_map_ptr(job->in_map, job->cursor, &map_len, &saw_eof);
    if (!p) {
	_hs_error("error mapping file");
	_hs_mksum_finish(job);
	return HS_FAILED;
    }

    /* Calculate and write out the sums, if any. */
    while (map_len > (size_t) job->block_len) {
	_hs_trace("calc sum for @%ld+%ld", (long) job->cursor,
		  (long) job->block_len);

	_hs_mksum_of_block(p, job->block_len,
			   job->write_fn, job->write_priv,
			   job->strong_sum_len);

	p += job->block_len;
	job->cursor += job->block_len;
	map_len -= job->block_len;
    }

    /* If we're at the end of the file, generate a signature for the * last
       short block and go home. */
    if (saw_eof) {
	_hs_trace("calc sum for @%ld+%ld", (long) job->cursor,
		  (long) map_len);

	_hs_mksum_of_block(p, map_len,
			   job->write_fn, job->write_priv,
			   job->strong_sum_len);

	_hs_mksum_finish(job);
	return HS_DONE;
    }

    /* Well, we haven't finished yet.  Return and hopefully we'll be * called 
       back. */
    return HS_AGAIN;
}
