/*				       	-*- c-file-style: "bsd" -*-
 * rproxy -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool
 * 
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */


/* TODO: A function like perror */


#ifdef __GNUC__

void
                _hs_trace0(char const *fmt, ...)
    __attribute__ ((format(printf, 1, 2)));

void            _hs_trace0(char const *fmt, ...)
    __attribute__ ((format(printf, 1, 2)));

#ifdef DO_HS_TRACE
#    define _hs_trace(fmt, arg...)			\
    do { _hs_trace0(__FUNCTION__ ": " fmt, ##arg);	\
    } while (0)
#endif	/* DO_HS_TRACE */

#define return_val_if_fail(expr, val) if (!(expr))	\
  { fprintf(stderr, "%s(%d): %s: assertion failed\n",	\
    __FILE__, __LINE__, __FUNCTION__); return (val); }

extern char const *program_invocation_short_name;

#  define _hs_fatal(s, str...) do { fprintf (stderr,	\
    "%s: " __FUNCTION__ ": "				\
    s "\n" , program_invocation_short_name ,		\
    ##str); abort(); } while(0)

#define _hs_error(s, str...) do {			\
      fprintf(stderr,					\
	     "%s: " __FUNCTION__ ": " s "\n" ,		\
	     program_invocation_short_name , ##str);	\
     } while (0)

#  else				/* ! __GNUC__ */

#  define _hs_fatal(s, str...) do { fprintf (stderr,    \
    "libhsync: " s "\n" , ##str); abort(); } while(0)

#  define _hs_error(s, str...) do { fprintf (stderr,    \
    "libhsync: " s "\n" , ##str); } while(0)

#  ifdef DO_HS_TRACE
#    define _hs_trace _hs_trace0
void            _hs_trace0(char const *, ...);
#  endif			/* DO_HS_TRACE */
#endif				/* ! __GNUC__ */

#ifndef DO_HS_TRACE
#  define _hs_trace(s, str...)
#endif				/* ! DO_HS_TRACE */
