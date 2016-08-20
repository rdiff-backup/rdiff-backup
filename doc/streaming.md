# Streaming jobs {#api_streaming}

A key design requirement for librsync is that it should handle data as
and when the hosting application requires it.  librsync can be used
inside applications that do non-blocking IO or filtering of network
streams, because it never does IO directly, or needs to block waiting
for data.

Arbitrary-length input and output buffers are passed to the
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
- one of various possible errors in processing (see ::rs_result.)

These can be converted to a human-readable string by rs_strerror().

\note Smaller buffers have high relative handling costs.  Application
performance will be improved by using buffers of at least 32kb or so
on each call.

\sa \ref api_whole - Simpler but more limited interface than the streaming
interface.

\sa \ref api_pull - Intermediate-complexity callback interface.

\sa \ref api_callbacks - for reading from the basis file
when doing a "patch" operation.


## Creating Jobs

All streaming librsync jobs are initiated using a `_begin`
function to create a ::rs_job_t object, passing in any necessary
initialization parameters.  The various jobs available are:

- rs_sig_begin(): Calculate the signature of a file.
- rs_loadsig_begin(): Load a signature into memory.
- rs_delta_begin(): Calculate the delta between a signature and a new
file.
- rs_patch_begin(): Apply a delta to a basis to recreate the new
file.

The patch job accepts the patch as input, and uses a callback to look up
blocks within the basis file.

You must configure read, write and basis callbacks after creating the
job but before it is run.

You can set job->sig_file_bytes to signature file size or
job->estimated_signature_count before running the job
if the signature file size (or the number of chunks) is known in advance.
If both are set, estimated_signature_count is used.
This will preallocate the needed memory for signature sums instead of
calling realloc for each block.


## Running Jobs

The work of the operation is done when the application calls
rs_job_iter(). This includes reading from input files via the callback,
running the rsync algorithms, and writing output.

The IO callbacks are only called from inside rs_job_iter(). If any of
them return an error, rs_job_iter() will generally return the same error.

When librsync needs to do input or output, it calls one of the callback
functions. rs_job_iter() returns when the operation has completed or
failed, or when one of the IO callbacks has blocked.

rs_job_iter() will usually be called in a loop, perhaps alternating
librsync processing with other application functions.


## Deleting Jobs

A job is deleted and its memory freed up using rs_job_free().

This is typically called when the job has completed or failed. It can be
called earlier if the application decides it wants to cancel
processing.

rs_job_free() does not delete the output of the job, such as the sumset
loaded into memory. It does delete the job's statistics.



## State Machine Internals

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
::rs_job_t::statefn, which points to a function with a name like
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

States should never generally return ::RS_DONE directly.  Instead, they
should call rs__job_done(), which sets the state function to
rs__s_done().  This makes sure that any pending output is flushed out
before ::RS_DONE is returned to the application.
