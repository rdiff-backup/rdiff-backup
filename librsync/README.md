# librsync

http://librsync.sourcefrog.net/

\copyright

Copyright 1999-2016 Martin Pool and other contributors.

librsync is distributed under the [GNU LGPL v2.1][LGPL]
(see COPYING), which basically
means that you can dynamically link librsync into non-GPL programs, but you
must redistribute the librsync source, with any modifications you have made.

[LGPL]: http://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html

librsync contains the BLAKE2 hash algorithm, written by Samuel Neves and
released under the [CC0 public domain dedication][CC0].

[CC0]: http://creativecommons.org/publicdomain/zero/1.0/


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

librsync was originally written for the rproxy experiment in
delta-compression for HTTP.
librsync is used by: [Dropbox](https://dropbox.com/),
[rdiff-backup](http://www.nongnu.org/rdiff-backup/),
[Duplicity](http://www.nongnu.org/duplicity/), and others.
(If you would like to be listed here, let me know.)

### What librsync is not

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


## More information

* \ref page_downloads
* \ref versioning
* \ref page_install
* \ref page_api
* \ref page_support
* \ref page_contributing
* \ref rdiff command line interface
* \ref NEWS.md
* \ref page_formats
