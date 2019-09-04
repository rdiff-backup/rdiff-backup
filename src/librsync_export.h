#ifndef LIBRSYNC_EXPORT_H
#  define LIBRSYNC_EXPORT_H

#  ifdef LIBRSYNC_STATIC_DEFINE
#    define LIBRSYNC_EXPORT
#  else
#    ifdef _WIN32
#      ifdef rsync_EXPORTS
#        define LIBRSYNC_EXPORT __declspec(dllexport)
#      else
#        define LIBRSYNC_EXPORT __declspec(dllimport)
#      endif
#    else
#      define LIBRSYNC_EXPORT __attribute__((visibility("default")))
#    endif
#  endif

#endif                          /* LIBRSYNC_EXPORT_H */
