/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * libhsync -- library for network deltas
 * $Id$
 * 
 * Copyright (C) 1999, 2000 by Martin Pool <mbp@samba.org>
 * Copyright (C) 1999 by Andrew Tridgell <mbp@samba.org>
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
enum hs_op_kind {
        HS_KIND_EOF = 1000,
        HS_KIND_LITERAL,
        HS_KIND_SIGNATURE,
        HS_KIND_COPY,
        HS_KIND_CHECKSUM,
        HS_KIND_RESERVED,           /* for future expansion */

        /* This one should never occur in file streams.  It's an
         * internal marker for invalid commands. */
        HS_KIND_INVALID
};


typedef struct hs_op_kind_name {
    char const           *name;
        enum hs_op_kind const    kind;
} hs_op_kind_name_t;

char const * hs_op_kind_name(enum hs_op_kind);


