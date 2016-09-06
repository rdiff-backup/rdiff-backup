# API Overview {#page_api}

The library supports four basic operations:

-# \b sig: Generating the signature S of a file A .
-# \b loadsig: Read a signature from a file into memory.
-# \b delta: Calculating a delta D from S and a new file B.
-# \b patch: Applying D to A to reconstruct B.

These are all available in three different modes:

- \ref api_whole - for applications that just
  want to make and use signatures and deltas on whole files
  with a single function call.
  
- \ref api_streaming - a "push" mode where the caller provides input and
  output space, and rs_job_iter() makes as much progress as it can.
  
- \ref api_pull - a "pull" mode where librsync will call application-provided
  callbacks to fill and empty buffers.
  
Other documentation pages:

- \ref api_trace - aid debugging by showing messages about librsync's state.
- \ref api_callbacks
- \ref api_stats
- \ref api_utility
- \ref versioning

The public interface to librsync is librsync.h, and other headers are internal.

The librsync tree also provides the \ref rdiff command-line tool, which
makes this functionality available to users and scripting languages.

## Naming conventions

All external symbols have the prefix \c rs_, or
\c RS_ in the case of preprocessor symbols.
(There are some private symbols that currently don't match this, but these
are considered to be bugs.)

Symbols beginning with \c rs__ (double underscore) are private and should
not be called from outside the library.

## Threaded IO

librsync may be used from threaded programs. librsync does no
synchronization itself. Each job should be guarded by a monitor or used
by only a single thread.

Be careful that the trace functions are safe to call from multiple threads.
