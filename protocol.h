/*=                                     -*- c-file-style: "bsd" -*-
 * rproxy -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 1999, 2000 by Martin Pool <mbp@humbug.org.au>
 * Copyright (C) 1999 by Andrew Tridgell
 * 
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public License
 * as published by the Free Software Foundation; either version 2.1 of
 * the License, or (at your option) any later version.
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
 * TODO: Have a way to copy from the old signature into the new
 * one. This will be useful for the case where the files are in fact
 * identical, which will be significantly common.
 */


                          /*
                           | "The IETF already has more than enough
                           | RFCs that codify the obvious, make
                           | stupidity illegal, support truth,
                           | justice, and the IETF way, and generally
                           | demonstrate the author is a brilliant and
                           | valuable Contributor to The Standards
                           | Process."
                           |     -- Vernon Schryver
                           */



#define HS_LT_MAGIC             0x67640036      /* "gd\000\001" */
#define HS_SIG_MAGIC            0x67640136      /* "gd\0016" */


/* 
 * Encoding opcodes.
 * 
 * We require 6 + 3 + 3 + 1 = 13 non-inline opcodes; we'll reserve three to
 * keep things simple.  That means we have 240 inline opcodes, or 120 each
 * for literals and signature.
 * 
 * TODO: What about a special case for offset=0?  This will be pretty common.
 *
 * Actually, perhaps we should release some of the hardcoded cases.
 * If we're encoding a 100-byte run it doesn't hurt too much to
 * explicitly give the length, but it would be good to have some space
 * to add new commands in the future.  If a decoder sees a command it
 * doesn't recognize, it should flag an error.
 */
enum {
    op_eof = 0,

    op_literal_1 = 0x01,
    op_literal_last = 0x78,
    op_literal_byte = 0x79,
    op_literal_short = 0x7a,
    op_literal_int = 0x7b,

    op_signature_1 = 0x7c,
    op_signature_last = 0xf2,
    op_signature_byte = 0xf3,
    op_signature_short = 0xf4,
    op_signature_int = 0xf5,

    op_checksum_short = 0xf6,

    op_copy_short_byte = 0xf7,
    op_copy_short_short = 0xf8,
    op_copy_short_int = 0xf9,
    op_copy_int_byte = 0xfa,
    op_copy_int_short = 0xfb,
    op_copy_int_int = 0xfc,
    op_copy_llong_byte = 0xfd,
    op_copy_llong_short = 0xfe,
    op_copy_llong_int = 0xff
};



/*
 * Declarations for a table describing how to encode and decode these
 * commands.  The actual table is in prototab.c.
 */
