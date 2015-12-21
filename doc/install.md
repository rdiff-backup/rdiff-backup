# Installing librsync {#page_install}

## Requirements

To build librsync you will need:

* A C compiler and appropriate headers and libraries

* Make

* [popt] command line parsing library

* CMake (http://cmake.org/)

* Doxygen (optional to build docs) (https://www.stack.nl/~dimitri/doxygen)

[popt]: http://rpm5.org/files/popt/


## Building

Generate the Makefile by running

    $ cmake .

After building you can install `rdiff` and `librsync` for system-wide use.

    $ make
    
To run the tests:

    $ make test
    
(Note that [CMake will not automatically build before testing](https://github.com/librsync/librsync/issues/49).)

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

## Cygwin

With Cygwin you can build using gcc as under a normal unix system. It
is also possible to compile under Cygwin using MSVC++. You must have
environment variables needed by MSVC set using the Vcvars32.bat
script.
