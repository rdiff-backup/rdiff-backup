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

/* ========================================

   Things to do with searching through the hashtable of blocks from
   downstream.  */

int             _hs_build_hash_table(hs_sumset_t *sums);

uint32_t        _hs_calc_weak_sum(byte_t const *buf1, int len);

uint32_t        _hs_calc_strong_sum(byte_t const *buf, size_t buf_len,
				    byte_t *sum, size_t sum_len);
