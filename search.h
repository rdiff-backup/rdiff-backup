/* -*- c-file-style: "bsd" -*- * * $Id: search.h,v 1.2 2000/06/01 03:30:38
   mbp Exp $ * * Copyright (C) 2000 by Martin Pool * * This program is free 
   software; you can redistribute it and/or modify * it under the terms of
   the GNU General Public License as published by * the Free Software
   Foundation; either version 2 of the License, or * (at your option) any
   later version. * * This program is distributed in the hope that it will
   be useful, * but WITHOUT ANY WARRANTY; without even the implied warranty
   of * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the * GNU
   General Public License for more details. * * You should have received a
   copy of the GNU General Public License * along with this program; if not,
   write to the Free Software * Foundation, Inc., 675 Mass Ave, Cambridge, MA 
   02139, USA. */

int             _hs_find_in_hash(uint32_t weak_sum,
				 byte_t const *inbuf, size_t block_len,
				 hs_sumset_t const *sigs, hs_stats_t *);
