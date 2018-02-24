/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- the library for network deltas
 *
 * Copyright (C) 2000, 2001 by Martin Pool <mbp@sourcefrog.net>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU Lesser General Public License as published by
 * the Free Software Foundation; either version 2.1 of the License, or
 * (at your option) any later version.
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

                                /*=
                                 | On heroin, I have all the answers.
                                 */

#include "config.h"
#include <stdlib.h>
#include <string.h>

#include "librsync.h"
#include "util.h"
#include "trace.h"

void rs_bzero(void *buf, size_t size)
{
    memset(buf, 0, size);
}

void *rs_alloc_struct0(size_t size, char const *name)
{
    void *p;

    if (!(p = malloc(size))) {
        rs_fatal("couldn't allocate instance of %s", name);
    }
    rs_bzero(p, size);
    return p;
}

void *rs_alloc(size_t size, char const *name)
{
    void *p;

    if (!(p = malloc(size))) {
        rs_fatal("couldn't allocate instance of %s", name);
    }

    return p;
}

void *rs_realloc(void *ptr, size_t size, char const *name)
{
    void *p;

    if (!(p = realloc(ptr, size))) {
        rs_fatal("couldn't reallocate instance of %s", name);
    }
    return p;
}
