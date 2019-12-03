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
"""Manage logging, displaying and recording messages with required verbosity"""

import datetime
import sys
import traceback
import types
import re
import os  # needed to grab verbosity as environment variable
from . import Globals, rpath


class LoggerError(Exception):
    pass


class Logger:
    """All functions which deal with logging"""

    def __init__(self):
        self.log_file_open = None
        self.log_file_local = None
        self.verbosity = self.term_verbosity = int(
            os.getenv('RDIFF_BACKUP_VERBOSITY', '3'))
        # termverbset is true if the term_verbosity has been explicitly set
        self.termverbset = None

    def setverbosity(self, verbosity_string):
        """Set verbosity levels.  Takes a number string"""
        try:
            self.verbosity = int(verbosity_string)
        except ValueError:
            Log.FatalError("Verbosity must be a number, received '%s' "
                           "instead." % verbosity_string)
        if not self.termverbset:
            self.term_verbosity = self.verbosity

    def setterm_verbosity(self, termverb_string):
        """Set verbosity to terminal.  Takes a number string"""
        try:
            self.term_verbosity = int(termverb_string)
        except ValueError:
            Log.FatalError("Terminal verbosity must be a number, received "
                           "'%s' instead." % termverb_string)
        self.termverbset = 1

    def open_logfile(self, rpath):
        """Inform all connections of an open logfile.

        rpath.conn will write to the file, and the others will pass
        write commands off to it.

        """
        assert not self.log_file_open
        rpath.conn.log.Log.open_logfile_local(rpath)
        for conn in Globals.connections:
            conn.log.Log.open_logfile_allconn(rpath.conn)

    def open_logfile_allconn(self, log_file_conn):
        """Run on all connections to signal log file is open"""
        self.log_file_open = 1
        self.log_file_conn = log_file_conn

    def open_logfile_local(self, rpath):
        """Open logfile locally - should only be run on one connection"""
        assert rpath.conn is Globals.local_connection
        try:
            self.logfp = rpath.open("a")
        except (OSError, IOError) as e:
            raise LoggerError(
                "Unable to open logfile %s: %s" % (rpath.path, e))
        self.log_file_local = 1
        self.logrp = rpath

    def close_logfile(self):
        """Close logfile and inform all connections"""
        if self.log_file_open:
            for conn in Globals.connections:
                conn.log.Log.close_logfile_allconn()
            self.log_file_conn.log.Log.close_logfile_local()

    def close_logfile_allconn(self):
        """Run on every connection"""
        self.log_file_open = None

    def close_logfile_local(self):
        """Run by logging connection - close logfile"""
        assert self.log_file_conn is Globals.local_connection
        assert not self.logfp.close()
        self.log_file_local = None

    def format(self, message, verbosity):
        """Format the message, possibly adding date information"""
        if verbosity < 9:
            return "%s\n" % message
        else:
            timestamp = datetime.datetime.now(
                datetime.timezone.utc).astimezone().strftime(
                    "%F %H:%M:%S.%f %z")
            if Globals.server:
                role = "SERVER"
            else:
                role = "CLIENT"
            return "%s  <%s-%d>  %s\n" % (timestamp, role, os.getpid(), message)

    def __call__(self, message, verbosity):
        """Log message that has verbosity importance

        message can be a string, which is logged as-is, or a function,
        which is then called and should return the string to be
        logged.  We do it this way in case producing the string would
        take a significant amount of CPU.

        """
        if verbosity > self.verbosity and verbosity > self.term_verbosity:
            return

        if not isinstance(message, (bytes, str)):
            assert isinstance(message, types.FunctionType)
            message = message()

        if verbosity <= self.verbosity:
            self.log_to_file(message)
        if verbosity <= self.term_verbosity:
            self.log_to_term(message, verbosity)

    def log_to_file(self, message):
        """Write the message to the log file, if possible"""
        if self.log_file_open:
            if self.log_file_local:
                tmpstr = self.format(message, self.verbosity)
                if type(tmpstr) != str:  # transform bytes into string
                    tmpstr = str(tmpstr, 'utf-8')
                self.logfp.write(tmpstr)
                self.logfp.flush()
            else:
                self.log_file_conn.log.Log.log_to_file(message)

    def log_to_term(self, message, verbosity):
        """Write message to stdout/stderr"""
        if verbosity <= 2 or Globals.server:
            termfp = sys.stderr
        else:
            termfp = sys.stdout
        tmpstr = self.format(message, self.term_verbosity)
        if type(tmpstr) != str:  # transform bytes in string
            tmpstr = str(tmpstr, 'utf-8')
        termfp.write(tmpstr)

    def conn(self, direction, result, req_num):
        """Log some data on the connection

        The main worry with this function is that something in here
        will create more network traffic, which will spiral to
        infinite regress.  So, for instance, logging must only be done
        to the terminal, because otherwise the log file may be remote.

        """
        if self.term_verbosity < 9:
            return
        if type(result) is bytes:
            result_repr = repr(result)
        else:
            result_repr = str(result)
        # shorten the result to a max size of 720 chars with ellipsis if needed
        #result_repr = result_repr[:720] + (result_repr[720:] and '[...]')  # noqa: E265
        if Globals.server:
            conn_str = "Server"
        else:
            conn_str = "Client"
        self.log_to_term(
            "%s %s (%d): %s" % (conn_str, direction, req_num, result_repr), 9)

    def FatalError(self, message, no_fatal_message=0, errlevel=1):
        """Log a fatal error and exit"""
        assert no_fatal_message == 0 or no_fatal_message == 1
        if no_fatal_message:
            prefix_string = ""
        else:
            prefix_string = "Fatal Error: "
        self.log_to_term(prefix_string + message, 1)
        sys.exit(errlevel)

    def exception_to_string(self, arglist=[]):
        """Return string version of current exception plus what's in arglist"""
        type, value, tb = sys.exc_info()
        s = ("Exception '%s' raised of class '%s':\n%s" %
             (value, type, "".join(traceback.format_tb(tb))))
        if arglist:
            s += "__Arguments:"
            for arg in arglist:
                s += "\n"
                try:
                    s += str(arg)
                except UnicodeError:
                    s += str(arg).encode('ascii', 'replace')
        return s

    def exception(self, only_terminal=0, verbosity=5):
        """Log an exception and traceback

        If only_terminal is None, log normally.  If it is 1, then only
        log to disk if log file is local (self.log_file_open = 1).  If
        it is 2, don't log to disk at all.

        """
        assert only_terminal in (0, 1, 2)
        if (only_terminal == 0 or (only_terminal == 1 and self.log_file_open)):
            logging_func = self.__call__
        else:
            logging_func = self.log_to_term
            if verbosity >= self.term_verbosity:
                return

        exception_string = self.exception_to_string()
        try:
            logging_func(exception_string, verbosity)
        except IOError:
            print("IOError while trying to log exception!")
            print(exception_string)


Log = Logger()


class ErrorLog:
    """Log each recoverable error in error_log file

    There are three types of recoverable errors:  ListError, which
    happens trying to list a directory or stat a file, UpdateError,
    which happen when trying to update a changed file, and
    SpecialFileError, which happen when a special file cannot be
    created.  See the error policy file for more info.

    """
    _log_fileobj = None

    @classmethod
    def open(cls, time_string, compress=1):
        """Open the error log, prepare for writing"""
        if not Globals.isbackup_writer:
            return Globals.backup_writer.log.ErrorLog.open(
                time_string, compress)
        assert not cls._log_fileobj, "log already open"
        assert Globals.isbackup_writer

        base_rp = Globals.rbdir.append("error_log.%s.data" % (time_string, ))
        if compress:
            cls._log_fileobj = rpath.MaybeGzip(base_rp)
        else:
            cls._log_fileobj = base_rp.open("wb", compress=0)

    @classmethod
    def isopen(cls):
        """True if the error log file is currently open"""
        if Globals.isbackup_writer or not Globals.backup_writer:
            return cls._log_fileobj is not None
        else:
            return Globals.backup_writer.log.ErrorLog.isopen()

    @classmethod
    def write(cls, error_type, rp, exc):
        """Add line to log file indicating error exc with file rp"""
        if not Globals.isbackup_writer:
            return Globals.backup_writer.log.ErrorLog.write(
                error_type, rp, exc)
        logstr = cls.get_log_string(error_type, rp, exc)
        Log(logstr, 2)
        if isinstance(logstr, bytes):
            logstr = logstr.decode('utf-8')
        if Globals.null_separator:
            logstr += "\0"
        else:
            logstr = re.sub("\n", " ", logstr)
            logstr += "\n"
        cls._log_fileobj.write(logstr)

    @classmethod
    def get_indexpath(cls, obj):
        """Return filename for logging.  rp is a rpath, string, or tuple"""
        try:
            return obj.get_safeindexpath()
        except AttributeError:
            if type(obj) is tuple:
                return "/".join(obj)
            else:
                return repr(obj)

    @classmethod
    def write_if_open(cls, error_type, rp, exc):
        """Call cls.write(...) if error log open, only log otherwise"""
        if not Globals.isbackup_writer and Globals.backup_writer:
            return Globals.backup_writer.log.ErrorLog.write_if_open(
                error_type, rp, exc)
        if cls.isopen():
            cls.write(error_type, rp, exc)
        else:
            Log(cls.get_log_string(error_type, rp, exc), 2)

    @classmethod
    def get_log_string(cls, error_type, rp, exc):
        """Return log string to put in error log"""
        assert (error_type == "ListError" or error_type == "UpdateError"
                or error_type == "SpecialFileError"), "Unknown type " + error_type
        return "%s: '%s' %s" % (error_type, cls.get_indexpath(rp), exc)

    @classmethod
    def close(cls):
        """Close the error log file"""
        if not Globals.isbackup_writer:
            return Globals.backup_writer.log.ErrorLog.close()
        assert not cls._log_fileobj.close()
        cls._log_fileobj = None
