/* -*- c-file-style: "bsd" -*- * * $Id: trace.c,v 1.12 2000/05/21 12:53:21
   mbp Exp $ * * Copyright (C) 2000 by Martin Pool * * This program is free 
   software; you can redistribute it and/or modify * it under the terms of
   the GNU General Public License as published by * the Free Software
   Foundation; either version 2 of the License, or * (at your option) any
   later version. * * This program is distributed in the hope that it will
   be useful, * but WITHOUT ANY WARRANTY; without even the implied warranty
   of * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the * GNU
   General Public License for more details. * * You should have received a
   copy of the GNU General Public License * along with this program; if not,
   write to the Free Software * Foundation, Inc., 675 Mass Ave, Cambridge, MA 
   02139, USA. */


#include "includes.h"

char const     *const hs_libhsync_version = PACKAGE " " VERSION;

hs_trace_fn_t  *_hs_trace_impl = hs_trace_to_stderr;


/* Called by the application to set the destination of trace * information. */
void
hs_trace_to(hs_trace_fn_t * new_impl)
{
    _hs_trace_impl = new_impl;
}


/* This function is called by a macro that switches it depending on * the
   compile-time setting, etc.  */
void
_hs_trace0(char const *fmt, ...)
{
    va_list         va;

    if (_hs_trace_impl) {
	va_start(va, fmt);
	_hs_trace_impl(fmt, va);
	va_end(va);
    }
}


void
hs_trace_to_stderr(char const *fmt, va_list va)
{
    char            buf[1000];
    int             n;

    n = 0;
    buf[n++] = '\t';
    vsnprintf(buf + n, sizeof buf - 1, fmt, va);
    n = strlen(buf);
    buf[n++] = '\n';

    /* NOTE NO TRAILING NUL */
    write(STDERR_FILENO, buf, n);
}


/* 
 * Return true if the library contains trace code; otherwise false.
 * If this returns false, then trying to turn trace on will achieve
 * nothing.
 */
int
hs_supports_trace(void)
{
#ifdef DO_HS_TRACE
    return 1;
#else
    return 0;
#endif				/* !DO_HS_TRACE */
}
