/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 * librsync -- dynamic caching and delta update in HTTP
 * $Id$
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

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

#include "isprefix.h"

/*
 * Test driver for isprefix.
 */
int main(int argc, char **argv)
{
    assert(isprefix("foo", "foobar"));
    assert(isprefix("", "foobar"));
    assert(isprefix("foobar", "foobar"));
    assert(isprefix("", ""));
    assert(isprefix("f", "foorbar"));

    assert(!isprefix("foobar", "foo"));
    assert(!isprefix("goo", "foo"));
    assert(!isprefix("foo", ""));
    assert(!isprefix("f", "g"));
}
