# librsync

librsync implements the rolling-checksum algorithm of remote file
synchronization that was popularized by the rsync utility and is used in
rproxy. This algorithm transfers the differences between 2 files without
needing both files on the same system.

librsync does *not* implement the rsync wire protocol. If you want to talk to
an rsync server to transfer files you'll need to shell out to `rsync`. librsync
is for building other programs that transfer files as efficiently as rsync. You
can use librsync to make backup tools, distribute binary patches to programs,
or sync directories to a server or between peers.

This tree also produces the `rdiff` command-line tool that exposes the key
operations of librsync: generating file signatures, generating the delta from a
signature to a new file, and applying the delta to regenerate the new file
given the old file.

## Copyright

librsync is Copyright 1999-2014 Martin Pool and others.

librsync is distributed under the GNU LGPL v2.1 (see COPYING), which basically
means that you can dynamically link librsync into non-GPL programs, but you
must redistribute the librsync source, with any modifications you have made.

## Contact

librsync's home is

- https://github.com/librsync/librsync/
- http://librsync.sourcefrog.net/

There are two mailing lists:

- https://groups.google.com/forum/#!forum/librsync-announce
- https://groups.google.com/forum/#!forum/librsync

There are some questions and answers about librsync on stackoverflow.com tagged
`librsync`.  That is a good place to start if you have questions.

## Requirements

To build librsync you will need:

* A C compiler and appropriate headers and libraries

* Make

* popt command line parsing library

  Available from http://rpm5.org/files/popt/

* automake, libtool, and autoconf

## Compiling

If you're building from a git tree you must first create the autoconf files:

    $ ./autogen.sh

To build and test librsync then do

    $ ./configure
    $ make all check

You can also do what's called a `VPATH` build, where the build products are
kept separate from the source tree:

    $ mkdir _build   # for example
    $ cd _build
    $ ../configure && make check

After building you can install `rdiff` and `librsync` for system-wide use. The
destination is controlled by `--prefix` and related options to `./configure`.

    $ sudo make install

## Note for Windows

With cygwin you can build using gcc as under a normal unix system. It
is also possible to compile under cygwin using MSVC++. You must have
environment variables needed by MSCV set using the Vcvars32.bat
script. With these variables set, you just do;

    $ ./configure.msc
    $ make all check

The PCbuild directory contains a project and pre-generated config
files for use with the MSVC++ IDE. This should be enought to compile
rdiff.exe without requiring cygwin.

## Library Versions

librsync uses the GNU libtool library versioning system, so the filename
does not correspond to the librsync release.  To show the library release
and version, use the librsyncinfo tool. See libversions.txt for more
information.

## Platforms

librsync should be widely portable. Patches to fix portability bugs are
welcome.

## Documentation

Documentation for the rdiff command-line tool:

- http://librsync.sourcefrog.net/doc/rdiff.html
- http://librsync.sourcefrog.net/doc/rdiff.pdf

and for the library:

- http://librsync.sourcefrog.net/doc/librsync.html
- http://librsync.sourcefrog.net/doc/librsync.pdf

Generated API documentation:

- https://rproxy.samba.org/doxygen/librsync/
- https://rproxy.samba.org/doxygen/librsync/refman.pdf

These are all produced from the source tree.

## Debugging

If you are using GNU libc, you might like to use

    MALLOC_CHECK_=2 ./rdiff

to detect some allocation bugs.

librsync has annotations for the SPLINT static checking tool.
