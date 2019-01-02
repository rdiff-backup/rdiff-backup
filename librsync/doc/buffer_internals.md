# Buffer internals {#buffer_internals}

## Input scoop

A module called the *scoop* is used for buffering data going into
librsync.  It accumulates data when the application does not supply it
in large enough chunks for librsync to make use of it.

The scoop object is a set of fields in the rs_job_t object::

    char       *scoop_buf;             /* the allocation pointer */
    size_t      scoop_alloc;           /* the allocation size */
    size_t      scoop_avail;           /* the data size */

Data from the read callback always goes into the scoop buffer.

The state functions call rs__scoop_read when they need some input
data.  If the read callback blocks, it might take multiple attempts
before it can be filled.  Each time, the state function will also need
to block, and then be reawakened by the library.

Once the scoop has been sufficiently filled, it must be completely
consumed by the state function.  This is easy if the state function
always requests one unit of work at a time: a block, a file header
element, etc.

All this means that the valid data is always located at the start of
the scoop, continuing for scoop_avail bytes.  The library is never
allowed to consume only part of the data.

One the state function has consumed the data, it should call
rs__scoop_reset(), which resets scoop_avail to 0.


## Output queue

The library can set up data to be written out by putting a
pointer/length for it in the output queue::

    char       *outq_ptr;
    size_t      outq_bytes;

The job infrastructure will make sure this is written out before the
next call into the state machine.

There is only one outq_ptr, so any given state function can only
produce one contiguous block of output.


## Buffer sharing

The scoop buffer may be used by the output queue.  This means that
data can traverse the library with no extra copies: one copy into the
scoop buffer, and one copy out.  In this case outq_ptr  points into
scoop_buf, and outq_bytes tells how much data needs to be written.

The state function calls rs__scoop_reset before returning when it is
finished with the data in the scoop.  However, the outq may still
point into the scoop buffer, if it has not yet been able to be copied
out.  This means that there is data in the scoop beyond scoop_avail
that must still be retained.

This is safe because neither the scoop nor the state function will
get to run before the output queue has completely drained.


## Readahead

How much readahead is required?

At the moment (??) our rollsum and MD4 routines require a full
contiguous block to calculate a checksum.  This could be relaxed, at a
possible loss of efficiency.

So calculating block checksums requires one full block to be in
memory.

When applying a patch, we only need enough readahead to unpack the
command header.

When calculating a delta, we need a full block to calculate its
checksum, plus space for the missed data.  We can accumulate any
amount of missed data before emitting it as a literal; the more we can
accumulate the more compact the encoding will be.
