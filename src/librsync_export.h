#ifndef LIBRSYNC_EXPORT_H
#  define LIBRSYNC_EXPORT_H

#  ifdef _WIN32
#    ifdef rsync_EXPORTS
#      define LIBRSYNC_EXPORT __declspec(dllexport)
#    else
#      define LIBRSYNC_EXPORT __declspec(dllimport)
#    endif
#  else
#    define LIBRSYNC_EXPORT __attribute__((visibility("default")))
#  endif

#endif                          /* LIBRSYNC_EXPORT_H */
