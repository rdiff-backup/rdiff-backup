/* acconfig.h -- hand-written definitions to eventually go into config.h */

/* Define this to enable trace code */
#undef DO_RS_TRACE

/* Version of the libtool interface. */
#define RS_LIBVERSION "unknown"

/* Define this if your sockaddr structure contains sin_len */
#undef HAVE_SOCK_SIN_LEN

/* Define this if there is a connect(2) call */
#undef HAVE_CONNECT

/* Define if we have an off64_t largefile type */
#undef HAVE_OFF64_T

/* Ask for large file support (LFS).  Should always be on, even if it
 * achieves nothing. */
#undef _LARGEFILE_SOURCE
#undef _LARGEFILE64_SOURCE

/* How many bits would you like to have in an off_t? */
#undef _FILE_OFFSET_BITS

/* Define to include GNU C library extensions. */
#undef _GNU_SOURCE

/* Define to get i18n support */
#undef ENABLE_NLS

/* Define if you want the suboptimal X/Open catgets implementation */
#undef HAVE_CATGETS

/* Define if you want the nice new GNU and Uniforum gettext system */
#undef HAVE_GETTEXT

/* Define if your system has the LC_MESSAGES locale category */
#undef HAVE_LC_MESSAGES

/* Define if you have stpcpy (copy a string and return a pointer to
 * the end of the result.) */
#undef HAVE_STPCPY

/* GNU extension of saving argv[0] to program_invocation_short_name */
#undef HAVE_PROGRAM_INVOCATION_NAME

/* Canonical GNU hostname */
#define RS_CANONICAL_HOST "unknown"

/* Define to a replacement type if intmax_t is not a builtin, or in
   sys/types.h or stdlib.h or stddef.h */
#undef intmax_t

/* end of acconfig.h */
