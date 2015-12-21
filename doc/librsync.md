# API Overview {#page_api}

The library supports four basic operations:

-# \b sig: Generating the signature S of a file A .
-# \b loadsig: Read a signature from a file into memory.
-# \b delta: Calculating a delta D from S and a new file B.
-# \b path: Applying D to A to reconstruct B.

These are all available in two different modes:

- \ref api_whole - for applications that just
  want to make and use signatures and deltas with a single function call.
- \ref api_streaming - for blocking or non-blocking IO and processing of
  encapsulated, encrypted or compressed streams.

The librsync tree also provides the \ref rdiff command-line tool, which
makes this functionality available to users and scripting languages.

The public interface to librsync (\ref librsync.h) has functions in several
main areas:

- \ref api_trace - aid debugging by showing messages about librsync's state.
- \ref api_callbacks
- \ref api_stats
- \ref api_utility
- \ref versioning

## Naming conventions

All external symbols have the prefix \c rs_, or
\c RS_ in the case of preprocessor symbols.
(There are some private symbols that currently don't match this, but these
are considered to be bugs.)

Symbols beginning with \c rs__ (double underscore) are private and should
not be called from outside the library.
