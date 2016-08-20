# Copyright (C) 2015 Adam Schubert <adam.schubert@sg1-game.net>
# Copyright 2016 Martin Pool
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.


project(librsync)
cmake_minimum_required(VERSION 2.6)

INCLUDE(CMakeDependentOption)

set(LIBRSYNC_MAJOR_VERSION 2)
set(LIBRSYNC_MINOR_VERSION 0)
set(LIBRSYNC_PATCH_VERSION 1)

set(LIBRSYNC_VERSION
  ${LIBRSYNC_MAJOR_VERSION}.${LIBRSYNC_MINOR_VERSION}.${LIBRSYNC_PATCH_VERSION})

set(CMAKE_MODULE_PATH "${CMAKE_SOURCE_DIR}/cmake")

if (NOT CMAKE_SYSTEM_PROCESSOR)
	message(FATAL_ERROR "No target CPU architecture set")
endif()

if (NOT CMAKE_SYSTEM_NAME)
	message(FATAL_ERROR "No target OS set")
endif()

# Add an option to include compression support
option(ENABLE_COMPRESSION "Whether or not to build with compression support" OFF)
# TODO: Remove this warning when compression is implemented.
#       Consider turning compression ON by default.
if (ENABLE_COMPRESSION)
    message(WARNING "Compression support is not functional. See issue #8.")
endif (ENABLE_COMPRESSION)

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

# Remove compression support if not needed
if (NOT ENABLE_COMPRESSION)
  SET(HAVE_BZLIB_H 0)
  SET(HAVE_ZLIB_H 0)
endif (NOT ENABLE_COMPRESSION)


include ( CheckFunctionExists )
check_function_exists ( alloca HAVE_ALLOCA )
check_function_exists ( fseeko HAVE_FSEEKO )
check_function_exists ( fseeko64 HAVE_FSEEKO64 )
check_function_exists ( fstat64 HAVE_FSTAT64 )
check_function_exists ( _fstati64 HAVE_FSTATI64 )
check_function_exists ( memmove HAVE_MEMMOVE )
check_function_exists ( memset HAVE_MEMSET )
check_function_exists ( strchr HAVE_STRCHR )
check_function_exists ( strerror HAVE_STRERROR )

include(CheckTypeSize)
check_type_size ( "long" SIZEOF_LONG )
check_type_size ( "long long" SIZEOF_LONG_LONG )
check_type_size ( "off_t" SIZEOF_OFF_T )
check_type_size ( "off64_t" SIZEOF_OFF64_T )
check_type_size ( "size_t" SIZEOF_SIZE_T )
check_type_size ( "unsigned int" SIZEOF_UNSIGNED_INT )
check_type_size ( "unsigned long" SIZEOF_UNSIGNED_LONG )
check_type_size ( "unsigned short" SIZEOF_UNSIGNED_SHORT )

#!FIXME: is this really the best way to do it? I think the limitation on
# rs_long_t is that we need to be able to seek to it, which relates to
# long file support. With fseeko, rs_long_t should be off_t, otherwise
# it should be long.
if ( HAVE_FSEEKO64 AND SIZEOF_OFF64_T )
  set( RS_LONG_T "off64_t" )
  message (STATUS "RS_LONG_T = off64_t")
elseif ( HAVE_SYS_TYPES_H AND LONG_LONG )
  set( RS_LONG_T LONG_LONG )
  message (STATUS "RS_LONG_T = ${LONG_LONG}")
else()
  if ( SIZEOF_LONG_LONG )
    set( RS_LONG_T "long long" )
    message (STATUS "RS_LONG_T = long long")
  else ( SIZEOF_LONG_LONG )
    set( RS_LONG_T "long" )
    message (STATUS "RS_LONG_T = long")
  endif ( SIZEOF_LONG_LONG )
endif()

# OS X
if(APPLE)
  set(CMAKE_MACOSX_RPATH ON)
  set(CMAKE_SKIP_BUILD_RPATH FALSE)
  set(CMAKE_BUILD_WITH_INSTALL_RPATH FALSE)
  set(CMAKE_INSTALL_RPATH "${CMAKE_INSTALL_PREFIX}/lib")
  set(CMAKE_INSTALL_RPATH_USE_LINK_PATH TRUE)
  list(FIND CMAKE_PLATFORM_IMPLICIT_LINK_DIRECTORIES "${CMAKE_INSTALL_PREFIX}/lib" isSystemDir)
  if("${isSystemDir}" STREQUAL "-1")
    set(CMAKE_INSTALL_RPATH "${CMAKE_INSTALL_PREFIX}/lib")
  endif()
endif()

if (CMAKE_C_COMPILER_ID MATCHES "(Clang|Gnu|GNU)")
  # TODO: Set for MSVC and other compilers.
  # TODO: Set -Werror when the build is clean.

  set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -Wall")
endif()

site_name(BUILD_HOSTNAME)

message (STATUS "PROJECT_NAME  = ${PROJECT_NAME}")
message (STATUS "BUILD_HOSTNAME = ${BUILD_HOSTNAME}")
message (STATUS "CMAKE_SYSTEM = ${CMAKE_SYSTEM}")

# Find POPT
find_package(POPT)
if (POPT_FOUND)
  include_directories(${POPT_INCLUDE_DIRS})
endif (POPT_FOUND)

# Add an option to exclude rdiff executable from build
# This is useful, because it allows to remove POPT dependency if a user is interested only in the
# rsync library itself and not in the rdiff executable
cmake_dependent_option(BUILD_RDIFF "Whether or not to build rdiff executable" ON "POPT_FOUND" OFF)

# Find BZIP
find_package (BZip2)
if (BZIP2_FOUND)
  message (STATUS "Found components for BZIP2")
  message (STATUS "BZIP2_INCLUDE_DIR  = ${BZIP2_INCLUDE_DIR}")
  message (STATUS "BZIP2_LIBRARIES = ${BZIP2_LIBRARIES}")
  include_directories(${BZIP2_INCLUDE_DIR})
endif (BZIP2_FOUND)

# Find Perl
find_package (Perl REQUIRED)
if (PERL_FOUND)
  message (STATUS "PERL_EXECUTABLE  = ${PERL_EXECUTABLE}")
endif (PERL_FOUND)

# Find ZLIB
find_package (ZLIB)
if (ZLIB_FOUND)
  message (STATUS "Found components for ZLIB")
  message (STATUS "ZLIB_INCLUDE_DIR  = ${ZLIB_INCLUDE_DIR}")
  message (STATUS "ZLIB_LIBRARIES = ${ZLIB_LIBRARIES}")
  include_directories(${ZLIB_INCLUDE_DIRS})
endif (ZLIB_FOUND)

# Doxygen doc generator
find_package(Doxygen)
if(DOXYGEN_FOUND)
    configure_file(${CMAKE_CURRENT_SOURCE_DIR}/doc/Doxyfile.in ${CMAKE_CURRENT_BINARY_DIR}/doc/Doxyfile @ONLY)
    add_custom_target(doc
        ${DOXYGEN_EXECUTABLE} ${CMAKE_CURRENT_BINARY_DIR}/doc/Doxyfile
        WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
        COMMENT "Generating API documentation with Doxygen" VERBATIM
    )
endif(DOXYGEN_FOUND)

# Generate prototab.c/h
file(MAKE_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/src)
execute_process(COMMAND ${PERL_EXECUTABLE} "${CMAKE_CURRENT_SOURCE_DIR}/src/mkprototab.pl" "${CMAKE_CURRENT_BINARY_DIR}/src/prototab.c" "${CMAKE_CURRENT_BINARY_DIR}/src/prototab.h")

# Testing

add_executable(isprefix_test
    tests/isprefix_test.c src/isprefix.c)
    
add_test(NAME isprefix_test COMMAND isprefix_test)

add_executable(rollsum_test
    tests/rollsum_test.c src/rollsum.c)
add_test(NAME rollsum_test COMMAND rollsum_test)

# Disable rdiff specific tests
if (BUILD_RDIFF)
    add_test(NAME rdiff_bad_option
             COMMAND rdiff_bad_option.sh ${CMAKE_CURRENT_BINARY_DIR}
             WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/tests)
    
    add_test(NAME Help COMMAND help.test ${CMAKE_CURRENT_BINARY_DIR} WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/tests)
    
    add_test(NAME Mutate COMMAND mutate.test ${CMAKE_CURRENT_BINARY_DIR} WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/tests)
    add_test(NAME Signature COMMAND signature.test ${CMAKE_CURRENT_BINARY_DIR} WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/tests)
    add_test(NAME Sources COMMAND sources.test ${CMAKE_CURRENT_BINARY_DIR} WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/tests)
    add_test(NAME Triple COMMAND triple.test ${CMAKE_CURRENT_BINARY_DIR} WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/tests)
    add_test(NAME Delta COMMAND delta.test ${CMAKE_CURRENT_BINARY_DIR} WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/tests)
    add_test(NAME Changes COMMAND changes.test ${CMAKE_CURRENT_BINARY_DIR} WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/tests)
endif (BUILD_RDIFF)


# `make check` that will build everything and then run the tests.
# See https://cmake.org/Wiki/CMakeEmulateMakeCheck and
# https://github.com/librsync/librsync/issues/49
if (BUILD_RDIFF)
  set(LAST_TARGET rdiff)
else (BUILD_RDIFF)
  set(LAST_TARGET rsync)
endif (BUILD_RDIFF)
add_custom_target(check COMMAND ${CMAKE_CTEST_COMMAND})
add_dependencies(check ${LAST_TARGET} isprefix_test rollsum_test)


enable_testing()

# Create conf files
configure_file(${CMAKE_CURRENT_SOURCE_DIR}/src/config.h.cmake ${CMAKE_CURRENT_BINARY_DIR}/src/config.h)

configure_file(${CMAKE_CURRENT_SOURCE_DIR}/src/librsync-config.h.cmake ${CMAKE_CURRENT_BINARY_DIR}/src/librsync-config.h)


# We need to be able to #include "file" from a few places,
# * The original source dir
# * The generated source dir
include_directories(${CMAKE_CURRENT_BINARY_DIR}/src)
include_directories(${CMAKE_CURRENT_SOURCE_DIR}/src)




########### next target ###############

# Only list the .c files that need to be compiled
# (Don't list .h files)

set(rsync_LIB_SRCS
    # This was generated
    ${CMAKE_CURRENT_BINARY_DIR}/src/prototab.c
    src/base64.c
    src/buf.c
    src/checksum.c
    src/command.c
    src/delta.c
    src/emit.c
    src/fileutil.c
    src/hex.c
    src/job.c
    src/mdfour.c
    src/mksum.c
    src/msg.c
    src/netint.c
    src/patch.c
    src/readsums.c
    src/rollsum.c
    src/scoop.c
    src/search.c
    src/stats.c
    src/stream.c
    src/sumset.c
    src/trace.c
    src/tube.c
    src/util.c
    src/version.c
    src/whole.c
    src/blake2b-ref.c)

add_library(rsync SHARED ${rsync_LIB_SRCS})

# Optionally link zlib and bzip2 if
# - compression is enabled
# - and libraries are found
if (ENABLE_COMPRESSION)
  if (ZLIB_FOUND AND BZIP2_FOUND)
    target_link_libraries(rsync ${ZLIB_LIBRARIES} ${BZIP2_LIBRARIES})
  else (ZLIB_FOUND AND BZIP2_FOUND)
    message (WARNING "zlib and bzip2 librares are required to enable compression")
  endif (ZLIB_FOUND AND BZIP2_FOUND)
endif (ENABLE_COMPRESSION)

set_target_properties(rsync PROPERTIES VERSION ${LIBRSYNC_VERSION}
        SOVERSION ${LIBRSYNC_MAJOR_VERSION})
install(TARGETS rsync ${INSTALL_TARGETS_DEFAULT_ARGS} DESTINATION lib)


########### next target ###############

if (BUILD_RDIFF)
  set(rdiff_SRCS
      src/rdiff.c
      src/isprefix.c)

  add_executable(rdiff ${rdiff_SRCS})
  if (POPT_FOUND)
    target_link_libraries(rdiff rsync ${POPT_LIBRARIES})
  else (POPT_FOUND)
    message (WARNING "Popt library is required for rdiff target")
  endif (POPT_FOUND)

  install(TARGETS rdiff ${INSTALL_TARGETS_DEFAULT_ARGS} DESTINATION bin)
endif (BUILD_RDIFF)


########### install files ###############

install(FILES
        src/librsync.h
        ${CMAKE_CURRENT_BINARY_DIR}/src/librsync-config.h
        DESTINATION include)

message (STATUS "CMAKE_C_FLAGS  = ${CMAKE_C_FLAGS}")

# vim: shiftwidth=4 expandtab
