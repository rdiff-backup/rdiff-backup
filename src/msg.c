/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- the library for network deltas
 *
 * Copyright (C) 2000, 2001 by Martin Pool <mbp@sourcefrog.net>
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

                              /*=
                               | Welcome to Arco AM/PM Mini-Market. We
                               | would like to advise our customers
                               | that any individual who offers to
                               | pump gas, wash windows or solicit
                               | products is not employed by or
                               | associated with this facility.  We
                               | discourage any contact with these
                               | individuals and ask that you report
                               | any problems to uniformed personal
                               | inside. Thankyou for shopping at
                               | Arco, and have a nice day.
                               */

/** \file msg.c error messages for re_result values.
 *
 * \todo (Suggestion by tridge) Add a function which outputs a complete text
 * description of a job, including only the fields relevant to the current
 * encoding function. */

#include "config.h"

#include <stdlib.h>
#include <stdio.h>

#include "librsync.h"

char const *rs_strerror(rs_result r)
{
    switch (r) {
    case RS_DONE:
        return "OK";
    case RS_RUNNING:
        return "still running";
    case RS_BLOCKED:
        return "blocked waiting for input or output buffers";
    case RS_BAD_MAGIC:
        return "bad magic number at start of stream";
    case RS_INPUT_ENDED:
        return "unexpected end of input";
    case RS_CORRUPT:
        return "stream corrupt";
    case RS_UNIMPLEMENTED:
        return "unimplemented case";
    case RS_MEM_ERROR:
        return "out of memory";
    case RS_IO_ERROR:
        return "IO error";
    case RS_SYNTAX_ERROR:
        return "bad command line syntax";
    case RS_INTERNAL_ERROR:
        return "library internal error";

    default:
        return "unexplained problem";
    }
}
