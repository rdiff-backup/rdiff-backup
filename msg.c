/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * libhsync -- the library for network deltas
 * $Id$
 * 
 * Copyright (C) 2000, 2001 by Martin Pool <mbp@samba.org>
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


                              /*
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

#include <config.h>

#include <stdlib.h>

#include "hsync.h"


/** \brief Translate from hs_result to human-readable messages. */
char const *hs_strerror(hs_result r)
{
    switch (r) {
    case HS_DONE:
        return "OK";
    case HS_RUNNING:
        return "still running";
    case HS_BAD_MAGIC:
        return "bad magic number at start of stream";
    case HS_BLOCKED:
        return "blocked waiting for input or output buffers";
    case HS_INPUT_ENDED:
        return "unexpected end of input";
    case HS_CORRUPT:
        return "stream corrupt";
    case HS_UNIMPLEMENTED:
        return "unimplemented case";
    case HS_MEM_ERROR:
        return "out of memory";
    case HS_IO_ERROR:
        return "IO error";
    case HS_SYNTAX_ERROR:
        return "command line syntax error";
    case HS_INTERNAL_ERROR:
        return "library internal error";
    default:
        return "unknown error";
    }
}
