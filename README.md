# librsync

http://librsync.sourcefrog.net/

Copyright 1999-2015 Martin Pool and other contributors.

[TOC]

## Introduction

librsync is a library for calculating and applying network deltas,
with an interface designed to ease integration into diverse
network applications.

librsync encapsulates the core algorithms of the rsync protocol, which
help with efficient calculation of the differences between two files.
The rsync algorithm is different from most differencing algorithms
because it does not require the presence of the two files to calculate
the delta.  Instead, it requires a set of checksums of each block of
one file, which together form a signature for that file.  Blocks at
any in the other file which have the same checksum are likely to be
identical, and whatever remains is the difference.

This algorithm transfers the differences between two files without
needing both files on the same system.

librsync is for building other programs that transfer files as efficiently
as rsync. You can use librsync in a program you write to do backups,
distribute binary patches to programs, or sync directories to a server
or between peers.

This tree also produces the @ref rdiff command-line tool that exposes the key
operations of librsync: generating file signatures, generating the delta from a
signature to a new file, and applying the delta to regenerate the new file
given the old file.

librsync is used by: [Dropbox](dropbox.com),
[rdiff-backup](http://www.nongnu.org/rdiff-backup/),
[Duplicity](http://www.nongnu.org/duplicity/), and others.  
(If you would like to be listed here, let me know.)

## What librsync is not

1. librsync does not implement the rsync wire protocol. If you want to talk to
an rsync server to transfer files you'll need to shell out to `rsync`.
You cannot make use of librsync to talk to an rsync server.

2. librsync does not deal with file metadata or structure, such as filenames,
permissions, or directories. To this library, a file is just a stream of bytes.
Higher-level tools can deal with such issues in a way appropriate to their
users.
 
3. librsync also does not include any network functions for talking to SSH
or any other server. To access a remote filesystem, you need to provide
your own code or make use of some other virtual filesystem layer.


## Copyright

librsync is copyright 1999-2015 Martin Pool and others.

librsync is distributed under the [GNU LGPL v2.1][LGPL]
(see COPYING), which basically
means that you can dynamically link librsync into non-GPL programs, but you
must redistribute the librsync source, with any modifications you have made.

[LGPL]: http://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html

librsync contains the BLAKE2 hash algorithm, written by Samuel Neves and
released under the
[CC0 public domain dedication][CC0].

[CC0]: http://creativecommons.org/publicdomain/zero/1.0/

## Coordinates

librsync's home is http://librsync.sourcefrog.net/ and built documentation
is available there.

If you are reading the Doxygen version of this file, see
@ref rdiff for the command line tool.

Source and bug tracking is at https://github.com/librsync/librsync/.

There are two mailing lists:

- https://groups.google.com/forum/#!forum/librsync-announce
- https://groups.google.com/forum/#!forum/librsync

There are some [questions and answers about librsync on stackoverflow.com tagged
`librsync`][stackoverflow].
That is a good place to see if your question has already been answered.

[stackoverflow]: http://stackoverflow.com/questions/tagged/librsync

Source tarballs and git tags are at
https://github.com/librsync/librsync/releases.

Test results for builds of public github branches are at
https://travis-ci.org/librsync/librsync.

## Requirements

To build librsync you will need:

* A C compiler and appropriate headers and libraries

* Make

* `popt` command line parsing library (http://rpm5.org/files/popt/)

* CMake (http://cmake.org/)

* Doxygen (optional to build docs) (https://www.stack.nl/~dimitri/doxygen)


## Building

Generate the Makefile by running

    $ cmake .

After building you can install `rdiff` and `librsync` for system-wide use.

    $ make
    
To run the tests:

    $ make test
    
(Note that [CMake will not automatically build before testing](https://github.com/librsync/librsync/issues/49).)

To install:

    $ sudo make install
    
To build the documentation:

    $ make doc

librsync should be widely portable. Patches to fix portability bugs are
welcome.

If you are using GNU libc, you might like to use

    MALLOC_CHECK_=2 ./rdiff

to detect some allocation bugs.

librsync has annotations for the SPLINT static checking tool.

### Cygwin

With cygwin you can build using gcc as under a normal unix system. It
is also possible to compile under cygwin using MSVC++. You must have
environment variables needed by MSCV set using the Vcvars32.bat
script.

## Versioning

librsync uses the [SemVer] approach to versioning: the major version number
changes when the API changes in an incompatible way, the minor version
changes when new features are added, and the patchlevel changes when there
are improvements or fixes that do not change the API.

[SemVer]: http://semver.org/

The solib/dylib version is simply the major number of the library version.

The librsync signature and patch files are separately versioned under
application control.

See [NEWS.md](NEWS.md) for a list of changes.
