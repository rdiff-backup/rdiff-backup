/*				       	-*- c-file-style: "bsd" -*-
 *
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool
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


#include "includes.h"

/* Read all signatures into a newly-allocated sum_struct, and index
   and hash them appropriately.

   The signature stream contains pair of short (4-byte) weak checksums, and
   long (SUM_LENGTH) strong checksums. */
/*@null@*/ hs_sum_set_t *
_hs_read_sum_set(hs_read_fn_t sigread_fn, void *sigreadprivate,
		 int block_len)
{
     struct sum_buf *asignature;
     int index = 0;
     int ret = 0;
     int checksum1;
     hs_sum_set_t *sumbuf;

     sumbuf = malloc(sizeof *sumbuf);
     if (!sumbuf) {
	  errno = ENOMEM;
	  _hs_error("no memory to allocate sum_struct");
	  return NULL;
     }
     hs_bzero(sumbuf, sizeof *sumbuf);
     sumbuf->block_len = block_len;

     sumbuf->sums = NULL;
     /* XXX: It's perhaps a bit inefficient to realloc each time.
	We could prealloc, but for now we'll give realloc the
	benefit of the doubt. */

     while (1) {
	  ret = _hs_read_netint(sigread_fn, sigreadprivate, &checksum1);

	  if (ret == 0)
	       break;
	  if (ret < 0) {
	       _hs_error("IO error while reading in signatures");
	       goto fail;
	  }
	  assert(ret == 4);
	 
	  sumbuf->sums =
	       realloc(sumbuf->sums, (index + 1) * sizeof(struct sum_buf));
	  if (sumbuf->sums == NULL) {
	       errno = ENOMEM;
	       ret = -1;
	       break;
	  }
	  asignature = &(sumbuf->sums[index]);
	 
	  asignature->sum1 = checksum1;
	  asignature->i = ++index;
	 
	  /* read in the long sum */
	  ret = _hs_must_read(sigread_fn, sigreadprivate,
			      asignature->strong_sum, DEFAULT_SUM_LENGTH);
	  if (ret != DEFAULT_SUM_LENGTH) {
	       _hs_error("IO error while reading strong signature %d",
			 index);
	       break;
	  }
     }
     if (ret < 0) {
	 _hs_error("error reading checksums");
	 goto fail;
     }

     sumbuf->count = index;
     _hs_trace("Read %d sigs", index);

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
_hs_free_sum_struct(hs_sum_set_t *psums)
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
