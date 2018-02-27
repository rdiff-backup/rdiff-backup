# librsync NEWS

## librsync 2.0.3

NOT RELEASED YET

## librsync 2.0.2

Released 2018-02-27

 * Improve CMake install paths configuration (wRAR,
   https://github.com/librsync/librsync/pull/133) and platform support
   checking when cross-compiling (fornwall,
   https://github.com/librsync/librsync/pull/136).

 * Fix Unaligned memory access for rs_block_sig_init() (dbaarda,
   https://github.com/librsync/librsync/issues/135).

 * Fix hashtable_test.c name collision for key_t in sys/types.h on some
   platforms (dbaarda, https://github.com/librsync/librsync/issues/134)

 * Format code with consistent style, adding `make tidy` and `make
   tidyc` targets for reformating code and comments. (dbaarda,
   https://github.com/librsync/librsync/issues/125)

 * Removed perl as a build dependency. Note it is still required for some
   tests. (dbaarda, https://github.com/librsync/librsync/issues/75)
   
 * Update RPM spec file for v2.0.2 and fix cmake man page install. (deajan,
   https://github.com/librsync/librsync/issues/47)

## librsync 2.0.1

Released 2017-10-17

 * Extensively reworked Doxygen documentation, now available at
   http://librsync.sourcefrog.net/ (Martin Pool)

 * Removed some declarations from librsync.h that were unimplemented or no
   longer ever useful: `rs_work_options`, `rs_accum_value`. Remove
   declaration of unimplemented `rs_mdfour_file()`. (Martin Pool)

 * Remove shipped `snprintf` code: no longer acutally linked after changing to
   CMake, and since it's part of C99 it should be widely available.
   (Martin Pool)

 * Document that Ninja (http://ninja-build.org/) is supported under CMake.
   It's a bit faster and nicer than Make. (Martin Pool)

 * `make check` (or `ninja check` etc) will now build and run the tests.
   Previously due to a CMake limitation, `make test` would only run existing
   tests and could fail if they weren't built.
   (Martin Pool, https://github.com/librsync/librsync/issues/49)

 * Added cmake options to exclude rdiff target and compression from build.
   See install documentation for details. Thanks to Michele Bertasi.

 * `popt` is only needed when `rdiff` is being built. (gulikoza)

 * Improved large file support for platforms using different variants
   of `fseek` (`fseeko`, `fseeko64`, `_fseeki64`), `fstat` (`fstat64`,
   `_fstati64`), and `fileno` (`_fileno`). (dbaarda, charlievieth,
   gulikoza, marius-nicolae)

 * `rdiff -s` option now shows bytes read/written and speed. (gulikoza).
   For delta operations it also shows hashtable match statistics. (dbaarda)

 * Running rdiff should not overwrite existing files (signatures, deltas and
   new patched files) by default. If the destination file exists, rdiff will
   now exit with an error. Add new option -f (--force) to overwrite existing
   files. (gulikoza)

 * Improve signature memory allocation (doubling size instead of calling
   realloc for every sig block) and added support for preallocation. See
   streaming.md job->estimated_signature_count for usage when using the
   library. `rdiff` uses this by default if possible. (gulikoza, dbaarda)

 * Significantly tidied signature handling code and testing, resulting in more
   consistent error handling behaviour, and making it easier to plug in
   alternative weak and strong sum implementations. Also fixed "slack delta"
   support for delta calculation with no signature. (dbaarda)

 * `stdint.h` and `inttypes.h` from C99 is now required. Removed redundant
   librsync-config.h header file. (dbaarda)

 * Lots of small fixes for windows platforms and building with MSVC.
   (lasalvavida, mbrt, dbaarda)

 * New open addressing hashtable implementation that significantly speeds up
   delta operations, particularly for large files. Also fixed degenerate
   behaviour with large number of duplicate blocks like runs of zeros
   in sparse files. (dbaarda)

 * Optional support with cmake option for using libb2 blake2 implementation.
   Also updated included reference blake2 implementation with bug fixes
   (dbaarda).

 * Improved default values for input and output buffer sizes. The defaults are
   now --input-size=0 and --output-size=0, which will choose recommended
   default sizes based on the --block-size and the operation being performed.
   (dbaarda)

 * Fixed hanging for truncated input files. It will now correctly report an
   error indicating an unexpected EOF was encountered. (dbaarda,
   https://github.com/librsync/librsync/issues/32)

 * Fixed #13 so that faster slack delta's are used for signatures of
   empty files. (dbaarda,
   https://github.com/librsync/librsync/issues/13)

 * Fixed #33 so rs_job_iter() doesn't need calling twice with eof=1.
   Also tidied and optimized it a bit. (dbaarda,
   https://github.com/librsync/librsync/issues/33)

 * Fixed #55 remove excessive rs_fatal() calls, replacing checks for
   programming errors with assert statements. Now rs_fatal() will only
   be called for rare unrecoverable fatal errors like malloc failures or
   impossibly large inputs. (dbaarda,
   https://github.com/librsync/librsync/issues/55)

## librsync 2.0.0

Released 2015-11-29

Note: despite the major version bump, this release has few changes and should
be binary and API compatible with the previous version.

 * Bump librsync version number to 2.0, to match the library
   soname/dylib version.
   (Martin Pool, https://github.com/librsync/librsync/issues/48)

## librsync 1.0.1 (2015-11-21)

 * Better performance on large files. (VictorDenisov)

 * Add comment on usage of rs_build_hash_table(), and assert correct use.
   Callers must call rs_build_hash_table() after loading the signature,
   and before calling rs_delta_begin().
   Thanks to Paul Harris <paulharris@computer.org>

 * Switch from autoconf to CMake.

   Thanks to Adam Schubert.

## librsync 1.0.0 (2015-01-23)

 * SECURITY: CVE-2014-8242: librsync previously used a truncated MD4
   "strong" check sum to match blocks. However, MD4 is not cryptographically
   strong. It's possible that an attacker who can control the contents of one
   part of a file could use it to control other regions of the file, if it's
   transferred using librsync/rdiff. For example this might occur in a
   database, mailbox, or VM image containing some attacker-controlled data.

   To mitigate this issue, signatures will by default be computed with a
   256-bit BLAKE2 hash. Old versions of librsync will complain about a
   bad magic number when given these signature files.

   Backward compatibility can be obtained using the new
   `rdiff sig --hash=md4`
   option or through specifying the "signature magic" in the API, but
   this should not be used when either the old or new file contain
   untrusted data.

   Deltas generated from those signatures will also use BLAKE2 during
   generation, but produce output that can be read by old versions.

   See https://github.com/librsync/librsync/issues/5

   Thanks to Michael Samuel <miknet.net> for reporting this and offering an
   initial patch.

 * Various build fixes, thanks Timothy Gu.

 * Improved rdiff man page from Debian.

 * Improved librsync.spec file for building RPMs.

 * Fixed bug #1110812 'internal error: job made no progress'; on large
   files.

 * Moved hosting to https://github.com/librsync/librsync/

 * Travis-CI.org integration test at https://travis-ci.org/librsync/librsync/

 * You can set `$LIBTOOLIZE` before running `autogen.sh`, for example on
   OS X Homebrew where it is called `glibtoolize`.

## 0.9.7 (released 2004-10-10)

 * Yet more large file support fixes.

 * `extern "C"` guards in librsync.h to let it be used from C++.

 * Removed Debian files from dist tarball.

 * Changed rdiff to an installed program on "make install".

 * Refactored delta calculation code to be cleaner and faster.

 * \#879763: Fixed mdfour to work on little-endian machines which don't
   like unaligned word access.  This should make librsync work on
   pa-risc, and it makes it slightly faster on ia64.

 * \#1022764: Fix corrupted encoding of some COPY commands in large
   files.

 * \#1024881: Print long integers directly, rather than via casts to
   double.

 * Fix printf formats for size_t: both the format and the argument
   should be cast to long.

## 0.9.6

 * Large file support fixes.

 * [v]snprintf or _[v]snprintf autoconf replacement function fix.

 * Changed installed include file from rsync.h to librsync.h.

 * Migration to sourceforge for hosting.

 * Rollsum bugfix that produces much smaller deltas.

 * Memory leaks bugfix patches.

 * mdfour bigendian and >512M bugfix, plus optimisations patch.

 * autoconf/automake updates and cleanups for autoconf 2.53.

 * Windows compilation patch, heavily modified.

 * MacOSX compilation patch, modified to autoconf vararg macro fix.

 * Debian package build scripts patch.

## 0.9.5

 * Bugfix patch from Shirish Hemant Phatak

## 0.9.4: (library 1.1.0)

 * Fixes for rsync.h from Thorsten Schuett <thorsten.schuett@zib.de>

 * RLL encoding fix from Shirish Hemant Phatak <shirish@nustorage.com>

 * RPM spec file by Peter J. Braam <braam@clusterfs.com>

 * No (intentional) changes to binary API.

## 0.9.3

 * Big speed improvements in MD4 routines and generation of weak
   checksums.

 * Patch to build on FreeBSD by Jos Backus <josb@cncdsl.com>

 * Suggestions to build on Solaris 2.6 from Alberto Accomazzi
   <aaccomazzi@cfa.harvard.edu>

 * Add rs_job_drive, a generic mechanism for turning the library into
   blocking mode.  rs_whole_run now builds on top of this.  The
   filebuf interface has changed a little to accomodate it.

 * Generating and loading signatures now generates statistics.

 * More test cases.

 * I suspect there may be a bug in rolling checksums, but it probably
   only causes inefficiency and not corruption.

 * Portability fixes for alphaev67-dec-osf5.1; at the moment builds
   but does not work because librsync tries to do unaligned accesses.

 * Works on sparc64-unknown-linux-gnu (Debian/2.2)

## 0.9.2

 * Improve delta algorithm so that deltas are actually
   delta-compressed, rather than faked.

## 0.9.1

 * Rename the library to `librsync'.

 * Portability fixes.

 * Include the popt library, and use it to build rdiff if the library
   is not present on the host.

 * Add file(1) magic for rdiff.

 * Add more to the manual pages.

 * It's no longer necessary to call rs_buffers_init on a stream before
   starting to use it: all the internal data is kept in the job, not
   in the stream.

 * Rename rs_stream_t to rs_buffers_t, a more obvious name.  Pass the
   buffers to every rs_job_iter() call, rather than setting it at
   startup.  Similarly for all the _begin() functions.

 * rs_job_new also takes the initial state function.

 * Return RS_PARAM_ERROR when library is misused.

## 0.9.0

 * Redesign API to be more like zlib/bzlib.

 * Put all command-line functions into a single rdiff(1) program.

 * New magic number `rs6'

 * Change to using popt for command line parsing.

 * Use Doxygen for API documentation.

## 0.5.7

 * Changes stats string format.

 * Slightly improved test cases

## 0.5.6

 * Don't install debugging tools into /usr/local/bin; leave them in
   the source directory.

 * Fix libhsync to build on (sgi-mips, IRIX64, gcc, GNU Make)

 * Include README.CVS in tarball

 * Back out of using libtool and shared libraries, as it is
   unnecessary at this stage, complicates installation and slows down
   compilation.

 * Use mapptr when reading data to decode, so that decoding should
   have less latency and be more reliable.

 * Cope better on systems that are missing functions like snprintf.

## 0.5.5

 * Put genuine search encoding back into the nad algorithm, and
   further clean up the nad code.  Literals are now sent out using a
   literal buffer integrated with the input mapptr so that data is not
   copied.  Checksums are still calculated from scratch each time
   rather than by rolling -- this is very slow but simple.

 * Reshuffle test cases so that they use files generated by hsmapread,
   rather than the source directory.  This makes the tests quicker and
   more reproducible, hopefully without losing coverage.  Further
   develop the test driver framework.

 * Add hsdumpsums debugging tool.

 * Hex strings (eg strong checksums) are broken up by underscores for
   readability.

 * Stats now go to the log rather than stdout.

 * mapptr acts properly when we're skipping/rewinding to data already
   present in the buffer -- it does a copy if required, but not
   necessarily real IO.

## 0.5.4

 * Improved mapptr input code

 * Turn on more warnings if using gcc

 * More test cases

## 0.5.3

 * Improvements to mapptr to make it work better for network IO.

 * Debug trace code is compiled in unless turned off in ./configure
   (although most programs will not write it out unless asked.)

 * Add libhsyncinfo program to show compiled-in settings and version.

 * Add test cases that run across localhost TCP sockets.

 * Improved build code; should now build easily from CVS through
   autogen.sh.

 * Improved trace code.

 * Clean up to build on sparc-sun-solaris2.8, and in the process clean
   up the handling of bytes vs chars, and of building without gcc

 * Reverse build scripts so that driver.sh calls the particular
   script.

## 0.5.2

 * Use mapptr for input.

 * Implement a new structure for encoding in nad.c.  It doesn't
   encode at the moment, but it's much more maintainable.

 * More regression cases.

 * Clean up build process.

## 0.5.0

 * Rewrite hs_inbuf and hs_encode to make them simpler and more
   reliable.

 * Test cases for input handling.

 * Use the map_ptr idea for input from both streams and files.

## 0.4.1

 * automake/autoconf now works cleanly when the build directory is
   different to the source directory.

 * --enable-ccmalloc works again.

## 0.4.0

* A much better regression suite.

* CHECKSUM token includes the file's checksum up to the current
  location, to aid in self-testing.

* Various bug fixes, particularly to do with short IO returns.
