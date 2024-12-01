# Copyright 2002 Ben Escoto

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
import os
import shutil
import sys
import textwrap
import typing
import traceback

from rdiffbackup.singletons import consts, generics, specifics
from rdiffbackup.utils import safestr

if typing.TYPE_CHECKING:  # pragma: no cover
    from rdiff_backup import connection

# type definitions
Verbosity = typing.Literal[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]  # : typing.TypeAlias
InputVerbosity = typing.Union[int, str]  # : typing.TypeAlias
LogType = typing.Literal[0, 1, 2]  # : typing.TypeAlias
# Error type for recoverable single file errors
ErrorType = typing.Literal["ListError", "UpdateError", "SpecialFileError"]

# we need to define constants
NONE: typing.Final[Verbosity] = 0  # are always output as-is on stdout
ERROR: typing.Final[Verbosity] = 1
WARNING: typing.Final[Verbosity] = 2
NOTE: typing.Final[Verbosity] = 3
INFO: typing.Final[Verbosity] = 5
DEBUG: typing.Final[Verbosity] = 8
TIMESTAMP: typing.Final[Verbosity] = 9  # for adding the timestamp

# mapping from severity to prefix (must be less than 9 characters)
_LOG_PREFIX: dict[Verbosity, str] = {
    NONE: "",
    ERROR: "ERROR:",
    WARNING: "WARNING:",
    NOTE: "NOTE:",
    INFO: "*",
    DEBUG: "DEBUG:",
}

NORMAL: typing.Final[LogType] = 0
LOCAL: typing.Final[LogType] = 1
NOFILE: typing.Final[LogType] = 2


class LogWriter(typing.Protocol):  # pragma: no cover
    """Protocol representing a subset of io.BufferedWriter methods"""

    def write(self, buffer: bytes) -> int:
        """Write a buffer of bytes to the log, returns the number of written bytes"""
        ...

    def flush(self) -> None:
        """Flush the log"""
        ...

    def close(self) -> None:
        """Close the log"""
        ...


class Logger:
    """All functions which deal with logging"""

    log_writer: LogWriter
    log_file_conn: "connection.Connection"
    log_file_open: bool = False  # is the logfile open?
    log_file_local: bool = False  # is the logfile locally stored?
    # if something wrong happens during initialization, we want to know
    file_verbosity: Verbosity = NONE
    term_verbosity: Verbosity = WARNING
    # output is human readable by default, not parsable
    parsable: bool = False

    def __call__(self, message: str, verbosity: Verbosity) -> None:
        """
        Log message that has verbosity importance

        message can be a string or bytes
        """
        if verbosity > self.file_verbosity and verbosity > self.term_verbosity:
            return

        if verbosity <= self.file_verbosity and self.log_file_open:
            if self.log_file_local:
                self.log_to_file(message, verbosity)
            else:
                self.log_file_conn.log.Log.log_to_file(message, verbosity)
        if verbosity <= self.term_verbosity:
            self.log_to_term(message, verbosity)

    # @API(Log.log_to_file, 200)
    def log_to_file(self, message: str, verbosity: Verbosity) -> None:
        """Write the message to the log file, if possible"""
        tmpstr = self._format(message, self.file_verbosity, verbosity)
        self.log_writer.write(safestr.to_bytes(tmpstr))
        self.log_writer.flush()

    def log_to_term(self, message: str, verbosity: Verbosity) -> None:
        """Write message to stdout/stderr"""
        if verbosity in {ERROR, WARNING} or specifics.server:
            termfp = sys.stderr
        else:
            termfp = sys.stdout

        tmpstr = self._format(message, self.term_verbosity, verbosity)
        # if the verbosity is below 9 and the string isn't deemed
        # pre-formatted by newlines (we ignore the last character),
        # and neither verbosity is none, nor output is required to be parasable
        if (
            verbosity != NONE
            and not self.parsable
            and self.term_verbosity < DEBUG
            and "\n" not in tmpstr[:-1]
        ):
            termfp.write(
                textwrap.fill(
                    tmpstr,
                    subsequent_indent=" " * 9,
                    break_long_words=False,
                    break_on_hyphens=False,
                    width=shutil.get_terminal_size().columns - 1,
                )
                + "\n"
            )
        else:
            termfp.write(tmpstr)

    def conn(self, direction: str, result: typing.Any, req_num: int) -> None:
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
        # TODO shorten the result to a max size of 720 chars with ellipsis if needed
        # result_repr = result_repr[:720] + (result_repr[720:] and '[...]')  # noqa: E265
        if specifics.server:
            conn_str = "Server"
        else:
            conn_str = "Client"
        self.log_to_term(
            "{cs} {di} ({rn}): {rr}".format(
                cs=conn_str, di=direction, rn=req_num, rr=result_repr
            ),
            DEBUG,
        )

    def FatalError(self, message: str, return_code: int = 1) -> None:
        """Log a fatal error and exit"""
        self.log_to_term("Fatal Error: {em}".format(em=message), ERROR)
        sys.exit(return_code)

    def exception(
        self, log_type: LogType = NORMAL, verbosity: Verbosity = INFO
    ) -> None:
        """
        Log an exception and traceback

        If log_type is zero, log normally.
        If it is 1, then only log to file if log file is local
        If it is 2, don't log to file at all.
        """
        if log_type == NORMAL or (log_type == LOCAL and self.log_file_open):
            logging_func = self.__call__
        else:
            logging_func = self.log_to_term
            if verbosity >= self.term_verbosity:
                return

        exception_string = self._exception_to_string()
        try:
            logging_func(exception_string, verbosity)
        except OSError:
            sys.stderr.write(
                "OS error while trying to log exception!\n"
                "{ex}\n".format(ex=exception_string)
            )

    # @API(Log.set_verbosity, 300)
    def set_verbosity(
        self,
        file_verbosity: InputVerbosity,
        term_verbosity: typing.Optional[InputVerbosity] = None,
    ) -> int:
        """
        Set verbosity levels, logfile and terminal.  Takes numbers or strings.
        The function makes sure that verbosities are only modified if both
        input values are correct.
        If not provided, the terminal verbosity is set from the logfile one.
        Returns an integer code.
        """
        try:
            # we set a temporary verbosity to make sure we overwrite the
            # actual one only if both values are correct
            tmp_verbosity: Verbosity = self.validate_verbosity(file_verbosity)
            if term_verbosity is None:
                self.term_verbosity = tmp_verbosity
            else:
                self.term_verbosity = self.validate_verbosity(term_verbosity)
        except ValueError:
            return consts.RET_CODE_ERR
        else:
            self.file_verbosity = tmp_verbosity
            return consts.RET_CODE_OK

    # @API(Log.set_parsable, 300)
    def set_parsable(self, parsable: bool) -> int:
        """
        Function to set if the output logged should be parsable or not.
        Not parsable means more human readable.
        """
        self.parsable = parsable
        return consts.RET_CODE_OK

    def open_logfile(self, log_writer: LogWriter) -> None:
        """
        Inform all connections of an open logfile on the current connection.

        log_rp.conn will write to the file, and the others will pass
        write commands off to it.
        """
        assert not self.log_file_open, "Can't open an already opened logfile"
        self.log_writer = log_writer
        self.log_file_local = True
        self.log_file_open = True
        for conn in specifics.connections[1:]:
            conn.log.Log.open_logfile_local(specifics.local_connection)

    # @API(Log.open_logfile_local, 300)
    def open_logfile_local(self, log_file_conn: "connection.Connection") -> None:
        """Run on all connections to signal log file is open"""
        self.log_file_open = True
        self.log_file_conn = log_file_conn

    def close_logfile(self) -> None:
        """Close logfile locally if necessary and inform all connections"""
        if self.log_file_open:
            for conn in specifics.connections:
                conn.log.Log.close_logfile_local()
            self.log_writer.close()
            self.log_file_local = False

    # @API(Log.close_logfile_local, 300)
    def close_logfile_local(self) -> None:
        """Run on every connection"""
        self.log_file_open = False

    def _exception_to_string(self) -> str:
        """Return string version of current exception"""
        type, value, tb = sys.exc_info()
        s = "Exception '%s' raised of class '%s':\n%s" % (
            value,
            type,
            "".join(traceback.format_tb(tb)),
        )
        return s

    def _format(
        self, message: str, verbosity: Verbosity, msg_verbosity: Verbosity
    ) -> str:
        """Format the message, possibly adding date information"""
        if verbosity <= DEBUG:
            # pre-formatted informative messages are returned as such
            if msg_verbosity == NONE or (
                msg_verbosity == INFO and "\n" in message[:-1]
            ):
                return "{msg}\n".format(msg=message)
            else:
                return "{pre:<9}{msg}\n".format(
                    pre=_LOG_PREFIX[msg_verbosity], msg=message
                )
        else:
            timestamp = (
                datetime.datetime.now(datetime.timezone.utc)
                .astimezone()
                .strftime("%F %H:%M:%S.%f %z")
            )
            if specifics.server:
                role = "SERVER"
            else:
                role = "CLIENT"
            return "{time}  <{role}-{pid}>  {pre} {msg}\n".format(
                time=timestamp,
                role=role,
                pid=os.getpid(),
                pre=_LOG_PREFIX[msg_verbosity],
                msg=message,
            )

    @classmethod
    def validate_verbosity(cls, input_verbosity: InputVerbosity) -> Verbosity:
        """
        Validate verbosity and returns its value as integer.
        The input value can be a string or an integer, between 0 and 9.
        Any wrong value raises a ValueError exception.
        """
        try:
            verbosity = int(input_verbosity)
        except ValueError:
            Log(
                "Verbosity must be a number, received '{vb}' "
                "instead".format(vb=input_verbosity),
                ERROR,
            )
            raise ValueError
        if verbosity in typing.get_args(Verbosity):
            return typing.cast(Verbosity, verbosity)
        else:
            Log(
                "Verbosity must be between 0 and 9, received '{vb}' "
                "instead".format(vb=verbosity),
                ERROR,
            )
            raise ValueError


class ErrorLogger:
    """
    Log each recoverable error in error_log file

    There are three types of recoverable errors:  ListError, which
    happens trying to list a directory or stat a file, UpdateError,
    which happen when trying to update a changed file, and
    SpecialFileError, which happen when a special file cannot be
    created.  See the error policy file for more info.
    """

    log_writer: LogWriter
    log_file_open: bool = False  # is the logfile open?
    log_file_local: bool = False  # is the logfile locally stored?
    log_file_conn: "connection.Connection"

    def __call__(self, error_type: ErrorType, rp: typing.Any, exc: BaseException):
        """Write the message to the log file, if possible"""
        if self.log_file_open:
            if self.log_file_local:
                self.log_to_file(error_type, rp, exc)
            else:
                self.log_file_conn.log.ErrorLog.log_to_file(error_type, rp, exc)
        else:
            Log(self._get_log_string(error_type, rp, exc), WARNING)

    def open_logfile(self, log_writer: LogWriter) -> None:
        """
        Inform all connections of an open logfile on the current connection.

        log_rp.conn will write to the file, and the others will pass
        write commands off to it.
        """
        assert not self.log_file_open, "Can't open an already opened logfile"
        self.log_writer = log_writer
        self.log_file_local = True
        self.log_file_open = True
        for conn in specifics.connections[1:]:
            conn.log.ErrorLog.open_logfile_local(specifics.local_connection)

    # @API(ErrorLog.open_logfile_local, 300)
    def open_logfile_local(self, log_file_conn: "connection.Connection") -> None:
        """Run on all connections to signal log file is open"""
        self.log_file_open = True
        self.log_file_conn = log_file_conn

    def close_logfile(self) -> None:
        """Close logfile locally if necessary and inform all connections"""
        if self.log_file_open:
            for conn in specifics.connections:
                conn.log.ErrorLog.close_logfile_local()
            self.log_writer.close()
            self.log_file_local = False

    # @API(ErrorLog.close_logfile_local, 300)
    def close_logfile_local(self) -> None:
        """Run on every connection"""
        self.log_file_open = False

    # @API(ErrorLog.log_to_file, 300)
    def log_to_file(
        self, error_type: ErrorType, rp: typing.Any, exc: BaseException
    ) -> None:
        """Add line to log file indicating error exc with file rp"""
        logstr = self._get_log_string(error_type, rp, exc)
        Log(logstr, WARNING)
        if generics.null_separator:
            logstr += "\0"
        else:  # we want to keep everything on one single line
            logstr = logstr.replace("\n", " ")
            logstr += "\n"
        self.log_writer.write(safestr.to_bytes(logstr))

    def _get_log_string(
        self, error_type: ErrorType, rp: typing.Any, exc: BaseException
    ) -> str:
        """Return log string to put in error log"""
        return "{et}: '{rp}' {ex}".format(et=error_type, rp=rp, ex=exc)


# Create singletons
Log = Logger()
ErrorLog = ErrorLogger()
