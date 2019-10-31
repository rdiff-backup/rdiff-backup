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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
# USA
"""Catch various exceptions given system call"""

import errno
import signal
import zlib
from . import librsync, C, rpath, Globals, log, connection


def check_common_error(error_handler, function, args=[]):
    """Apply function to args, if error, run error_handler on exception

    This uses the catch_error predicate below to only catch
    certain exceptions which seems innocent enough.

    """
    try:
        return function(*args)
    except (Exception, KeyboardInterrupt, SystemExit) as exc:
        TracebackArchive.add([function] + list(args))
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
            log.Log.exception(1, 6)
        else:
            log.Log.exception(1, 2)
        raise


def catch_error(exc):
    """Return true if exception exc should be caught"""
    for exception_class in (rpath.SkipFileException, rpath.RPathException,
                            librsync.librsyncError, C.UnknownFileTypeError,
                            zlib.error):
        if isinstance(exc, exception_class):
            return 1
    if (isinstance(exc, EnvironmentError)
            # the invalid mode shows up in backups of /proc for some reason
        and ('invalid mode: rb' in str(exc) or 'Not a gzipped file' in str(exc)
        or exc.errno in (errno.EPERM, errno.ENOENT, errno.EACCES, errno.EBUSY,
                         errno.EEXIST, errno.ENOTDIR, errno.EILSEQ,
                         errno.ENAMETOOLONG, errno.EINTR, errno.ESTALE,
                         errno.ENOTEMPTY, errno.EIO, errno.ETXTBSY,
                         errno.ESRCH, errno.EINVAL, errno.EDEADLOCK,
                         errno.EDEADLK, errno.EOPNOTSUPP, errno.ETIMEDOUT))):
        return 1
    return 0


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
    elif isinstance(exc, EnvironmentError) and exc.errno == errno.ENOTCONN:
        return ("Filesystem reports connection failure:\n%s" % exc)
    return None


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
        log.Log("Error listing directory %s" % rp.get_safepath(), 2)
        return []

    dir_listing = check_common_error(error_handler, rp.listdir)
    dir_listing.sort()
    return dir_listing


def signal_handler(signum, frame):
    """This is called when signal signum is caught"""
    raise SignalException(signum)


def install_signal_handlers():
    """Install signal handlers on current connection"""
    signals = [signal.SIGTERM, signal.SIGINT]
    try:
        signals.extend([signal.SIGHUP, signal.SIGQUIT])
    except AttributeError:
        pass
    for signum in signals:
        signal.signal(signum, signal_handler)


class SignalException(Exception):
    """SignalException(signum) means signal signum has been received"""
    pass


class TracebackArchive:
    """Save last 10 caught exceptions, so they can be printed if fatal"""
    _traceback_strings = []

    @classmethod
    def add(cls, extra_args=[]):
        """Add most recent exception to archived list

        If extra_args are present, convert to strings and add them as
        extra information to same traceback archive.

        """
        cls._traceback_strings.append(log.Log.exception_to_string(extra_args))
        if len(cls._traceback_strings) > 10:
            cls._traceback_strings = cls._traceback_strings[:10]

    @classmethod
    def log(cls):
        """Print all exception information to log file"""
        if cls._traceback_strings:
            log.Log(
                "------------ Old traceback info -----------\n%s\n"
                "-------------------------------------------" % ("\n".join(
                    cls._traceback_strings), ), 3)
