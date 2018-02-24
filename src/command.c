/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- the library for network deltas
 *
 * Copyright (C) 2000 by Martin Pool <mbp@sourcefrog.net>
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

#include "librsync.h"
#include "command.h"

/* For debugging purposes, here are some human-readable forms. */
struct rs_op_kind_name const rs_op_kind_names[] = {
    {"END", RS_KIND_END},
    {"COPY", RS_KIND_COPY},
    {"LITERAL", RS_KIND_LITERAL},
    {"SIGNATURE", RS_KIND_SIGNATURE},
    {"CHECKSUM", RS_KIND_CHECKSUM},
    {"INVALID", RS_KIND_INVALID},
    {NULL, 0}
};

/** Return a human-readable name for KIND. */
char const *rs_op_kind_name(enum rs_op_kind kind)
{
    const struct rs_op_kind_name *k;

    for (k = rs_op_kind_names; k->kind; k++) {
        if (k->kind == kind) {
            return k->name;
        }
    }

    return NULL;
}
