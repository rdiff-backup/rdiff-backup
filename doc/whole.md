# Whole-file API {#api_whole}

Some applications do not require the fine-grained control over IO, but
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

\see api_streaming
