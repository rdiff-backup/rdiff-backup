/*				       	-*- c-file-style: "bsd" -*-
 * rproxy -- dynamic caching and delta update in HTTP
 * $Id$
 *
 * Copyright (C) 2000 by Martin Pool <mbp@linuxcare.com>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU Lesser General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
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

                                     /*
                                      | Finality is death.
                                      | Perfection is finality.
                                      | Nothing is perfect.
                                      | There are lumps in it.
                                      */

#include "includes.h"

#include <unistd.h>
#include <stdio.h>
#include <sys/file.h>
#include <string.h>

char const * const hs_libhsync_version = PACKAGE " " VERSION;
char const * const hs_libhsync_libversion = HS_LIBVERSION;
int const hs_libhsync_file_offset_bits = SIZEOF_OFF_T * 8;

hs_trace_fn_t  *_hs_trace_impl = hs_trace_to_stderr;

static int _hs_trace_level = LOG_INFO;


/* Called by the application to set the destination of trace * information. */
void
hs_trace_to(hs_trace_fn_t * new_impl)
{
    _hs_trace_impl = new_impl;
}


/* Set the least import message severity that will be output. */
void
hs_trace_set_level(int level)
{
    _hs_trace_level = level;
}


void
_hs_log_va(int level, char const *fn, char const *fmt, va_list va)
{
    if (_hs_trace_impl && level <= _hs_trace_level) {
        char            buf[1000];
        char            full_buf[1000];

	/* TODO: Use our own vsnprintf if necessary.  Sigh. */
#ifdef have_vsnprintf
        vsnprintf(buf, sizeof buf - 1, fmt, va);
#else
	vsprintf(buf, fmt, va);
#endif

#ifdef __GNUC__
#ifdef HAVE_SNPRINTF
        snprintf(full_buf, sizeof full_buf - 1,
                  "%s: %s: %s\n",
                  program_invocation_short_name,
                  fn,
                  buf);
#else
	/* TODO: test explicitly for program_invocation_short_name */
	sprintf(full_buf, "%s: %s: %s\n",
		"(libhsync)", 
		fn,
		buf);
#endif /* HAVE_SPRINTF */
#else
        snprintf(full_buf, sizeof full_buf - 1,
                  "%s: %s\n",
                  PACKAGE, 
                  buf);
#endif

	_hs_trace_impl(level, full_buf);
    }
}



/* This function is called by a macro that prepends the calling function
 * name, etc.  */
void
_hs_log0(int level, char const *fn, char const *fmt, ...)
{
    va_list         va;

    va_start(va, fmt);
    _hs_log_va(level, fn, fmt, va);
    va_end(va);
}


void
hs_trace_to_stderr(int UNUSED(level), char const *msg)
{
    /* NOTE NO TRAILING NUL */
    write(STDERR_FILENO, msg, strlen(msg));
}


/* This is called directly if the machine doesn't allow varargs
 * macros. */
void
_hs_fatal0(char const *s, ...) 
{
    va_list	va;

    va_start(va, s);
    _hs_log_va(LOG_CRIT, PACKAGE, s, va);
    va_end(va);
}


/* This is called directly if the machine doesn't allow varargs
 * macros. */
void
_hs_error0(char const *s, ...) 
{
    va_list	va;

    va_start(va, s);
    _hs_log_va(LOG_ERR, PACKAGE, s, va);
    va_end(va);
}


/* This is called directly if the machine doesn't allow varargs
 * macros. */
void
_hs_trace0(char const *s, ...) 
{
    va_list	va;

    va_start(va, s);
    _hs_log_va(LOG_DEBUG, PACKAGE, s, va);
    va_end(va);
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
