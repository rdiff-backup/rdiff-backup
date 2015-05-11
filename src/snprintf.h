/* $Id$ */

/* Some platforms don't have one or both of these functions.
 * MSVC has _snprintf and _vsnprintf functions instead.
 * 
 * XXX: put this into a "common.h" for all platform conditionals and split
 * snprintf.c into two seperate autoconf replacement functions.
 */
#ifndef HAVE_SNPRINTF
#  ifdef HAVE__SNPRINTF
#    define snprintf _snprintf
#  else
int snprintf (char *str, size_t count, const char *fmt, ...);
#  endif
#endif
#ifndef HAVE_VSNPRINTF
#  ifdef HAVE__VSNPRINTF
#    define vsnprintf _vsnprintf
#  else
int vsnprintf (char *str, size_t count, const char *fmt, va_list arg);
#  endif
#endif
