# Versioning {#versioning}

librsync uses the [SemVer] approach to versioning: the major version number
changes when the API changes in an incompatible way, the minor version
changes when new features are added, and the patchlevel changes when there
are improvements or fixes that do not change the API.

[SemVer]: http://semver.org/

The solib/dylib version is simply the major number of the library version.

The librsync signature and patch files are separately versioned under
application control, by passing a ::rs_magic_number when creating a job.

The library version can be checked at runtime in ::rs_librsync_version.

A brief summary of the licence on librsync is in ::rs_licence_string.

See [NEWS.md](NEWS.md) for a list of changes.

\note Only the public interface, defined in \ref librsync.h, is covered
by the API stability contract. Internal symbols and functions may change
without notice.
