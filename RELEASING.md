# Releasing

If you are making a new tarball release of librsync, follow this checklist:

* AUTHORS - make sure all significant authors are included.

* NEWS - make sure the top "Changes in X.Y.Z" is correct.

* THANKS - make sure the bottom "Contributors for X.Y.Z" is correct.

* configure.ac - make sure AC_INIT and librsync_libversion are right.

* libversions.txt - make sure libversion is added.

* librsync.spec - make sure version and URL are right.

* PCBuild/config.h,librsync-config.h - update using configure.msc
  using cygwin.

Do a complete configure and distcheck to ensure everything is properly
configured, built, and tested:

    $ ./autogen.sh [OPTIONS]
    $ ./configure
    $ make distcheck

