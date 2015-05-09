project(librsync)
cmake_minimum_required(VERSION 2.6)


set(librsync_MAJOR_VERSION 1)
set(librsync_MINOR_VERSION 0)
set(librsync_PATCH_VERSION 0)

set(librsync_VERSION
  ${librsync_MAJOR_VERSION}.${librsync_MINOR_VERSION}.${librsync_PATCH_VERSION})

set(CMAKE_MODULE_PATH "${CMAKE_SOURCE_DIR}/cmake")

if (NOT CMAKE_SYSTEM_PROCESSOR)
	message(FATAL_ERROR "No target CPU architecture set")
endif()

if (NOT CMAKE_SYSTEM_NAME)
	message(FATAL_ERROR "No target OS set")
endif()

execute_process(COMMAND perl "${CMAKE_SOURCE_DIR}/mkprototab.pl" "prototab.c" "prototab.h")

include ( CheckIncludeFiles )
check_include_files ( alloca.h HAVE_ALLOCA_H )
check_include_files ( dlfcn.h HAVE_DLFCN_H )
check_include_files ( inttypes.h HAVE_INTTYPES_H )
check_include_files ( memory.h HAVE_MEMORY_H )
check_include_files ( stdint.h HAVE_STDINT_H )
check_include_files ( stdlib.h HAVE_STDLIB_H )
check_include_files ( strings.h HAVE_STRINGS_H )
check_include_files ( string.h HAVE_STRING_H )
check_include_files ( sys/stat.h HAVE_SYS_STAT_H )
check_include_files ( sys/types.h HAVE_SYS_TYPES_H )
check_include_files ( unistd.h HAVE_UNISTD_H )
check_include_files ( bzlib.h HAVE_BZLIB_H )
check_include_files ( fcntl.h HAVE_FCNTL_H )
check_include_files ( malloc.h HAVE_MALLOC_H )
check_include_files ( mcheck.h HAVE_MCHECK_H )
check_include_files ( sys/file.h HAVE_SYS_FILE_H )
check_include_files ( zlib.h HAVE_ZLIB_H )

#Temporary configuration
set ( STDC_HEADERS 1 )
set ( DO_RS_TRACE 0 )
set ( HAVE_PROGRAM_INVOCATION_NAME 0)
set ( HAVE_VARARG_MACROS 0 )


include ( CheckFunctionExists )
check_function_exists ( alloca HAVE_ALLOCA )
check_function_exists ( fseeko HAVE_FSEEKO )
check_function_exists ( memmove HAVE_MEMMOVE )
check_function_exists ( memset HAVE_MEMSET )
check_function_exists ( snprintf HAVE_SNPRINTF )
check_function_exists ( strchr HAVE_STRCHR )
check_function_exists ( strerror HAVE_STRERROR )
check_function_exists ( vsnprintf HAVE_VSNPRINTF )
check_function_exists ( _snprintf HAVE__SNPRINTF )
check_function_exists ( _vsnprintf HAVE__VSNPRINTF )

include(CheckTypeSize)
check_type_size ( "long" SIZEOF_LONG )
check_type_size ( "long long" SIZEOF_LONG_LONG )
check_type_size ( "off_t" SIZEOF_OFF_T )
check_type_size ( "size_t" SIZEOF_SIZE_T )
check_type_size ( "unsigned int" SIZEOF_UNSIGNED_INT )
check_type_size ( "unsigned long" SIZEOF_UNSIGNED_LONG )
check_type_size ( "unsigned short" SIZEOF_UNSIGNED_SHORT )

site_name(SITE_NAME)

message (STATUS "PROJECT_NAME  = ${PROJECT_NAME}")
message (STATUS "SITE_NAME  = ${SITE_NAME}")

# Find POPT
find_package(POPT REQUIRED)
include_directories(${POPT_INCLUDE_DIRS})

# Find BZIP
find_package (BZip2 REQUIRED)
if (BZIP2_FOUND)
  message (STATUS "Found components for BZIP2")
  message (STATUS "BZIP2_INCLUDE_DIR  = ${BZIP2_INCLUDE_DIR}")
  message (STATUS "BZIP_LIBRARIES = ${BZIP2_LIBRARIES}")
  include_directories(${BZIP2_INCLUDE_DIR})
endif (BZIP2_FOUND)

# Find ZLIB
find_package (ZLIB REQUIRED)
if (ZLIB_FOUND)
  message (STATUS "Found components for ZLIB")
  message (STATUS "BZIP2_INCLUDE_DIR  = ${ZLIB_INCLUDE_DIR}")
  message (STATUS "BZIP_LIBRARIES = ${ZLIB_LIBRARIES}")
  include_directories(${ZLIB_INCLUDE_DIRS})
endif (ZLIB_FOUND)

configure_file(${CMAKE_CURRENT_SOURCE_DIR}/config.h.cmake ${CMAKE_CURRENT_BINARY_DIR}/config.h)

configure_file(${CMAKE_CURRENT_SOURCE_DIR}/librsync-config.h.cmake ${CMAKE_CURRENT_BINARY_DIR}/librsync-config.h)

#add_subdirectory(doc)
#add_subdirectory(testsuite)


########### next target ###############

set(rsync_LIB_SRCS
    prototab.c
    prototab.h
    base64.c
    buf.c
    buf.h
    config.h
    checksum.c
    checksum.h
    command.c
    command.h
    delta.c
    emit.c
    emit.h
    fileutil.c
    fileutil.h
    hex.c
    job.c
    job.h
    mdfour.c
    mdfour.h
    mksum.c
    msg.c
    netint.c
    netint.h
    patch.c
    readsums.c
    librsync.h
    librsync-config.h
    rollsum.c
    rollsum.h
    scoop.c
    search.c
    search.h
    stats.c
    stream.c
    stream.h
    sumset.c
    sumset.h
    trace.c
    trace.h
    tube.c
    types.h
    util.c
    util.h
    version.c
    whole.c
    whole.h
    snprintf.h
    blake2b-ref.c
    blake2.h
    blake2-impl.h)

add_library(rsync SHARED ${rsync_LIB_SRCS})

target_link_libraries(rsync
${BZIP2_LIBRARIES}
${ZLIB_LIBRARIES}
)

set_target_properties(rsync PROPERTIES VERSION 1.0.0 SOVERSION 1)
#install(TARGETS rsync ${INSTALL_TARGETS_DEFAULT_ARGS})


########### next target ###############

set(rdiff_SRCS
    rdiff.c
    isprefix.c
    isprefix.h
    librsync.h
    librsync-config.h
    trace.h)

add_executable(rdiff ${rdiff_SRCS})

target_link_libraries(rdiff rsync ${POPT_LIBRARIES})

#install(TARGETS rdiff ${INSTALL_TARGETS_DEFAULT_ARGS})


########### install files ###############

#install(FILES  librsync.h librsync-config.h DESTINATION include)
#install(FILES  mkprototab.pl DESTINATION )



#original Makefile.am contents follow:

### Process this file with automake to produce Makefile.in
#
## Copyright (C) 2000, 2001, 2002, 2014 by Martin Pool <mbp@sourcefrog.net>
## Copyright (C) 2003 by Donovan Baarda <abo@minkirri.apana.org.au> 
#
## This program is free software; you can redistribute it and/or
## modify it under the terms of the GNU Lesser General Public License
## as published by the Free Software Foundation; either version 2.1 of
## the License, or (at your option) any later version.
## 
## This program is distributed in the hope that it will be useful, but
## WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
## Lesser General Public License for more details.
## 
## You should have received a copy of the GNU Lesser General Public
## License along with this program; if not, write to the Free Software
## Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
#AUTOMAKE_OPTIONS = foreign
#SUBDIRS = . doc testsuite
#ACLOCAL_AMFLAGS = -I m4
#
#MAINTAINERCLEANFILES = Makefile.in \
#	aclocal.m4 config.guess config.h.in config.sub configure \
#	depcomp install-sh ltmain.sh missing mkinstalldirs \
#	prototab.c prototab.h
#
#EXTRA_DIST = autogen.sh configure.msc $(noinst_SCRIPTS) rdiff.magic \
#	librsync.spec README.RPM libversions.txt \
#	PCbuild/rdiff.dsp PCbuild/PCbuild.dsw   PCbuild/config.h \
#	PCbuild/librsync-config.h
#
#include_HEADERS = librsync.h librsync-config.h
#
#lib_LTLIBRARIES = librsync.la
#
#librsync_la_SOURCES =  prototab.c prototab.h \
#	base64.c buf.c buf.h checksum.c checksum.h command.c \
#	command.h delta.c emit.c emit.h fileutil.c fileutil.h \
#	hex.c job.c job.h mdfour.c mdfour.h mksum.c msg.c netint.c netint.h \
#	patch.c readsums.c librsync.h librsync-config.h \
#	rollsum.c rollsum.h \
#	scoop.c search.c search.h stats.c stream.c stream.h sumset.c \
#	sumset.h trace.c trace.h tube.c types.h util.c util.h \
#	version.c whole.c whole.h snprintf.h \
#	blake2b-ref.c blake2.h blake2-impl.h
#
#librsync_la_LIBADD = @LIBOBJS@
#
#librsync_la_LDFLAGS = -version-info @librsync_libversion@
#
## This is the default for any programs that don't specify a preference.
#LDADD = librsync.la
#
## This is the rdiff application
#bin_PROGRAMS = rdiff
#
#rdiff_SOURCES = rdiff.c isprefix.c isprefix.h librsync.h librsync-config.h \
#	trace.h
#
#rdiff_LDADD = librsync.la
#
#rdiff_DEPENDENCIES = librsync.la
#
## this script is used to build prototab.[ch]
#noinst_SCRIPTS = mkprototab.pl
#
## Autogenerated by a script.
#prototab.c prototab.h: $(srcdir)/mkprototab.pl
#	perl $(srcdir)/mkprototab.pl prototab.c prototab.h
