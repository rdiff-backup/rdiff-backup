# librsync

http://librsync.sourcefrog.net/

\copyright

Copyright 1999-2015 Martin Pool and other contributors.

librsync is distributed under the [GNU LGPL v2.1][LGPL]
(see COPYING), which basically
means that you can dynamically link librsync into non-GPL programs, but you
must redistribute the librsync source, with any modifications you have made.

[LGPL]: http://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html

librsync contains the BLAKE2 hash algorithm, written by Samuel Neves and
released under the
[CC0 public domain dedication][CC0].

[CC0]: http://creativecommons.org/publicdomain/zero/1.0/


[TOC]


\section intro Introduction

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

\subsection is_not What librsync is not

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


\section coordinates Coordinates

librsync's home is http://librsync.sourcefrog.net/ and built documentation
is available there.

If you are reading the Doxygen version of this file, see
the @ref rdiff page about the command line tool.

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

\section requirements Requirements

To build librsync you will need:

* A C compiler and appropriate headers and libraries

* Make

* `popt` command line parsing library (http://rpm5.org/files/popt/)

* CMake (http://cmake.org/)

* Doxygen (optional to build docs) (https://www.stack.nl/~dimitri/doxygen)


\section building Building

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

\subsection building_cygwin Cygwin

With cygwin you can build using gcc as under a normal unix system. It
is also possible to compile under cygwin using MSVC++. You must have
environment variables needed by MSCV set using the Vcvars32.bat
script.

\section versioning Versioning

librsync uses the [SemVer] approach to versioning: the major version number
changes when the API changes in an incompatible way, the minor version
changes when new features are added, and the patchlevel changes when there
are improvements or fixes that do not change the API.

[SemVer]: http://semver.org/

The solib/dylib version is simply the major number of the library version.

The librsync signature and patch files are separately versioned under
application control.

See [NEWS.md](NEWS.md) for a list of changes.


\section api API Overview

The library supports three basic operations:

-# \b sig: Generating the signature S of a file A .
-# \b loadsig: Read a signature from a file into memory.
-# \b delta: Calculating a delta D from S and a new file B.
-# \b path: Applying D to A to reconstruct B.

The librsync tree also provides the \ref rdiff command-line tool, which
makes this functionality available to users and scripting languages.

The public interface to librsync (librsync.h) has functions in several
main areas:

- \ref api_whole - for applications that just
  want to make and use signatures and deltas with a single function call.
- \ref api_streaming - for blocking or non-blocking IO and processing of
  encapsulated, encrypted or compressed streams.
- \ref api_delta
- \ref api_buffers
- \ref api_trace
- \ref api_stats
- \ref api_utility


\subsection naming Naming conventions

All external symbols have the prefix \c rs_, or
\c RS_ in the case of preprocessor symbols.

Symbols beginning with \c rs__ (double underscore) are private and should
not be called from outside the library.


\subsection api_streaming Data streaming

A key design requirement for librsync is that it should handle data as
and when the hosting application requires it.  librsync can be used
inside applications that do non-blocking IO or filtering of network
streams, because it never does IO directly, or needs to block waiting
for data.

The programming interface to librsync is similar to that of zlib and
bzlib.  Arbitrary-length input and output buffers are passed to the
library by the application, through an instance of ::rs_buffers_t.  The
library proceeds as far as it can, and returns an ::rs_result value
indicating whether it needs more data or space.

All the state needed by the library to resume processing when more
data is available is kept in a small opaque ::rs_job_t structure.
After creation of a job, repeated calls to rs_job_iter() in between
filling and emptying the buffers keeps data flowing through the
stream.  The ::rs_result values returned may indicate

- ::RS_DONE:  processing is complete
- ::RS_BLOCKED: processing has blocked pending more data
- one of various possible errors in processing

These can be converted to a human-readable string by rs_strerror().

\note Smaller buffers have high relative handling costs.  Application
performance will be improved by using buffers of at least 32kb or so
on each call.

\subsection api_delta Generating and applying deltas

All encoding operations are performed by using a <tt>_begin</tt>
function to create a ::rs_job_t object, passing in any necessary
initialization parameters.  The various jobs available are:

- rs_sig_begin(): Calculate the signature of a file.
- rs_loadsig_begin(): Load a signature into memory.
- rs_delta_begin(): Calculate the delta between a signature and a new
file.
- rs_patch_begin(): Apply a delta to a basis to recreate the new
file.

\subsection api_buffers Buffers

After creating a job, input and output buffers are passed to
rs_job_iter() in an ::rs_buffers_s structure.

On input, the buffers structure must contain the address and length of
the input and output buffers.  The library updates these values to
indicate the amount of \b remaining buffer.  So, on return, \c
avail_out is not the amount of output data produced, but rather the
amount of output buffer space unfilled.  This means that the values on
return are consistent with the values on entry, but not necessarily
what you would expect.

A similar system is used by \p libz and \p libbz2.

\warning The input may not be completely consumed by the iteration if
there is not enough output space.  The application must retain unused
input data, and pass it in again when it is ready for more output.

\subsection api_whole Processing whole files

Some applications do not require fine-grained control over IO, but
rather just want to process a whole file with a single call.
librsync provides whole-file APIs to do exactly that.

These functions open files, process the entire contents, and return an
overall result. The whole-file operations are the core of the
\ref rdiff program.

Processing of a whole file begins with creation of a ::rs_job_t
object for the appropriate operation, just as if the application was
going to do buffering itself.  After creation, the job may be passed
to rs_whole_run(), which will feed it to and from two FILEs as
necessary until end of file is reached or the operation completes.

\see rs_sig_file()
\see rs_loadsig_file()
\see rs_mdfour_file()
\see rs_delta_file()
\see rs_patch_file()

\subsection api_trace Debugging trace and error logging

librsync can output trace or log messages as it proceeds.  These
follow a fairly standard priority-based filtering system
(rs_trace_set_level()), using the same severity levels as UNIX syslog.
Messages by default are sent to stderr, but may be passed to an
application-provided callback (rs_trace_to(), rs_trace_fn_t()).

\subsection api_stats Encoding statistics

Encoding and decoding routines accumulate compression performance
statistics in a ::rs_stats_t structure as they run.  These may be
converted to human-readable form or written to the log file using
rs_format_stats() or rs_log_stats() respectively.

NULL may be passed as the \p stats pointer if you don't want the stats.

\subsection api_utility Utility functions

Some additional functions are used internally and also exposed in the
API:

- encoding/decoding binary data: rs_base64(), rs_unbase64(),
rs_hexify().
- MD4 message digests: rs_mdfour(), rs_mdfour_begin(),
rs_mdfour_update(), rs_mdfour_result().
