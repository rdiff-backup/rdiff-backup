/*				       	-*- c-file-style: "linux" -*-
 *
 * libhsync -- generate and apply network deltas
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool <mbp@linuxcare.com.au>
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
 * TODO: A function like perror that includes strerror output.  Apache
 * does this by adding flags as well as the severity level which say
 * whether such information should be included.
 */


/*
 * trace may be turned off.
 *
 * error is always on, but you can return and continue in some way
 *
 * fatal terminates the whole process
 */

void _hs_fatal0(char const *s, ...);
void _hs_error0(char const *s, ...);
void _hs_trace0(char const *s, ...);

#ifdef __GNUC__

void _hs_log0(int level, char const *fn, char const *fmt, ...)
    __attribute__ ((format(printf, 3, 4)));

#ifdef DO_HS_TRACE
#  define _hs_trace(fmt, arg...)                                \
    do { _hs_log0(LOG_DEBUG, __FUNCTION__, fmt , ##arg);  \
    } while (0)
#else
#  define _hs_trace(s, str...)
#endif	/* !DO_HS_TRACE */

/*
 * TODO: Don't assume this is a gcc thing; rather test in autoconf for
 * support for __FUNCTION__ and varargs macros.  One simple way might
 * just be to try compiling the definition of one of these functions!
 *
 * TODO: Also look for the C9X predefined identifier `_function', or
 * whatever it's called.
 */

#define _hs_log(l, s, str...) do {              \
     _hs_log0(l, __FUNCTION__, (s) , ##str);    \
     } while (0)


#define _hs_error(s, str...) do {                       \
     _hs_log0(LOG_ERR,  __FUNCTION__, (s) , ##str);     \
     } while (0)


#define _hs_fatal(s, str...) do {               \
     _hs_log0(LOG_CRIT,  __FUNCTION__,          \
	      (s) , ##str);                     \
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



/* Log levels (same as syslog) */
#define	LOG_EMERG	0	/* system is unusable */
#define	LOG_ALERT	1	/* action must be taken immediately */
#define	LOG_CRIT	2	/* critical conditions */
#define	LOG_ERR		3	/* error conditions */
#define	LOG_WARNING	4	/* warning conditions */
#define	LOG_NOTICE	5	/* normal but significant condition */
#define	LOG_INFO	6	/* informational */
#define	LOG_DEBUG	7	/* debug-level messages */

#define	LOG_PRIMASK	0x07	/* mask to extract priority part (internal) */
				/* extract priority */
