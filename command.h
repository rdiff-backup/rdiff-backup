/*=                                     -*- c-file-style: "bsd" -*-
 * rproxy -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 1999, 2000 by Martin Pool <mbp@samba.org>
 * Copyright (C) 1999 by Andrew Tridgell <tridge@samba.org>
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


/* ===================================================================
 * command.h -- Types of commands present in the encoding stream.
 *
 * The vague idea is that eventually this file will be more abstract
 * than protocol.h.
 * =================================================================== */


/*
 * Classes of operation that can be present.  Each may have several different
 * possible representations.
 */
typedef enum hs_op_kind {
    op_kind_eof = 1000,
    op_kind_literal,
    op_kind_signature,
    op_kind_copy,
    op_kind_checksum,
    op_kind_reserved,           /* for future expansion */

    /* This one should never occur in file streams.  It's an internal
     * marker for invalid commands. */
    op_kind_invalid
} hs_op_kind_t;


typedef struct hs_op_kind_name {
    char const           *name;
    hs_op_kind_t const    kind;
} hs_op_kind_name_t;

char const * _hs_op_kind_name(hs_op_kind_t);


