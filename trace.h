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


/* TODO: A function like perror that includes strerror output. */

void _hs_fatal0(char const *s, ...);
void _hs_error0(char const *s, ...);
void _hs_trace0(char const *s, ...);


#ifdef __GNUC__

void _hs_log0(int level, char const *fmt, ...) __attribute__ ((format(printf, 2, 3)));

#ifdef DO_HS_TRACE
#  define _hs_trace(fmt, arg...)                                \
    do { _hs_log0(LOG_DEBUG, __FUNCTION__ ": " fmt , ##arg);  \
    } while (0)
#else
#  define _hs_trace(s, str...)
#endif	/* !DO_HS_TRACE */


extern char const *program_invocation_short_name;

/* TODO: Don't assume this is a gcc thing; rather test in autoconf for
 * the presence of __FUNCTION__. */

#define _hs_log(l, s, str...) do {              \
     _hs_log0(l, __FUNCTION__ ": " s          \
                , ##str);                       \
     } while (0)


#define _hs_error(s, str...) do {               \
     _hs_log0(LOG_ERR, __FUNCTION__ ": " s    \
                , ##str);                       \
     } while (0)


#define _hs_fatal(s, str...) do {               \
     _hs_log0(LOG_CRIT,                       \
	      __FUNCTION__ ": " s               \
	      , ##str);                         \
     abort();                                   \
     } while (0)


#else /************************* ! __GNUC__ */

#  define _hs_fatal _hs_fatal0
#  define _hs_error _hs_error0

#  ifdef DO_HS_TRACE
#    define _hs_trace _hs_trace0
void            _hs_log0(int, char const *, ...);
#  endif			/* DO_HS_TRACE */
#endif				/* ! __GNUC__ */

