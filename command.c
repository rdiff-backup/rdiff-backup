/*=                                     -*- c-file-style: "linux" -*-
 *
 * libhsync -- the library for network deltas
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool <mbp@linuxcare.com.au>
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


#include "config.h"

#include <assert.h>
#include <stdlib.h>
#include <stdio.h>

#include "hsync.h"
#include "command.h"

/* For debugging purposes, here are some human-readable forms. */
struct hs_op_kind_name const _hs_op_kind_names[] = {
    {"EOF",       HS_KIND_EOF },
    {"COPY",      HS_KIND_COPY },
    {"LITERAL",   HS_KIND_LITERAL },
    {"SIGNATURE", HS_KIND_SIGNATURE },
    {"CHECKSUM",  HS_KIND_CHECKSUM },
    {"INVALID",   HS_KIND_INVALID },
    {NULL,        0 }
};


/*
 * Return a human-readable name for KIND.
 */
char const * _hs_op_kind_name(enum hs_op_kind kind)
{
        const struct hs_op_kind_name *k;

        for (k = _hs_op_kind_names; k->kind; k++) {
                if (k->kind == kind) {
                        return k->name;
                }
        }

        return NULL;
}


