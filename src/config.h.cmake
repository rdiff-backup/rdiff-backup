/* config.h.  Generated from config.h.in by configure.  */
/* config.h.in.  Generated from configure.ac by autoheader.  */

/* Define if building universal (internal helper macro) */
#cmakedefine AC_APPLE_UNIVERSAL_BUILD

/* Define to one of `_getb67', `GETB67', `getb67' for Cray-2 and Cray-YMP
   systems. This function is required for `alloca.c' support on those systems.
   */
#cmakedefine CRAY_STACKSEG_END

/* Define to 1 if using `alloca.c'. */
#cmakedefine C_ALLOCA 1

/* Define this to enable trace code  */
#cmakedefine DO_RS_TRACE

/* Define to 1 if you have `alloca', as a function or macro. */
#cmakedefine HAVE_ALLOCA 1

/* Define to 1 if you have <alloca.h> and it should be used (not on Ultrix). */
#cmakedefine HAVE_ALLOCA_H 1

/* Define to 1 if you have the <bzlib.h> header file.  */
#cmakedefine HAVE_BZLIB_H 1

/* Define to 1 if you have the <dlfcn.h> header file. */
#cmakedefine HAVE_DLFCN_H 1

/* Define to 1 if you have the <fcntl.h> header file. */
#cmakedefine HAVE_FCNTL_H 1

/* Define to 1 if fseeko (and presumably ftello) exists and is declared. */
#cmakedefine HAVE_FSEEKO 1

/* Define to 1 if fseeko64 (and presumably ftello64) exists and is declared. */
#cmakedefine HAVE_FSEEKO64 1

/* Define to 1 if _fseeki64 (and presumably _ftelli64) exists and is declared. */
#cmakedefine HAVE__FSEEKI64 1

/* Define to 1 if fstat64 exists and is declared. */
#cmakedefine HAVE_FSTAT64 1

/* Define to 1 if _fstati64 exists and is declared. */
#cmakedefine HAVE__FSTATI64 1

/* Define to 1 if fileno exists and is declared (Posix). */
#cmakedefine HAVE_FILENO 1

/* Define to 1 if _fileno exists and is declared (ISO C++). */
#cmakedefine HAVE__FILENO 1

/* Define to 1 if you have the <inttypes.h> header file. */
#cmakedefine HAVE_INTTYPES_H 1

/* Define to 1 if you have the `bz2' library (-lbz2). */
#cmakedefine HAVE_LIBBZ2 ${BZIP2_FOUND}

/* Define to 1 if you have the `popt' library (-lpopt). */
#cmakedefine HAVE_LIBPOPT ${POPT_FOUND}

/* Define to 1 if you have the `z' library (-lz). */
#cmakedefine HAVE_LIBZ ${ZLIB_FOUND}

/* Define to 1 if you have the <malloc.h> header file. */
#cmakedefine HAVE_MALLOC_H 1

/* Define to 1 if you have the <mcheck.h> header file. */
#cmakedefine HAVE_MCHECK_H 1

/* Define to 1 if you have the `memmove' function. */
#cmakedefine HAVE_MEMMOVE 1

/* Define to 1 if you have the <memory.h> header file. */
#cmakedefine HAVE_MEMORY_H 1

/* Define to 1 if you have the `memset' function. */
#cmakedefine HAVE_MEMSET 1

/* GNU extension of saving argv[0] to program_invocation_short_name */
#cmakedefine HAVE_PROGRAM_INVOCATION_NAME

/* Define to 1 if you have the `snprintf' function. */
#cmakedefine HAVE_SNPRINTF 1

/* Define to 1 if you have the <stdint.h> header file. */
#cmakedefine HAVE_STDINT_H 1

/* Define to 1 if you have the <stdlib.h> header file. */
#cmakedefine HAVE_STDLIB_H 1

/* Define to 1 if you have the `strchr' function. */
#cmakedefine HAVE_STRCHR 1

/* Define to 1 if you have the `strerror' function. */
#cmakedefine HAVE_STRERROR 1

/* Define to 1 if you have the <strings.h> header file. */
#cmakedefine HAVE_STRINGS_H 1

/* Define to 1 if you have the <string.h> header file. */
#cmakedefine HAVE_STRING_H 1

/* Define to 1 if you have the <sys/file.h> header file. */
#cmakedefine HAVE_SYS_FILE_H 1

/* Define to 1 if you have the <sys/stat.h> header file. */
#cmakedefine HAVE_SYS_STAT_H 1

/* Define to 1 if you have the <sys/types.h> header file. */
#cmakedefine HAVE_SYS_TYPES_H 1

/* Define to 1 if you have the <unistd.h> header file. */
#cmakedefine HAVE_UNISTD_H 1

/* Define if your cpp has vararg macros */
#cmakedefine HAVE_VARARG_MACROS

/* Define to 1 if you have the `vsnprintf' function. */
#cmakedefine HAVE_VSNPRINTF 1

/* Define to 1 if you have the <zlib.h> header file. */
#cmakedefine HAVE_ZLIB_H 1

/* Define to 1 if you have the `_snprintf' function. */
#cmakedefine HAVE__SNPRINTF 1

/* Define to 1 if you have the `_vsnprintf' function. */
#cmakedefine HAVE__VSNPRINTF 1

/* Name of package */
#define PACKAGE "${PROJECT_NAME}"

/* The size of `long', as computed by sizeof. */
#cmakedefine SIZEOF_LONG ${SIZEOF_LONG}

/* The size of `long long', as computed by sizeof. */
#cmakedefine SIZEOF_LONG_LONG ${SIZEOF_LONG_LONG}

/* The size of `size_t', as computed by sizeof. */
#cmakedefine SIZEOF_SIZE_T ${SIZEOF_SIZE_T}

/* The size of `off_t', as computed by sizeof. */
#cmakedefine SIZEOF_OFF_T ${SIZEOF_OFF_T}

/* The size of `off64_t', as computed by sizeof. */
#cmakedefine SIZEOF_OFF64_T ${SIZEOF_OFF64_T}

/* The size of `unsigned int', as computed by sizeof. */
#cmakedefine SIZEOF_UNSIGNED_INT ${SIZEOF_UNSIGNED_INT}

/* The size of `unsigned long', as computed by sizeof. */
#cmakedefine SIZEOF_UNSIGNED_LONG ${SIZEOF_UNSIGNED_LONG}

/* The size of `unsigned short', as computed by sizeof. */
#cmakedefine SIZEOF_UNSIGNED_SHORT ${SIZEOF_UNSIGNED_SHORT}

/* Define to 1 if printf supports the size_t "%zu" length field. */
#cmakedefine HAVE_PRINTF_Z 1

/* If using the C implementation of alloca, define if you know the
   direction of stack growth for your system; otherwise it will be
   automatically deduced at runtime.
        STACK_DIRECTION > 0 => grows toward higher addresses
        STACK_DIRECTION < 0 => grows toward lower addresses
        STACK_DIRECTION = 0 => direction of growth unknown */
#cmakedefine STACK_DIRECTION

/* Define to 1 if you have the ANSI C header files. */
#cmakedefine STDC_HEADERS 1

/* FIXME Enable extensions on AIX 3, Interix.  */
#ifndef _ALL_SOURCE
# define _ALL_SOURCE 1
#endif
/* FIXME Enable GNU extensions on systems that have them.  */
#ifndef _GNU_SOURCE
# define _GNU_SOURCE 1
#endif
/* FIXME Enable threading extensions on Solaris.  */
#ifndef _POSIX_PTHREAD_SEMANTICS
# define _POSIX_PTHREAD_SEMANTICS 1
#endif
/* FIXME Enable extensions on HP NonStop.  */
#ifndef _TANDEM_SOURCE
# define _TANDEM_SOURCE 1
#endif
/* FIXME Enable general extensions on Solaris.  */
#ifndef __EXTENSIONS__
# define __EXTENSIONS__ 1
#endif


/* Version number of package */
#define VERSION "${LIBRSYNC_VERSION}"

/* Define WORDS_BIGENDIAN to 1 if your processor stores words with the most
   significant byte first (like Motorola and SPARC, unlike Intel). */
#cmakedefine WORDS_BIGENDIAN 1

/* FIXME Enable large inode numbers on Mac OS X 10.5.  */
#ifndef _DARWIN_USE_64_BIT_INODE
# define _DARWIN_USE_64_BIT_INODE 1
#endif

/* FIXME Number of bits in a file offset, on hosts where this is settable. */
/* #undef _FILE_OFFSET_BITS */

/* FIXME Define to 1 to make fseeko visible on some hosts (e.g. glibc 2.2). */
/* #undef _LARGEFILE_SOURCE */

/* FIXME Define for large files, on AIX-style hosts. */
/* #undef _LARGE_FILES */

/* FIXME Define to 1 if on MINIX. */
/* #undef _MINIX */

/* FIXME Define to 2 if the system does not provide POSIX.1 features except with
   this defined. */
/* #undef _POSIX_1_SOURCE */

/* FIXME Define to 1 if you need to in order for `stat' and other things to work. */
/* #undef _POSIX_SOURCE */

/* FIXME Define to empty if `const' does not conform to ANSI C. */
/* #undef const */

/* FIXME Define to `long int' if <sys/types.h> does not define. */
/* #undef off_t */

/* FIXME Define to `unsigned int' if <sys/types.h> does not define. */
/* #undef size_t */
