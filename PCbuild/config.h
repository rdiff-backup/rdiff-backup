/* config.h.  Generated automatically by configure.  */
/* config.h.in.  Generated automatically from configure.in by autoheader.  */
/* acconfig.h -- hand-written definitions to eventually go into config.h */

/* Define this to enable trace code */
#define DO_RS_TRACE 1

/* Version of the libtool interface. */
#define RS_LIBVERSION "2:0:0"

/* Define this if your sockaddr structure contains sin_len */
/* #undef HAVE_SOCK_SIN_LEN */

/* Define this if there is a connect(2) call */
/* #undef HAVE_CONNECT */

/* Define if we have an off64_t largefile type */
/* #undef HAVE_OFF64_T */

/* Ask for large file support (LFS).  Should always be on, even if it
 * achieves nothing. */
/* #undef _LARGEFILE_SOURCE */
/* #undef _LARGEFILE64_SOURCE */

/* How many bits would you like to have in an off_t? */
/* #undef _FILE_OFFSET_BITS */

/* Define to include GNU C library extensions. */
#define _GNU_SOURCE 1

/* Define to get i18n support */
/* #undef ENABLE_NLS */

/* Define if you want the suboptimal X/Open catgets implementation */
/* #undef HAVE_CATGETS */

/* Define if you want the nice new GNU and Uniforum gettext system */
/* #undef HAVE_GETTEXT */

/* Define if your system has the LC_MESSAGES locale category */
/* #undef HAVE_LC_MESSAGES */

/* Define if you have stpcpy (copy a string and return a pointer to
 * the end of the result.) */
/* #undef HAVE_STPCPY */

/* GNU extension of saving argv[0] to program_invocation_short_name */
/* #undef HAVE_PROGRAM_INVOCATION_NAME */

/* Canonical GNU hostname */
#define RS_CANONICAL_HOST "i386-pc-windows32-msvcrt"

/* Define to a replacement type if intmax_t is not a builtin, or in
   sys/types.h or stdlib.h or stddef.h */
#define intmax_t long

/* end of acconfig.h */

/* Define if you have the <alloca.h> header file. */
/* #undef HAVE_ALLOCA_H */

/* Define if you have the <bzlib.h> header file. */
/* #undef HAVE_BZLIB_H */

/* Define if you have the <config.h> header file. */
/* #undef HAVE_CONFIG_H */

/* Define if you have the <dlfcn.h> header file. */
/* #undef HAVE_DLFCN_H */

/* Define if you have the <inttypes.h> header file. */
/* #undef HAVE_INTTYPES_H */

/* Define if you have the `bz2' library (-lbz2). */
/* #undef HAVE_LIBBZ2 */

/* Define if you have the <libintl.h> header file. */
/* #undef HAVE_LIBINTL_H */

/* Define if you have the `popt' library (-lpopt). */
/* #undef HAVE_LIBPOPT */

/* Define if you have the `z' library (-lz). */
/* #undef HAVE_LIBZ */

/* Define if you have the <mcheck.h> header file. */
/* #undef HAVE_MCHECK_H */

/* Define if you have the <memory.h> header file. */
#define HAVE_MEMORY_H 1

/* Define if you have the `mtrace' function. */
/* #undef HAVE_MTRACE */

/* Define if you have the `snprintf' function. */
/* #undef HAVE_SNPRINTF */

/* Define if you have the <stdint.h> header file. */
/* #undef HAVE_STDINT_H */

/* Define if you have the <stdlib.h> header file. */
#define HAVE_STDLIB_H 1

/* Define if you have the `strerror' function. */
#define HAVE_STRERROR 1

/* Define if you have the <strings.h> header file. */
/* #undef HAVE_STRINGS_H */

/* Define if you have the <string.h> header file. */
#define HAVE_STRING_H 1

/* Define if you have the <sys/stat.h> header file. */
#define HAVE_SYS_STAT_H 1

/* Define if you have the <sys/types.h> header file. */
#define HAVE_SYS_TYPES_H 1

/* Define if you have the <unistd.h> header file. */
/* #undef HAVE_UNISTD_H */

/* Define if you have the `vsnprintf' function. */
/* #undef HAVE_VSNPRINTF */

/* Define if you have the <zlib.h> header file. */
/* #undef HAVE_ZLIB_H */

/* Name of package */
#define PACKAGE "librsync"

/* The size of a `int', as computed by sizeof. */
#define SIZEOF_INT 4

/* The size of a `long', as computed by sizeof. */
#define SIZEOF_LONG 4

/* The size of a `long long', as computed by sizeof. */
#define SIZEOF_LONG_LONG 0

/* The size of a `off_t', as computed by sizeof. */
#define SIZEOF_OFF_T 4

/* The size of a `short', as computed by sizeof. */
#define SIZEOF_SHORT 2

/* The size of a `size_t', as computed by sizeof. */
#define SIZEOF_SIZE_T 4

/* The size of a `unsigned char', as computed by sizeof. */
#define SIZEOF_UNSIGNED_CHAR 1

/* The size of a `unsigned int', as computed by sizeof. */
#define SIZEOF_UNSIGNED_INT 4

/* The size of a `unsigned long', as computed by sizeof. */
#define SIZEOF_UNSIGNED_LONG 4

/* The size of a `unsigned short', as computed by sizeof. */
#define SIZEOF_UNSIGNED_SHORT 2

/* Define if you have the ANSI C header files. */
#define STDC_HEADERS 1

/* Version number of package */
#define VERSION "0.9.5"

/* Number of bits in a file offset, on hosts where this is settable. */
/* #undef _FILE_OFFSET_BITS */

/* Define to make ftello visible on some hosts (e.g. HP-UX 10.20). */
/* #undef _LARGEFILE_SOURCE */

/* Define for large files, on AIX-style hosts. */
/* #undef _LARGE_FILES */

/* Define to make ftello visible on some hosts (e.g. glibc 2.1.3). */
/* #undef _XOPEN_SOURCE */

/* Define to empty if `const' does not conform to ANSI C. */
/* #undef const */

/* Define to `long' if <sys/types.h> does not define. */
/* #undef off_t */

/* Define to `unsigned' if <sys/types.h> does not define. */
/* #undef size_t */
