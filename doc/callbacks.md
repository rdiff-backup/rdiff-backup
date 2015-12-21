# IO callbacks {#api_callbacks}

librsync jobs use IO callbacks to read and write files in pull mode.
It uses a "copy callback" to read data from the basis file for
"patch" operations in both push and pull mode.

These callbacks
might write the data directly to a file or network connection, or they
can do some additional work such as compression or encryption.

Callbacks are passed a `void *` baton, which is chosen by the application when
setting up the job. The baton can hold context or state for the
callback, such as a file handle or descriptor.

There are three types of callbacks, for input, output, and a special
"copy callback" for random-access reads of the basis file when patching.  

## Input and output callbacks

Input and output callbacks are both of type ::rs_driven_cb. These
are used for all operations in pull mode only (see \ref api_pull).

The callbacks are passed to rs_job_drive() and are called repeatedly
until the job completes, fails, or permanently blocks.

Input and output callbacks can and must choose their own buffers, which they
provide as pointers to librsync as the job proceeds. There are many
possibilities:

 * The application may allocate a buffer when starting the job,
   and shuffle data in and out of it as the job proceeds.  As librsync
   produces data in the output buffer, it is written out e.g. to a socket,
   and the output pointer is then reset.
   
 * The application may allocate a single output buffer adequate to hold all
   the output, and then the output callback need do nothing but let librsync
   gradually consume it.
   
 * The input or output pointers might point into a mmap'd file.
 
 * The input and output buffers might be provided by some other library.
 
The caller is responsible for freeing the buffer, and for remembering where
it previously asked librsync to write output.

## Input callbacks

Input callbacks are passed a ::rs_buffers_s struct into which they can store
a pointer to the data they have read. Note that librsync does not allocate
the buffer, the caller must do so. The input callback should update
::rs_buffers_s::next_in, ::rs_buffers_s::avail_in, and set ::rs_buffers_s::eof_in
if it's reached the end of the input.

When an input callback reaches end-of-file and can return no more data, it
should return ::RS_INPUT_ENDED.  If the callback has just a
little data left before end of file, then it should return that data
with ::RS_DONE. On the next call, unless the file has grown, it can
return ::RS_INPUT_ENDED.

## Output callbacks

Output callbacks are also passed a ::rs_buffers_s struct. On the first call,
the output callback should store a pointer to its buffer into
::rs_buffers_s::next_out, and the length into ::rs_buffers_s::avail_out. On
subsequent calls, librsync will have used some of this buffer and updated
those fields. The caller should then write out the used buffer space,
and possibly update the buffer to the place it wants new output to go.

If the callback processes only part of the requested data, it should
still return ::RS_DONE.
In this case librsync will call the callback again later
until it either completes, fails, or blocks.

The key thing to understand about ::rs_buffers_s is that the counts and
pointers are from librsync's point of view: the next byte, and the number
of bytes, that it should read or write.

## Copy callbacks

Copy callbacks are used from both push-mode (rs_job_iter()) and pull-mode
(rs_job_drive()) invocations, only when doing a "patch" operation started by
rs_patch_begin().

Copy callbacks have type ::rs_copy_cb.

Copy callbacks are directly passed a buffer and length into which they
should write the data read from the basis file.

## Callback lifecycle

IO callbacks are only called from within rs_job_drive() or
rs_job_iter().

Different callbacks may be called several times in a
single invocation of rs_job_iter() or rs_job_drive().

## Return values

Callbacks return a ::rs_result value to indicate success, an error, or
being blocked.

If the callbacks return an error, that error will typically be passed
back to the application.
