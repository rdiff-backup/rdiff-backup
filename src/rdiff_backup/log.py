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
"""Manage logging, displaying and recording messages with required verbosity"""

import datetime
import os  # needed to grab verbosity as environment variable
import re
import shutil
import sys
import textwrap
import traceback
from rdiff_backup import Globals

LOGFILE_ENCODING = 'utf-8'

# we need to define constants
ERROR = 1
WARNING = 2
NOTE = 3
INFO = 5
DEBUG = 8  # we reserve 9 for adding the timestamp

# mapping from severity to prefix (must be less than 9 characters)
_LOG_PREFIX = {
    1: "ERROR:",
    2: "WARNING:",
    3: "NOTE:",
    5: "*",
    8: "DEBUG:",
}


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

    def __call__(self, message, verbosity):
        """
        Log message that has verbosity importance

        message can be a string or bytes
        """
        if verbosity > self.verbosity and verbosity > self.term_verbosity:
            return

        if not isinstance(message, (bytes, str)):
            raise TypeError(
                "You can only log bytes or str, and not {lt}".format(
                    lt=type(message)))

        if Globals.get_api_version() < 201:  # compat200
            message = "{pre} {msg}".format(pre=_LOG_PREFIX[verbosity],
                                           msg=message)
        if verbosity <= self.verbosity:
            self.log_to_file(message, verbosity)
        if verbosity <= self.term_verbosity:
            self.log_to_term(message, verbosity)

    # @API(Log.log_to_file, 200)
    def log_to_file(self, message, verbosity=None):
        """Write the message to the log file, if possible"""
        if self.log_file_open:
            if self.log_file_local:
                if Globals.get_api_version() < 201:
                    tmpstr = self._format(message, self.verbosity)
                    self.logfp.write(_to_bytes(tmpstr))
                else:
                    tmpstr = self._format(message, self.verbosity, verbosity)
                    self.logfp.write(_to_bytes(tmpstr))
                self.logfp.flush()
            else:
                if Globals.get_api_version() < 201:  # compat200
                    self.log_file_conn.log.Log.log_to_file(message)
                else:
                    self.log_file_conn.log.Log.log_to_file(message, verbosity)

    def log_to_term(self, message, verbosity):
        """Write message to stdout/stderr"""
        if verbosity <= 2 or Globals.server:
            termfp = sys.stderr
        else:
            termfp = sys.stdout
        if Globals.get_api_version() < 201:  # compat200
            tmpstr = self._format(message, self.term_verbosity)
            termfp.write(tmpstr)
        else:
            tmpstr = self._format(message, self.term_verbosity, verbosity)
            # if the verbosity is below 9 and the string isn't deemed
            # pre-formatted by newlines (we ignore the last character)
            if self.verbosity <= DEBUG and "\n" not in tmpstr[:-1]:
                termfp.write(
                    textwrap.fill(
                        tmpstr, subsequent_indent=" " * 9,
                        break_long_words=False,
                        break_on_hyphens=False,
                        width=shutil.get_terminal_size().columns - 1) + "\n")
            else:
                termfp.write(tmpstr)

    def conn(self, direction, result, req_num):
        """Log some data on the connection

        The main worry with this function is that something in here
        will create more network traffic, which will spiral to
        infinite regress.  So, for instance, logging must only be done
        to the terminal, because otherwise the log file may be remote.

        """
        if self.term_verbosity <= DEBUG:
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
        self.log_to_term("{cs} {di} ({rn}): {rr}".format(
            cs=conn_str, di=direction, rn=req_num, rr=result_repr), DEBUG)

    def FatalError(self, message, return_code=1):
        """Log a fatal error and exit"""
        self.log_to_term("Fatal Error: {em}".format(em=message), ERROR)
        sys.exit(return_code)

    def exception(self, only_terminal=0, verbosity=INFO):
        """Log an exception and traceback

        If only_terminal is zero, log normally.
        If it is 1, then only log to disk if log file is local
        If it is 2, don't log to disk at all.
        """
        assert only_terminal in (0, 1, 2), (
            "Variable only_terminal '{ot}' must be one of [012]".format(
                ot=only_terminal))
        if (only_terminal == 0 or (only_terminal == 1 and self.log_file_open)):
            logging_func = self.__call__
        else:
            logging_func = self.log_to_term
            if verbosity >= self.term_verbosity:
                return

        exception_string = self._exception_to_string()
        try:
            logging_func(exception_string, verbosity)
        except OSError:
            print("OS error while trying to log exception!")
            print(exception_string)

    # @API(Log.setverbosity, 200)
    def setverbosity(self, verbosity_string):
        """Set verbosity levels.  Takes a number string"""
        try:
            self.verbosity = int(verbosity_string)
        except ValueError:
            Log.FatalError("Verbosity must be a number, received '{vs}' "
                           "instead".format(vs=verbosity_string))
        if not self.termverbset:
            self.term_verbosity = self.verbosity

    # @API(Log.setterm_verbosity, 200)
    def setterm_verbosity(self, termverb_string):
        """Set verbosity to terminal.  Takes a number string"""
        try:
            self.term_verbosity = int(termverb_string)
        except ValueError:
            Log.FatalError("Terminal verbosity must be a number, received "
                           "'{tv}' instead".format(tv=termverb_string))
        self.termverbset = 1

    def open_logfile(self, log_rp):
        """Inform all connections of an open logfile.

        log_rp.conn will write to the file, and the others will pass
        write commands off to it.

        """
        assert not self.log_file_open, "Can't open an already opened logfile"
        log_rp.conn.log.Log.open_logfile_local(log_rp)
        for conn in Globals.connections:
            conn.log.Log.open_logfile_allconn(log_rp.conn)

    # @API(Log.open_logfile_allconn, 200)
    def open_logfile_allconn(self, log_file_conn):
        """Run on all connections to signal log file is open"""
        self.log_file_open = 1
        self.log_file_conn = log_file_conn

    # @API(Log.open_logfile_local, 200)
    def open_logfile_local(self, log_rp):
        """Open logfile locally - should only be run on one connection"""
        assert log_rp.conn is Globals.local_connection, (
            "Action only foreseen locally and not over {conn}".format(
                conn=log_rp.conn))
        try:
            self.logfp = log_rp.open("ab")
        except OSError as exc:
            raise LoggerError("Unable to open logfile {lf} due to "
                              "exception '{ex}'".format(lf=log_rp, ex=exc))
        self.log_file_local = 1

    def close_logfile(self):
        """Close logfile and inform all connections"""
        if self.log_file_open:
            for conn in Globals.connections:
                conn.log.Log.close_logfile_allconn()
            self.log_file_conn.log.Log.close_logfile_local()

    # @API(Log.close_logfile_allconn, 200)
    def close_logfile_allconn(self):
        """Run on every connection"""
        self.log_file_open = None

    # @API(Log.close_logfile_local, 200)
    def close_logfile_local(self):
        """Run by logging connection - close logfile"""
        assert self.log_file_conn is Globals.local_connection, (
            "Action only foreseen locally and not over {lc}".format(
                lc=self.log_file_conn))
        self.logfp.close()
        self.log_file_local = None

    def _exception_to_string(self):
        """Return string version of current exception"""
        type, value, tb = sys.exc_info()
        s = ("Exception '%s' raised of class '%s':\n%s" %
             (value, type, "".join(traceback.format_tb(tb))))
        return s

    def _format(self, message, verbosity, msg_verbosity=None):
        """Format the message, possibly adding date information"""
        if verbosity <= DEBUG:
            if msg_verbosity:
                # pre-formatted informative messages are returned as such
                if msg_verbosity == INFO and "\n" in message[:-1]:
                    return "{msg}\n".format(msg=message)
                else:
                    return "{pre:<9}{msg}\n".format(
                        pre=_LOG_PREFIX[msg_verbosity], msg=message)
            else:  # compat200
                return "{msg}\n".format(msg=message)
        else:
            timestamp = datetime.datetime.now(
                datetime.timezone.utc).astimezone().strftime(
                    "%F %H:%M:%S.%f %z")
            if Globals.server:
                role = "SERVER"
            else:
                role = "CLIENT"
            if msg_verbosity:
                return "{time}  <{role}-{pid}>  {pre} {msg}\n".format(
                    time=timestamp, role=role, pid=os.getpid(),
                    pre=_LOG_PREFIX[msg_verbosity], msg=message)
            else:  # compat200
                return "{time}  <{role}-{pid}>  {msg}\n".format(
                    time=timestamp, role=role, pid=os.getpid(), msg=message)


Log = Logger()


class ErrorLog:
    """
    Log each recoverable error in error_log file

    There are three types of recoverable errors:  ListError, which
    happens trying to list a directory or stat a file, UpdateError,
    which happen when trying to update a changed file, and
    SpecialFileError, which happen when a special file cannot be
    created.  See the error policy file for more info.
    """
    _log_fileobj = None

    @classmethod
    # @API(ErrorLog.open, 200)
    def open(cls, time_string, compress=1):
        """Open the error log, prepare for writing"""
        if not Globals.isbackup_writer:
            return Globals.backup_writer.log.ErrorLog.open(
                time_string, compress)
        assert not cls._log_fileobj, "Log already open, can't be reopened"

        base_rp = Globals.rbdir.append("error_log.%s.data" % time_string)
        if compress:
            from . import rpath
            cls._log_fileobj = rpath.MaybeGzip(base_rp)
        else:
            cls._log_fileobj = base_rp.open("wb", compress=0)

    @classmethod
    # @API(ErrorLog.isopen, 200)
    def isopen(cls):
        """True if the error log file is currently open"""
        if Globals.isbackup_writer or not Globals.backup_writer:
            return cls._log_fileobj is not None
        else:
            return Globals.backup_writer.log.ErrorLog.isopen()

    @classmethod
    # @API(ErrorLog.write_if_open, 200)
    def write_if_open(cls, error_type, rp, exc):
        """Call cls._write(...) if error log open, only log otherwise"""
        if not Globals.isbackup_writer and Globals.backup_writer:
            return Globals.backup_writer.log.ErrorLog.write_if_open(
                error_type, rp, exc)
        if cls.isopen():
            cls._write(error_type, rp, exc)
        else:
            Log(cls._get_log_string(error_type, rp, exc), WARNING)

    @classmethod
    # @API(ErrorLog.close, 200)
    def close(cls):
        """Close the error log file"""
        if cls.isopen():
            if not Globals.isbackup_writer:
                return Globals.backup_writer.log.ErrorLog.close()
            cls._log_fileobj.close()
            cls._log_fileobj = None

    @classmethod
    def _get_log_string(cls, error_type, rp, exc):
        """Return log string to put in error log"""
        assert (error_type == "ListError" or error_type == "UpdateError"
                or error_type == "SpecialFileError"), (
            "Unknown error type {et}".format(et=error_type))
        return "{et}: '{rp}' {ex}".format(et=error_type, rp=rp, ex=exc)

    @classmethod
    def _write(cls, error_type, rp, exc):
        """Add line to log file indicating error exc with file rp"""
        logstr = cls._get_log_string(error_type, rp, exc)
        Log(logstr, WARNING)
        if Globals.null_separator:
            logstr += "\0"
        else:
            logstr = re.sub("\n", " ", logstr)
            logstr += "\n"
        cls._log_fileobj.write(_to_bytes(logstr))


def _to_bytes(logline, encoding=LOGFILE_ENCODING):
    """
    Convert string into bytes for logging into file.
    """
    assert logline, "There must be a text to encode"
    assert isinstance(logline, str), (
        "Text to encode must be str and not {lt}".format(lt=type(logline)))
    return logline.encode(encoding, 'backslashreplace')
