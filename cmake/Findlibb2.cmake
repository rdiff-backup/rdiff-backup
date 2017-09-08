# - Check for the presence of libb2
#
# The following variables are set when libb2 is found:
#  LIBB2_FOUND = Set to true, if all components of libb2 have been found.
#  LIBB2_INCLUDE_DIRS  = Include path for the header files of libb2.
#  LIBB2_LIBRARIES = Link these to use libb2.

find_path (LIBB2_INCLUDE_DIRS blake2.h)
find_library (LIBB2_LIBRARIES b2)

INCLUDE(FindPackageHandleStandardArgs)
FIND_PACKAGE_HANDLE_STANDARD_ARGS (LIBB2 DEFAULT_MSG LIBB2_LIBRARIES LIBB2_INCLUDE_DIRS)

mark_as_advanced (LIBB2_INCLUDE_DIRS LIBB2_LIBRARIES)
