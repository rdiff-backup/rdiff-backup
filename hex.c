/* -*- mode: c; c-file-style: "bsd" -*- */
/* 
   Copyright (C) 2000 by Martin Pool
   
   This program is free software; you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation; either version 2 of the License, or
   (at your option) any later version.
   
   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.
   
   You should have received a copy of the GNU General Public License
   along with this program; if not, write to the Free Software
   Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
*/

#include "includes.h"

void
hs_hexify_buf(char *to_buf, unsigned char const *from_buf, int from_len)
{
     static const char hex_chars[] = "0123456789abcdef";
     
     while (from_len-- > 0) {
	  *(to_buf++) = hex_chars[((*from_buf) >> 4) & 0xf];
	  *(to_buf++) = hex_chars[(*from_buf) & 0xf];
	  from_buf++;
     }

     *to_buf = 0;
}
