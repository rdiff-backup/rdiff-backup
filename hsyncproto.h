/* -*- mode: c; c-file-style: "gnu" -*-  */

/* hsyncproto -- Protocol special numbers
   Copyright (C) 2000 by Martin Pool <mbp@humbug.org.au>

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
   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
   USA
*/


#define HS_LT_MAGIC		0x67640001          /* "gd\000\001" */
#define HS_SIG_MAGIC		0x67642001	    /* "gd \001" */


/* ========================================

   Encoding opcodes.

   We require 6 + 3 + 3 + 1 = 13 non-inline opcodes; we'll reserve
   three to keep things simple.  That means we have 240 inline
   opcodes, or 120 each for literals and signature. */

enum {
    op_eof = 0,

    op_literal_1 = 1,
    op_literal_last = 120,
    op_literal_byte = 121,
    op_literal_short = 122,
    op_literal_int = 123,

    op_signature_1 = 124,
    op_signature_last = 243,
    op_signature_byte = 244,
    op_signature_short = 245,
    op_signature_int = 246,

    /* 247, 248, 249 are reserved */

    op_copy_short_byte = 250,
    op_copy_short_short,
    op_copy_short_int,
    op_copy_int_byte,
    op_copy_int_short,
    op_copy_int_int
};
