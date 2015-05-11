project(librsync)
cmake_minimum_required(VERSION 2.6)


set(LIBRSYNC_MAJOR_VERSION 1)
set(LIBRSYNC_MINOR_VERSION 0)
set(LIBRSYNC_PATCH_VERSION 0)

set(LIBRSYNC_VERSION
  ${LIBRSYNC_MAJOR_VERSION}.${LIBRSYNC_MINOR_VERSION}.${LIBRSYNC_PATCH_VERSION})

set(CMAKE_MODULE_PATH "${CMAKE_SOURCE_DIR}/cmake")

if (NOT CMAKE_SYSTEM_PROCESSOR)
	message(FATAL_ERROR "No target CPU architecture set")
endif()

if (NOT CMAKE_SYSTEM_NAME)
	message(FATAL_ERROR "No target OS set")
endif()

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

#!FIXME: is this really the best way to do it? I think the limitation on
# rs_long_t is that we need to be able to seek to it, which relates to
# long file support. With fseeko, rs_long_t should be off_t, otherwise
# it should be long.
if ( HAVE_SYS_TYPES_H AND LONG_LONG )
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

site_name(SITE_NAME)

message (STATUS "PROJECT_NAME  = ${PROJECT_NAME}")
message (STATUS "SITE_NAME  = ${SITE_NAME}")

# Find POPT
find_package(POPT REQUIRED)
if ( POPT_FOUND )
  include_directories(${POPT_INCLUDE_DIRS})
endif ( POPT_FOUND )

# Find BZIP
find_package (BZip2 REQUIRED)
if (BZIP2_FOUND)
  message (STATUS "Found components for BZIP2")
  message (STATUS "BZIP2_INCLUDE_DIR  = ${BZIP2_INCLUDE_DIR}")
  message (STATUS "BZIP_LIBRARIES = ${BZIP2_LIBRARIES}")
  include_directories(${BZIP2_INCLUDE_DIR})
endif (BZIP2_FOUND)

# Find Perl
find_package (Perl REQUIRED)
if (PERL_FOUND)
  message (STATUS "PERL_EXECUTABLE  = ${PERL_EXECUTABLE}")
endif (PERL_FOUND)

# Find ZLIB
find_package (ZLIB REQUIRED)
if (ZLIB_FOUND)
  message (STATUS "Found components for ZLIB")
  message (STATUS "BZIP2_INCLUDE_DIR  = ${ZLIB_INCLUDE_DIR}")
  message (STATUS "BZIP_LIBRARIES = ${ZLIB_LIBRARIES}")
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
execute_process(COMMAND ${PERL_EXECUTABLE} "${CMAKE_SOURCE_DIR}/src/mkprototab.pl" "${CMAKE_SOURCE_DIR}/src/prototab.c" "${CMAKE_SOURCE_DIR}/src/prototab.h")

# Testing
# build testsuite
add_subdirectory(tests)

add_test(NAME Help COMMAND help.test WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/tests)
add_test(NAME Isprefix COMMAND isprefix.test WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/tests)
add_test(NAME Mutate COMMAND mutate.test WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/tests)
add_test(NAME Signature COMMAND signature.test WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/tests)
add_test(NAME Sources COMMAND sources.test WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/tests)
add_test(NAME Triple COMMAND triple.test WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/tests)
add_test(NAME Delta COMMAND delta.test WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/tests)
add_test(NAME Changes COMMAND changes.test WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/tests)


enable_testing()

# Create conf files
configure_file(${CMAKE_CURRENT_SOURCE_DIR}/src/config.h.cmake ${CMAKE_CURRENT_SOURCE_DIR}/src/config.h)

configure_file(${CMAKE_CURRENT_SOURCE_DIR}/src/librsync-config.h.cmake ${CMAKE_CURRENT_SOURCE_DIR}/src/librsync-config.h)





########### next target ###############

set(rsync_LIB_SRCS
    src/prototab.c
    src/prototab.h
    src/base64.c
    src/buf.c
    src/buf.h
    src/config.h
    src/checksum.c
    src/checksum.h
    src/command.c
    src/command.h
    src/delta.c
    src/emit.c
    src/emit.h
    src/fileutil.c
    src/fileutil.h
    src/hex.c
    src/job.c
    src/job.h
    src/mdfour.c
    src/mdfour.h
    src/mksum.c
    src/msg.c
    src/netint.c
    src/netint.h
    src/patch.c
    src/readsums.c
    src/librsync.h
    src/librsync-config.h
    src/rollsum.c
    src/rollsum.h
    src/scoop.c
    src/search.c
    src/search.h
    src/stats.c
    src/stream.c
    src/stream.h
    src/sumset.c
    src/sumset.h
    src/trace.c
    src/trace.h
    src/tube.c
    src/types.h
    src/util.c
    src/util.h
    src/version.c
    src/whole.c
    src/whole.h
    src/snprintf.h
    src/blake2b-ref.c
    src/blake2.h
    src/blake2-impl.h)

add_library(rsync SHARED ${rsync_LIB_SRCS})

target_link_libraries(rsync
${BZIP2_LIBRARIES}
${ZLIB_LIBRARIES}
)

set_target_properties(rsync PROPERTIES VERSION 1.0.0 SOVERSION 1)
install(TARGETS rsync ${INSTALL_TARGETS_DEFAULT_ARGS} DESTINATION lib)


########### next target ###############

set(rdiff_SRCS
    src/rdiff.c
    src/isprefix.c
    src/isprefix.h
    src/librsync.h
    src/librsync-config.h
    src/trace.h)

add_executable(rdiff ${rdiff_SRCS})

target_link_libraries(rdiff rsync ${POPT_LIBRARIES})

install(TARGETS rdiff ${INSTALL_TARGETS_DEFAULT_ARGS} DESTINATION bin)


########### install files ###############

install(FILES  librsync.h librsync-config.h DESTINATION include)
