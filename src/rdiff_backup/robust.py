# Copyright 2002 Ben Escoto
#
# This file is part of rdiff-backup.
#
# rdiff-backup is free software; you can redistribute it and/or modify
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.
#
# rdiff-backup is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with rdiff-backup; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA
"""Catch various exceptions given system call"""

import errno
import signal
import zlib
from . import librsync, C, rpath, Globals, log, connection


# Those are the signals we want to catch because they relate to conditions
# impacting only a single file, especially on remote file systems.
# We list first only the POSIX conform signals, present on all platforms.
_robust_errno_list = [errno.EPERM, errno.ENOENT, errno.EACCES, errno.EBUSY,
                      errno.EEXIST, errno.ENOTDIR, errno.EILSEQ, errno.EBADF,
                      errno.ENAMETOOLONG, errno.EINTR, errno.ESTALE,
                      errno.ENOTEMPTY, errno.EIO, errno.ETXTBSY,
                      errno.ESRCH, errno.EINVAL, errno.EDEADLK,
                      errno.EOPNOTSUPP, errno.ETIMEDOUT]
# Skip on resource deadlock only if the error is defined (_not_ on MacOSX)
if hasattr(errno, 'EDEADLOCK'):
    _robust_errno_list.append(errno.EDEADLOCK)


class SignalException(Exception):
    """SignalException(signum) means signal signum has been received"""
    pass


# @API(install_signal_handlers, 200)
def install_signal_handlers():
    """Install signal handlers on current connection"""
    signals = [signal.SIGTERM, signal.SIGINT]
    try:
        signals.extend([signal.SIGHUP, signal.SIGQUIT])
    except AttributeError:
        pass
    for signum in signals:
        signal.signal(signum, _signal_handler)


def get_error_handler(error_type):
    """Return error handler function that can be used above

    Function will just log error to the error_log and then return
    None.  First two arguments must be the exception and then an rp
    (from which the filename will be extracted).

    """

    def error_handler(exc, rp, *args):
        log.ErrorLog.write_if_open(error_type, rp, exc)
        return 0

    return error_handler


def listrp(rp):
    """Like rp.listdir() but return [] if error, and sort results"""

    def error_handler(exc):
        log.Log("Failed listing directory {di}".format(di=rp), log.WARNING)
        return []

    dir_listing = check_common_error(error_handler, rp.listdir)
    dir_listing.sort()
    return dir_listing


def check_common_error(error_handler, function, args=[]):
    """Apply function to args, if error, run error_handler on exception

    This uses the catch_error predicate below to only catch
    certain exceptions which seems innocent enough.

    """
    try:
        return function(*args)
    except (Exception, KeyboardInterrupt, SystemExit) as exc:
        if catch_error(exc):
            log.Log.exception()
            conn = Globals.backup_writer
            if conn is not None:
                conn.statistics.record_error()
            if error_handler:
                return error_handler(exc, *args)
            else:
                return None
        if is_routine_fatal(exc):
            log.Log.exception(1, log.INFO)
        else:
            log.Log.exception(1, log.WARNING)
        raise


def catch_error(exc):
    """
    Return True if exception exc should be caught, else False.
    """
    if isinstance(exc, (rpath.SkipFileException, rpath.RPathException,
                        librsync.librsyncError, C.UnknownFileTypeError,
                        zlib.error)):
        return True
    if (isinstance(exc, OSError)
            # the invalid mode shows up in backups of /proc for some reason
            and ('invalid mode: rb' in str(exc)
                 or 'Not a gzipped file' in str(exc)
                 or exc.errno in _robust_errno_list)):
        return True
    return False


def is_routine_fatal(exc):
    """Return string if exception is non-error unrecoverable, None otherwise

    Used to suppress a stack trace for exceptions like keyboard
    interrupts or connection drops.  Return value is string to use as
    an exit message.

    """
    if isinstance(exc, KeyboardInterrupt):
        return "User abort"
    elif isinstance(exc, connection.ConnectionError):
        return "Lost connection to the remote system"
    elif isinstance(exc, SignalException):
        return "Killed with signal %s" % (exc, )
    elif isinstance(exc, OSError) and exc.errno == errno.ENOTCONN:
        return ("Filesystem reports connection failure:\n%s" % exc)
    return None


def _signal_handler(signum, frame):
    """This is called when signal signum is caught"""
    raise SignalException(signum)
