AC_DEFUN(SAMBA_TYPE_OFF64_T, [
AC_CACHE_CHECK([for off64_t],samba_cv_HAVE_OFF64_T,[
AC_TRY_RUN([
#if defined(HAVE_UNISTD_H)
#include <unistd.h>
#endif
#include <stdio.h>
#include <sys/stat.h>
main() { struct stat64 st; off64_t s; if (sizeof(off_t) == sizeof(off64_t)) exit(1); exit((lstat64("/dev/null", &st)==0)?0:1); }],
samba_cv_HAVE_OFF64_T=yes,samba_cv_HAVE_OFF64_T=no,samba_cv_HAVE_OFF64_T=cross)])
if test x"$samba_cv_HAVE_OFF64_T" = x"yes"; then
    AC_DEFINE(HAVE_OFF64_T)
fi

])