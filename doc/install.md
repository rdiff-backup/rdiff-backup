# Installing librsync {#page_install}

## Requirements

To build librsync you will need:

* A C compiler and appropriate headers and libraries

* [CMake]

* Some build tool supported by CMake: [Make] is most common,
  [Ninja] is nicer.

* [popt] command line parsing library

* [Doxygen] - optional, to build docs

[popt]: http://rpm5.org/files/popt/
[CMake]: http://cmake.org/
[Doxygen]: https://www.stack.nl/~dimitri/doxygen
[Ninja]: http://build-ninja.org
[Make]: https://www.gnu.org/software/make/

## Building

Generate the Makefile by running

    $ cmake .

After building you can install `rdiff` and `librsync` for system-wide use.

    $ make

To build and run the tests:

    $ make check

To install:

    $ sudo make install

To build the documentation:

    $ make doc

librsync should be widely portable. Patches to fix portability bugs are
welcome.

If you are using GNU libc, you might like to use

    MALLOC_CHECK_=2 ./rdiff

to detect some allocation bugs.

librsync has annotations for the SPLINT static checking tool.


## Build options

The build is customizable by using CMake options in the configure step:

    $ cmake -D <option-name>=<value> .

If you are interested in building only the `librsync` target, you can skip
the `rdiff` build. In this way you don't need its dependencies (e.g. `popt`).
To do that, set the `BUILD_RDIFF` option to `OFF`:

    $ cmake -D BUILD_RDIFF=OFF .

Be aware that many tests depend on `rdiff` executable, so when it is disabled,
also those tests are.

Compression support is under development (see
[#8](https://github.com/librsync/librsync/issues/8)). It is so disabled by
default. You can turn it on by using `ENABLE_COMPRESSION` option:

    $ cmake -D ENABLE_COMPRESSION=ON .

To build code for debug trace messages:

    $ cmake -D ENABLE_TRACE=ON .

## Ninja builds

CMake generates input files for an underlying build tool that will actually do
the build. Typically this is Make, but others are supported. In particular
[Ninja] is a nice alternative. To use it:

    $ cmake -G Ninja .
    $ ninja check


## Cygwin

With Cygwin you can build using gcc as under a normal unix system. It
is also possible to compile under Cygwin using MSVC++. You must have
environment variables needed by MSVC set using the Vcvars32.bat
script.
