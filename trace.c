/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * libhsync -- library for network deltas
 *
 * Copyright (C) 2000, 2001 by Martin Pool <mbp@samba.org>
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

                                     /*
                                      | Finality is death.
                                      | Perfection is finality.
                                      | Nothing is perfect.
                                      | There are lumps in it.
                                      */

#include <config.h>

#include <unistd.h>
#include <stdio.h>
#include <sys/file.h>
#include <string.h>
#include <errno.h>
#include <stdlib.h>
#include <assert.h>
#include <stdint.h>
#include <stdarg.h>

#include "hsync.h"
#include "util.h"
#include "trace.h"


hs_trace_fn_t  *hs_trace_impl = hs_trace_stderr;

static int hs_trace_level = HS_LOG_INFO;

#ifdef HAVE_PROGRAM_INVOCATION_NAME
#  define MY_NAME program_invocation_short_name
#else
#  define MY_NAME "libhsync"
#endif

static void hs_log_va(int level, char const *fn, char const *fmt, va_list va);


/**
 * Log severity strings, if any.  Must match ordering in
 * ::hs_loglevel.
 */
static const char *hs_severities[] = {
    "EMERGENCY! ", "ALERT! ", "CRITICAL! ", "ERROR: ", "Warning: ",
    "", "", ""
};

/**
 * \brief Return the appropriate shell exit value for an internal
 * result code.
 */
hs_exit_value hs_result_to_exit(hs_result r)
{
    switch (r) {
    case HS_OK:
        return HS_EXIT_OK;
    default:
        return HS_EXIT_INTERNAL;
    }
}


/**
 * \brief Set the destination of trace information.
 *
 * The callback scheme allows for use within applications that may
 * have their own particular ways of reporting errors: log files for a
 * web server, perhaps, and an error dialog for a browser.
 *
 * \todo Do we really need such fine-grained control, or just yes/no
 * tracing?
 */
void
hs_trace_to(hs_trace_fn_t * new_impl)
{
    hs_trace_impl = new_impl;
}


/** 
 * Set the least important message severity that will be output.
 */
void
hs_trace_set_level(hs_loglevel level)
{
    hs_trace_level = level;
}


static void
hs_log_va(int level, char const *fn, char const *fmt, va_list va)
{
    if (hs_trace_impl && level <= hs_trace_level) {
        char            buf[1000];
        char            full_buf[1000];

        vsnprintf(buf, sizeof buf - 1, fmt, va);

        snprintf(full_buf, sizeof full_buf - 1,
                 "%s: %s%s: %s\n",
                 MY_NAME, hs_severities[level], fn, buf);

	hs_trace_impl(level, full_buf);
    }
}



/* Called by a macro that prepends the calling function name,
 * etc.  */
void
hs_log0(int level, char const *fn, char const *fmt, ...)
{
    va_list         va;

    va_start(va, fmt);
    hs_log_va(level, fn, fmt, va);
    va_end(va);
}


void
hs_trace_stderr(int UNUSED(level), char const *msg)
{
    /* NOTE NO TRAILING NUL */
    write(STDERR_FILENO, msg, strlen(msg));
}


/* This is called directly if the machine doesn't allow varargs
 * macros. */
void
hs_fatal0(char const *s, ...) 
{
    va_list	va;

    va_start(va, s);
    hs_log_va(HS_LOG_CRIT, PACKAGE, s, va);
    va_end(va);
}


/* This is called directly if the machine doesn't allow varargs
 * macros. */
void
hs_error0(char const *s, ...) 
{
    va_list	va;

    va_start(va, s);
    hs_log_va(HS_LOG_ERR, PACKAGE, s, va);
    va_end(va);
}


/* This is called directly if the machine doesn't allow varargs
 * macros. */
void
hs_trace0(char const *s, ...) 
{
    va_list	va;

    va_start(va, s);
    hs_log_va(HS_LOG_DEBUG, PACKAGE, s, va);
    va_end(va);
}


/**
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
