# librsync

[![Build Status](https://travis-ci.org/librsync/librsync.svg?branch=master)](https://travis-ci.org/librsync/librsync)

librsync implements the rolling-checksum algorithm of remote file
synchronization that was popularized by the rsync utility.

This algorithm transfers the differences between 2 files without
needing both files on the same system.

*librsync does not implement the rsync wire protocol. If you want to talk to
an rsync server to transfer files you'll need to shell out to `rsync`.
You cannot make use of librsync to talk to an rsync server.*

librsync also does not include any network functions for talking to SSH
or any other server. To access a remote filesystem, you need to provide
your own code or make use of some other virtual filesystem layer.

librsync is for building other programs that transfer files as efficiently
as rsync. You can use librsync in a program you write to do backups,
distribute binary patches to programs, or sync directories to a server
or between peers.

This tree also produces the `rdiff` command-line tool that exposes the key
operations of librsync: generating file signatures, generating the delta from a
signature to a new file, and applying the delta to regenerate the new file
given the old file.

## Copyright

librsync is Copyright 1999-2015 Martin Pool and others.

librsync is distributed under the GNU LGPL v2.1 (see COPYING), which basically
means that you can dynamically link librsync into non-GPL programs, but you
must redistribute the librsync source, with any modifications you have made.

librsync contains the BLAKE2 hash algorithm, written by Samuel Neves and
released under the CC0 public domain
dedication, <http://creativecommons.org/publicdomain/zero/1.0/>.

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

* cmake (http://cmake.org/)


## Compiling

Generate the Makefile by running

    $ cmake .

After building you can install `rdiff` and `librsync` for system-wide use.

    $ make && sudo make install


## Note for Windows

With cygwin you can build using gcc as under a normal unix system. It
is also possible to compile under cygwin using MSVC++. You must have
environment variables needed by MSCV set using the Vcvars32.bat
script. With these variables set, you just do;

    $ FIXME test in MSVC

The PCbuild directory contains a project and pre-generated config
files for use with the MSVC++ IDE. This should be enought to compile
rdiff.exe without requiring cygwin.

## Versioning

librsync uses the semver.org approach to versioning.

The solib version is simply the major number of the library version.

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

These are all produced from the source tree.

## Debugging

If you are using GNU libc, you might like to use

    MALLOC_CHECK_=2 ./rdiff

to detect some allocation bugs.

librsync has annotations for the SPLINT static checking tool.

## Testing

You can run the tests with `make test`.

**Note that CMake will not automatically build before testing.**

You need `make all && make test`.
