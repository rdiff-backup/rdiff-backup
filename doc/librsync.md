
## API overview

### Debug messages

IO callbacks
============

librsync jobs use IO callbacks to read and write files. These callbacks
might write the data directly to a file or network connection, or they
might do some additional work such as compression or encryption.

Callbacks are passed a *baton*, which is chosen by the application when
setting up the job. The baton can hold context or state for the
callback, such as a file handle or descriptor.

There are three types of callbacks, for input, output, and a special one
for random-access reads of the basis file when patching. Different types
of job use different callbacks. The callbacks are assigned when the job
is created and cannot be changed. (If the behaviour of the callback
needs to change during the job, that can be controlled by variables in
the baton.)

There are three function typedefs for these callbacks:

    typedef rs_result rs_cb_read(void *baton,
                                 char *buf,
                                 size_t buf_len,
                                 size_t *bytes_read);

    typedef rs_result rs_cb_basis(void *baton,
                                  char *buf,
                                  size_t buf_len,
                                  off_t offset,
                                  size_t *bytes_read);

    typedef rs_result rs_cb_write(void *baton,
                                  const char *buf,
                                  size_t buf_len,
                                  size_t *bytes_written);

IO callbacks are passed the address of a buffer allocated by librsync
which they read data into or write data from, plus the length of the
buffer.

Callbacks return an `rs_result` value to indicate success, an error, or
being blocked. Callbacks must set the appropriate `bytes_read` or
`bytes_written` to indicate how much data was processed. They may
process only part of the requested data, in which case they still return
`RS_DONE`. In this case librsync will call the callback again later
until it either completes, fails, or blocks.

When a read callback reaches end-of-file and can return no more data, it
should return `RS_EOF`. In this case no data should be returned; the
output value of bytes\_read is ignored. If the callback has just a
little data left before end of file, then it should return that data
with `RS_DONE`. On the next call, unless the file has grown, it can
return `RS_EOF`.

If the callbacks return an error, that error will typically be passed
back to the application.

IO callbacks are only called from within `rs_job_run`, never
spontaneously. Different callbacks may be called several times in a
single invocation of `rs_job_run`.

stdio callbacks
---------------

librsync provides predefined IO callbacks that wrap the C stdio
facility. The baton argument for all these functions is a `FILE*`:

    rs_result rs_cb_read_stdio(void*,
                               char *buf,
                               size_t buf_len,
                               size_t *bytes_read);

    rs_result rs_cb_basis_stdio(void *,
                                char *buf,
                                size_t buf_len,
                                off_t offset,
                                size_t *bytes_read);

    rs_result rs_cb_write_stdio(void *voidp,
                                const char *buf,
                                size_t buf_len,
                                size_t *bytes_written);

There is also a utility function that wraps `fopen`. It reports any
errors through the librsync error log, and translates return values. It
also treats `-` as stdin or stdout as appropriate. :

    rs_result rs_stdio_open(const char *file,
                            const char *mode,
                            FILE **filp_out);

Creating Jobs
=============

There are functions to create jobs for each operation: gensig, delta,
loadsig and patch. These functions create a new job object, which can
then be run using `rs_job_run`. These creation functions are passed the
IO callbacks and batons to be used for the job.

    rs_result rs_gensig_begin(rs_job_t **job_out,
                              size_t block_len,
                              size_t strong_sum_len,
                              rs_cb_read *read_cb, void *read_baton,
                              rs_cb_write *write_cb, void *write_baton);

A newly allocated job object is stored in `*job_out`.

The patch job accepts the patch as input, and uses a callback to look up
blocks within the basis file.

You must configure read, write and basis callbacks after creating the
job but before it is run.

After creating the job, call `rs_job_run` to feed in patch data and
retrieve output data. When the job is complete, call `rs_job_finish` to
dispose of the job object and free memory.

Running Jobs
============

The work of the operation is done when the application calls
`rs_job_run`. This includes reading from input files via the callback,
running the rsync algorithms, and writing output.

The IO callbacks are only called from inside `rs_job_run`. If any of
them return an error, `rs_job_run` will generally return the same error.

When librsync needs to do input or output, it calls one of the callback
functions. `rs_job_run` returns when the operation has completed or
failed, or when one of the IO callbacks has blocked.

`rs_job_run` will usually be called in a loop, perhaps alternating
librsync processing with other application functions.

    rs_result rs_job_run(rs_job_t *job);

Deleting Jobs
=============

A job is deleted and its memory freed up using `rs_job_free`:

    rs_result rs_job_free(rs_job_t *job);

This is typically called when the job has completed or failed. It can be
called earlier if the application decides it wants to cancell
processing.

`rs_job_free` does not delete the output of the job, such as the sumset
loaded into memory. It does delete the job's statistics.

Non-blocking IO
===============

The librsync interface allows non-blocking streaming processing of data.
This means that the library will accept input and produce output when it
suits the application. If nonblocking file IO is used and the IO
callbacks support it, then librsync will never block waiting for IO.

Normally callbacks will read/write the whole buffer when they're called,
but in some cases they might not be able to process all of it, or
perhaps not process any at all. This might happen if the callbacks are
connected to a nonblocking socket. Either of two things can happen in
this case. If the callback returns `RS_BLOCKED`, then `rs_job_run` will
also return `RS_BLOCKED` shortly.

When an IO callback blocks, it is the responsibility of the application
to work out when it will be able to make progress and therefore when it
is worth calling `rs_job_run` again. Typically this involves a mechanism
like `poll` or `select` to wait for the file descriptor to be ready.

Threaded IO
===========

librsync may be used from threaded programs. librsync does no
synchronization itself. Each job should be guarded by a monitor or used
by only a single thread.

Job Statistics
==============

Jobs accumulate statistics while they run, such as the number of input
and output bytes. The particular statistics collected depend on the type
of job. :

    const rs_stats_t * rs_job_statistics(rs_job_t *job);

`rs_job_statistics` returns a pointer to statistics for the job. The
pointer is valid throughout the life of the job, until the job is freed.
The statistics are updated during processing and can be used to measure
progress.

Statistics can be written to the trace file in human-readable form:

    int rs_log_stats(rs_stats_t const *stats);

Statistics are held in a structure referenced by the job object. The
statistics are kept up-to-date as the job runs and so can be used for
progress indicators.
