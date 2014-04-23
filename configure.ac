#                                               -*- Autoconf -*-
# Process this file with autoconf to produce a configure script.

AC_PREREQ(2.53)
AC_INIT([librsync],[0.9.8pre])
AC_COPYRIGHT([Copyright (C) 1999-2014 by Martin Pool <mbp@sourcefrog.net>])
AC_CONFIG_SRCDIR([trace.c])
AM_CONFIG_HEADER(config.h)
AC_CONFIG_MACRO_DIR([m4])
AM_INIT_AUTOMAKE([foreign])

# GNU library versioning: This is NOT the librsync release number.
# See libversions.txt and the libtool manual for an explanation of the
# library versioning
librsync_libversion=1:2:0

# Disable shared libs by default.
AC_DISABLE_SHARED

# Checks for programs.
AC_GNU_SOURCE
AC_PROG_CC
AC_ISC_POSIX
AC_PROG_CPP
AC_PROG_INSTALL
AC_PROG_MAKE_SET
AC_PROG_LIBTOOL

# Checks for libraries.
AC_CHECK_LIB(z, deflate)
AC_CHECK_LIB(bz2, BZ2_bzCompress)
AC_CHECK_LIB(popt, poptGetContext, [], AC_MSG_WARN([cannot find libpopt: won't be able to run tests or build rdiff]))

# Checks for header files.
AC_FUNC_ALLOCA
AC_HEADER_STDC
AC_CHECK_HEADERS([mcheck.h bzlib.h zlib.h])
AC_CHECK_HEADERS([fcntl.h inttypes.h libintl.h limits.h malloc.h stdint.h stdlib.h string.h sys/file.h unistd.h])

# Checks for typedefs, structures, and compiler characteristics.
AC_C_CONST
AC_C_BIGENDIAN
AC_TYPE_SIZE_T
AC_TYPE_OFF_T
AC_SYS_LARGEFILE

AC_CHECK_SIZEOF([unsigned char], 1)
if test "$ac_cv_sizeof_unsigned_char" -ne 1; then
  AC_MSG_WARN(unsigned char seems to be $ac_cv_sizeof_unsigned_char bytes.  Expect trouble.)
fi
AC_CHECK_SIZEOF(short)
AC_CHECK_SIZEOF([unsigned short])
AC_CHECK_SIZEOF(int)
AC_CHECK_SIZEOF([unsigned int])
AC_CHECK_SIZEOF(long)
AC_CHECK_SIZEOF([unsigned long])
AC_CHECK_SIZEOF([long long])
AC_CHECK_SIZEOF(off_t)
AC_CHECK_SIZEOF(size_t)

#XXX: is this really the best way to do it? I think the limitation on
# rs_long_t is that we need to be able to seek to it, which relates to
# long file support. With fseeko, rs_long_t should be off_t, otherwise 
# it should be long.
AC_COMPILE_IFELSE([AC_LANG_PROGRAM(
  [[#include <sys/types.h>
#ifndef LONG_LONG
#error not defined
#endif]],
  [;])],
  [ RS_LONG_T='LONG_LONG' ],
  [ case "$ac_cv_sizeof_long_long" in
    0) RS_LONG_T='long' ;;
    *) RS_LONG_T='long long' ;;
    esac ])
AC_SUBST(RS_LONG_T)

# Checks for library functions.
#AC_FUNC_MALLOC      #XXX: needs malloc.c replacement  
#AC_FUNC_MEMCMP      #XXX: needs memcmp.c replacement
#AC_FUNC_REALLOC     #XXX: needs realloc.c replacement
AC_FUNC_FSEEKO
AC_CHECK_FUNCS([memmove memset strchr strerror strtol])
AC_CHECK_FUNCS([gettext dgettext])
AC_CHECK_FUNC(setreuid, [],
  [ AC_CHECK_LIB(ucb, setreuid, 
    [ if echo $LIBS | grep -- -lucb >/dev/null ;then :; 
      else LIBS="$LIBS -lc -lucb"; USEUCB=y;fi])
])
# supply a snprintf and vsnprintf if the system doesn't have one.
# if missing, check MSVC _xxx varients, otherwise use snprintf.c
# replacement.
AC_CHECK_FUNCS(snprintf,,[AC_CHECK_FUNCS(_snprintf)])
AC_CHECK_FUNCS(vsnprintf,,[AC_CHECK_FUNCS(_vsnprintf,,[AC_LIBOBJ(snprintf)])])

# Test if the compiler has the GNU feature of putting argv[0] into a global
AC_MSG_CHECKING([for program_invocation_short_name])
AC_COMPILE_IFELSE([AC_LANG_PROGRAM(
  [[#include <errno.h>]],
  [[strlen(program_invocation_short_name)]])],
  [ AC_DEFINE(HAVE_PROGRAM_INVOCATION_NAME,,
      [GNU extension of saving argv[0] to program_invocation_short_name])
    AC_MSG_RESULT(yes) ],
  [ AC_MSG_RESULT(no) ])

# Test if the preprocessor understands vararg macros
AC_MSG_CHECKING([for vararg macro support])
AC_COMPILE_IFELSE([AC_LANG_PROGRAM(
  [#define func(a, b...) do {} while (0)],
  [func("a", "b", "c");func("a")])],
  [ AC_DEFINE(HAVE_VARARG_MACROS, , [Define if your cpp has vararg macros])
    AC_MSG_RESULT(yes) ],
  [ AC_MSG_RESULT(no) ])

if test "$GCC" = "yes"; then # GCC
  CFLAGS="-Wall -Wshadow -Wundef -Wwrite-strings -Wmissing-prototypes -Wmissing-declarations -Wstrict-prototypes -Wpointer-arith -Wcast-qual -Wcast-align $CFLAGS"
elif test "$CC" = "cl"; then # MSVC
  CFLAGS="-Z7 -Od -MD $CFLAGS"
fi
# TODO: Similar conditions for other known compilers.  For SUNWspro, use `-v'.

AC_ARG_ENABLE(ccmalloc,
  AC_HELP_STRING([--enable-ccmalloc],[use ccmalloc debugger (default no)]),
  [ LIBS="$LIBS -lccmalloc -ldl" ])

AC_ARG_ENABLE(trace,
  AC_HELP_STRING([--disable-trace],[turn off library tracing]),
  [enable_trace=$enableval],[enable_trace=yes])
if test "$enable_trace" = "yes"; then
  AC_DEFINE(DO_RS_TRACE,,[Define this to enable trace code])
fi

AC_DEFINE_UNQUOTED(RS_LIBVERSION, "$librsync_libversion",[Version of the libtool interface.])
AC_DEFINE_UNQUOTED(RS_CANONICAL_HOST, "$host",[Canonical GNU hostname])

AC_SUBST(librsync_libversion)
AC_SUBST(BUILD_POPT)

AC_CONFIG_FILES([ 
  Makefile 
  doc/Makefile 
  doc/Doxyfile 
  testsuite/Makefile
  librsync-config.h])
AC_OUTPUT
