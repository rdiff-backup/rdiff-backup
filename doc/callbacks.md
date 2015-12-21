# IO callbacks {#api_callbacks}

librsync jobs use IO callbacks to read and write files. These callbacks
might write the data directly to a file or network connection, or they
might do some additional work such as compression or encryption.

Callbacks are passed a *baton*, which is chosen by the application when
setting up the job. The baton can hold context or state for the
callback, such as a file handle or descriptor.

There are three types of callbacks, for input, output, and a special one
for random-access reads of the basis file when patching. Different types
of job use different callbacks. The callbacks are assigned when the job
is created and cannot be changed. (If the behavior of the callback
needs to change during the job, that can be controlled by variables in
the baton.)

IO callbacks are passed the address of a buffer allocated by librsync
which they read data into or write data from, plus the length of the
buffer.

Callbacks return a ::rs_result value to indicate success, an error, or
being blocked. Callbacks must set the appropriate `bytes_read` or
`bytes_written` to indicate how much data was processed. They may
process only part of the requested data, in which case they still return
::RS_DONE. In this case librsync will call the callback again later
until it either completes, fails, or blocks.

When a read callback reaches end-of-file and can return no more data, it
should return ::RS_INPUT_ENDED. In this case no data should be returned; the
output value of bytes\_read is ignored. If the callback has just a
little data left before end of file, then it should return that data
with ::RS_DONE. On the next call, unless the file has grown, it can
return ::RS_INPUT_ENDED.

If the callbacks return an error, that error will typically be passed
back to the application.

IO callbacks are only called from within rs_job_iter(), never
spontaneously. Different callbacks may be called several times in a
single invocation of rs_job_iter().
