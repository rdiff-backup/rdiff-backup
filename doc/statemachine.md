# librsync state machine

## State Machines


Internally, the operations are implemented as state machines that move
through various states as input and output buffers become available.

All computers and programs are state machines.  So why is the
representation as a state machine a little more explicit (and perhaps
verbose) in librsync than other places?  Because we need to be able to
let the real computer go off and do something else like waiting for
network traffic, while still remembering where it was in the librsync
state machine.

librsync will never block waiting for IO, unless the callbacks do
that.

The current state is represented by the private field
`job->statefn`, which points to a function with a name like
`rs_OPERATION_s_STATE`.  Every time librsync tries to make progress,
it will call this function.

The state function returns one of the ::rs_result values.  The
most important values are

 * ::RS_DONE: Completed successfully.

 * ::RS_BLOCKED: Cannot make further progress at this point.

 * ::RS_RUNNING: The state function has neither completed nor blocked but
    wants to be called again.  **XXX**: Perhaps this should be removed?

States need to correspond to suspension points.  The only place the
job can resume after blocking is at the entry to a state function.

Therefore states must be "all or nothing" in that they can either
complete, or restart without losing information.

Basically every state needs to work from one input buffer to one
output buffer.

States should never generally return RS_DONE directly.  Instead, they
should call rs__job_done, which sets the state function to
rs__s_done.  This makes sure that any pending output is flushed out
before RS_DONE is returned to the application.


## Blocking input and output

The IO callbacks are allowed to block or to process only part of the
requested data.  The library needs to cope with this frustration.

The library might not get as much input as it wanted when it is first
called.  If it gets a partial read, it needs to hold onto that
valuable and irreplaceable data.

It cannot keep it on the stack, because it will be lost if the read
blocks.  It needs to be kept in the job structure, or in somewhere
referenced from there.

The state function probably cannot proceed until it has all the needed
input.  So possibly this can be expressed at a high level of the job
structure.  Or perhaps it should just be done by each particular state
function.

When the library has output to write out, the callback might not be
able to accept all of it at the time it is called.  Deferred outgoing
data needs to be stored in a buffer referenced from the job structure.

I think it's always OK to try to flush this when entering rs_job_run.
I think it's OK to not do anything else until all the outgoing data
has been flushed.

In many cases we would like to pass a pointer into the input (or
pread) buffer straight to the output callback.  In other cases, we
need a different buffer to build up literal outgoing data.

librsync deals with short, bounded-size headers and checksums, and
with arbitrarily-large streaming data.  Although the commands are of
bounded size, they are not of fixed size, because there are different
encodings to suit different situations.

The situation is very similar to fetching variable-length headers from
a socket.  We cannot read the whole command in a single input, because
we don't know how long it is.  As a general principle I think we
should *not* read in too much data and buffer it, because this
complicates things.  Therefore we need to read the type byte first,
and then possibly read some parameters.


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
rs__scoop_reset, which resets scoop_avail to 0.


## Output queue

The library can set up data to be written out by putting a
pointer/length for it in the output queue::

    char       *outq_ptr;
    size_t      outq_bytes;

The job infrastructure will make sure this is written out before the
next call into the state machine.  This implies it is

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
