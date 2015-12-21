# Stats {#api_stats}

Encoding and decoding routines accumulate compression performance
statistics, such as the number of bytes read and written, indicators
a ::rs_stats_t structure.  

The particular statistics collected depend on the type
of job.

Stats may be
converted to human-readable form or written to the log file using
::rs_format_stats() or ::rs_log_stats() respectively.

Statistics are held in a structure referenced by the job object. The
statistics are kept up-to-date as the job runs and so can be used for
progress indicators.
 
::rs_job_statistics returns a pointer to statistics for the job. The
pointer is valid throughout the life of the job, until the job is freed.
The statistics are updated during processing and can be used to measure
progress.

Whole-file functions write statistics into a structure supplied by the caller.
\c NULL may be passed as the \p stats pointer if you don't want the stats.
