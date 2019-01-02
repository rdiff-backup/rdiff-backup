
#--------------------------------------------------------------------------------
# Copyright (C) 2012-2013, Lars Baehren <lbaehren@gmail.com>
# Copyright (C) 2015 Adam Schubert <adam.schubert@sg1-game.net>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#--------------------------------------------------------------------------------

# - Check for the presence of POPT
#
# The following variables are set when POPT is found:
#  POPT_FOUND      = Set to true, if all components of POPT have been found.
#  POPT_INCLUDE_DIRS   = Include path for the header files of POPT
#  POPT_LIBRARIES  = Link these to use POPT
#  POPT_LFLAGS     = Linker flags (optional)


INCLUDE(FindPackageHandleStandardArgs)
if (NOT POPT_FOUND)

  if (NOT POPT_ROOT_DIR)
    set (POPT_ROOT_DIR ${CMAKE_INSTALL_PREFIX})
  endif (NOT POPT_ROOT_DIR)

  ##_____________________________________________________________________________
  ## Check for the header files

  find_path (POPT_INCLUDE_DIRS popt.h
    HINTS ${POPT_ROOT_DIR} ${CMAKE_INSTALL_PREFIX} $ENV{programfiles}\\GnuWin32 $ENV{programfiles32}\\GnuWin32
    PATH_SUFFIXES include
    )

  ##_____________________________________________________________________________
  ## Check for the library

  find_library (POPT_LIBRARIES popt
    HINTS ${POPT_ROOT_DIR} ${CMAKE_INSTALL_PREFIX} $ENV{programfiles}\\GnuWin32 $ENV{programfiles32}\\GnuWin32
    PATH_SUFFIXES lib
    )

  ##_____________________________________________________________________________
  ## Actions taken when all components have been found

  FIND_PACKAGE_HANDLE_STANDARD_ARGS (POPT DEFAULT_MSG POPT_LIBRARIES POPT_INCLUDE_DIRS)

  if (POPT_FOUND)
    if (NOT POPT_FIND_QUIETLY)
      message (STATUS "Found components for POPT")
      message (STATUS "POPT_ROOT_DIR  = ${POPT_ROOT_DIR}")
      message (STATUS "POPT_INCLUDE_DIRS  = ${POPT_INCLUDE_DIRS}")
      message (STATUS "POPT_LIBRARIES = ${POPT_LIBRARIES}")
    endif (NOT POPT_FIND_QUIETLY)
  else (POPT_FOUND)
    if (POPT_FIND_REQUIRED)
      message (FATAL_ERROR "Could not find POPT!")
    endif (POPT_FIND_REQUIRED)
  endif (POPT_FOUND)

  ##_____________________________________________________________________________
  ## Mark advanced variables

  mark_as_advanced (
    POPT_ROOT_DIR
    POPT_INCLUDE_DIRS
    POPT_LIBRARIES
    )

endif (NOT POPT_FOUND)
