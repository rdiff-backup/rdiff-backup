# Debugging trace and error logging {#api_trace}
 
librsync can output trace or log messages as it proceeds.
Error
messages supplement return codes by describing in more detail what went
wrong. Debug messages are useful when debugging librsync or applications
that call it.

These
follow a fairly standard priority-based filtering system
(rs_trace_set_level()), using the same severity levels as UNIX syslog.
Messages by default are sent to stderr, but may be passed to an
application-provided callback (rs_trace_to(), rs_trace_fn_t()).

The default configuration is that warning and error messages are written
to stderr. This should be appropriate for many applications. If it is
not, the level and destination of messages may be changed.

Messages are passed out of librsync through a trace callback which is
passed a severity and message string. The type for this callback is
\ref rs_trace_fn_t.

The default trace function is \ref rs_trace_stderr.

The trace callback may be changed at runtime with \ref rs_trace_to.

Messages from librsync are labelled with a severity indicator of
enumerated type \ref rs_loglevel.

The application may also specify a minimum severity of interest through
\ref rs_trace_set_level.
Messages lower than the specified level
are discarded without being passed to the trace callback.
