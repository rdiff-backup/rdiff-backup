# Pull stream interface {#api_pull}

As an alternative to \ref api_streaming, librsync provides a "pull"-mode
interface where it will repeatedly call application-provided callbacks
to get more input data and to accept output data.

Pull jobs are also created using rs_sig_begin(), rs_loadsig_begin,()
rs_delta_begin(), rs_patch_begin().

However, rather than calling rs_job_iter(), the application should then call
rs_job_drive(), passing an input and an output callback. rs_job_drive() takes
an opaque pointer for both the input and output callback: this could be a
`FILE*` or some similar object telling them what to read and write.

## Non-blocking IO

The librsync interface allows non-blocking streaming processing of data.
This means that the library will accept input and produce output when it
suits the application. If nonblocking file IO is used and the IO
callbacks support it, then librsync will never block waiting for IO.

Normally callbacks will read/write the whole buffer when they're called,
but in some cases they might not be able to process all of it, or
perhaps not process any at all. This might happen if the callbacks are
connected to a nonblocking socket. Either of two things can happen in
this case. If the callback returns ::RS_BLOCKED, then rs_job_iter() will
also return ::RS_BLOCKED shortly.

When an IO callback blocks, it is the responsibility of the application
to work out when it will be able to make progress and therefore when it
is worth calling rs_job_iter() again. Typically this involves a mechanism
like `poll` or `select` to wait for the file descriptor to be ready.

## Blocking IO

The IO callbacks are allowed to block.
This will of course mean that the application's call to
rs_job_drive() will also block.

## Partial completion

IO callbacks are also allowed to process or provide only part of the requested
data, as will commonly happen with socket IO.

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

I think it's always OK to try to flush this when entering rs_job_iter.
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
