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
"""Generate and process aggregated backup session information"""

import time
import typing

from rdiff_backup import Time
from rdiffbackup.singletons import generics, specifics
from rdiffbackup.utils import convert, buffer, quoting

_active_statfileobj = None

if typing.TYPE_CHECKING:  # pragma: no cover
    from rdiff_backup import rpath

# workaround until we don't need to support Python lower than 3.11
try:
    from typing import Self  # type: ignore
except ImportError:  # pragma: no cover
    try:
        from typing_extensions import Self
    except (ModuleNotFoundError, ImportError):
        # it works because Self is only used in one class
        Self = typing.TypeVar("Self", bound="SessionStatsCalc")  # type: ignore


class SessionStatsWriter(typing.Protocol):  # pragma: no cover
    """Protocol representing a subset of io.BufferedWriter methods"""

    def write(self, buffer: str) -> int:
        """Write a string buffer to the stats, returns the number of written bytes"""
        ...

    def close(self) -> None:
        """Close the stats writer"""
        ...

    def flush(self) -> None:
        """Flush the stats writer"""
        ...


class SessionStatsReader(typing.Protocol):  # pragma: no cover
    """Protocol representing a subset of io.BufferedReader methods"""

    def read(self, size: int = -1) -> str:
        """Read a string from the file and return it"""
        ...

    def close(self) -> None:
        """Close the stats reader"""
        ...


class StatsException(Exception):
    pass


class SessionStatsCalc:
    """Contains various statistics, provide string conversion functions"""

    # Because we use the same object to average, we can have floats for sizes
    SourceFiles: typing.Optional[float] = None
    SourceFileSize: typing.Optional[float] = None
    MirrorFiles: typing.Optional[float] = None
    MirrorFileSize: typing.Optional[float] = None
    NewFiles: typing.Optional[float] = None
    NewFileSize: typing.Optional[float] = None
    DeletedFiles: typing.Optional[float] = None
    DeletedFileSize: typing.Optional[float] = None
    ChangedFiles: typing.Optional[float] = None
    ChangedSourceSize: typing.Optional[float] = None
    ChangedMirrorSize: typing.Optional[float] = None
    IncrementFiles: typing.Optional[float] = None
    IncrementFileSize: typing.Optional[float] = None
    Errors: typing.Optional[float] = None
    TotalDestinationSizeChange: typing.Optional[float] = None
    StartTime: typing.Optional[float] = None
    EndTime: typing.Optional[float] = None
    ElapsedTime: typing.Optional[float] = None

    Count: int = 1

    _stat_file_attrs = (
        "SourceFiles",
        "SourceFileSize",
        "MirrorFiles",
        "MirrorFileSize",
        "NewFiles",
        "NewFileSize",
        "DeletedFiles",
        "DeletedFileSize",
        "ChangedFiles",
        "ChangedSourceSize",
        "ChangedMirrorSize",
        "IncrementFiles",
        "IncrementFileSize",
    )
    _stat_misc_attrs = ("Errors", "TotalDestinationSizeChange")
    _stat_time_attrs = ("StartTime", "EndTime", "ElapsedTime")
    _stat_attrs = _stat_time_attrs + _stat_misc_attrs + _stat_file_attrs

    # Below, the second value in each pair is true iff the value
    # indicates a number of bytes
    _stat_file_pairs = (
        ("SourceFiles", False),
        ("SourceFileSize", True),
        ("MirrorFiles", False),
        ("MirrorFileSize", True),
        ("NewFiles", False),
        ("NewFileSize", True),
        ("DeletedFiles", False),
        ("DeletedFileSize", True),
        ("ChangedFiles", False),
        ("ChangedSourceSize", True),
        ("ChangedMirrorSize", True),
        ("IncrementFiles", False),
        ("IncrementFileSize", True),
    )

    def get_stats_as_string(self, title: str = "Session statistics") -> str:
        """Like _get_stats_string, but add header and footer"""
        header = "--------------[ %s ]--------------" % title
        footer = "-" * len(header)
        return "%s\n%s%s\n" % (header, self._get_stats_string(), footer)

    def write_stats(self, fp: SessionStatsWriter) -> None:
        """Write statistics string to given rpath"""
        fp.write(self._get_stats_string())
        fp.close()

    def read_stats(self, fp: SessionStatsReader) -> Self:
        """Set statistics from rpath, return self for convenience"""
        self._set_stats_from_string(fp.read())
        fp.close()
        return self

    def calc_average(self, sess_stats_list: list[Self]) -> Self:
        """Set self's attributes to average of those in sess_stats_list"""
        for attr in self._stat_attrs:
            self.__setattr__(attr, 0)
        for statobj in sess_stats_list:
            for attr in self._stat_attrs:
                if statobj.__getattribute__(attr) is None:
                    self.__setattr__(attr, None)
                elif self.__getattribute__(attr) is not None:
                    self.__setattr__(
                        attr,
                        statobj.__getattribute__(attr) + self.__getattribute__(attr),
                    )

        # Never compute average starting/stopping time
        self.StartTime = None
        self.EndTime = None

        self.Count = len(sess_stats_list)
        count = float(self.Count)
        for attr in self._stat_attrs:
            value = self.__getattribute__(attr)
            if value is not None:
                self.__setattr__(attr, value / count)
        return self

    def _get_total_dest_size_change(self) -> typing.Optional[float]:
        """
        Return total destination size change

        This represents the total change in the size of the
        rdiff-backup destination directory.
        """
        addvals = [self.NewFileSize, self.ChangedSourceSize, self.IncrementFileSize]
        subtractvals = [self.DeletedFileSize, self.ChangedMirrorSize]
        # if any value is None, the result is also None, else it's calculated
        if any(v is None for v in addvals + subtractvals):
            result = None
        else:
            # we need the casting to make mypy happy as it doesn't grok that the
            # above "any" makes sure that only numbers remain in the lists
            result = sum(typing.cast(list[float], addvals)) - sum(
                typing.cast(list[float], subtractvals)
            )
        self.TotalDestinationSizeChange = result
        return result

    def _get_stats_line(self, index: list[str], quote_filename: bool = True):
        """TEST: Return one line abbreviated version of full stats string"""
        file_attrs = [
            str(self.__getattribute__(attr)) for attr in self._stat_file_attrs
        ]
        if not index:
            filename = "."
        else:
            filename = "/".join(index)  # RORPath.path_join works only with bytes paths
            if quote_filename:
                # quote filename to make sure it doesn't have spaces
                # or newlines impeaching proper parsing of the line
                filename = filename.replace("\n", "\\n").replace(" ", "\\x20")
        return " ".join(
            [
                filename,
            ]
            + file_attrs
        )

    def _get_stats_string(self) -> str:
        """Return extended string printing out statistics"""
        return "%s%s%s" % (
            self._get_timestats_string(),
            self._get_filestats_string(),
            self._get_miscstats_string(),
        )

    def _get_timestats_string(self) -> str:
        """Return portion of statistics string dealing with time"""
        timelist = []
        if self.StartTime is not None:
            timelist.append(
                "StartTime %.2f (%s)\n"
                % (self.StartTime, Time.timetopretty(self.StartTime))
            )
        if self.EndTime is not None:
            timelist.append(
                "EndTime %.2f (%s)\n" % (self.EndTime, Time.timetopretty(self.EndTime))
            )
        if self.StartTime is not None and self.EndTime is not None:
            if self.ElapsedTime is None:
                self.ElapsedTime = self.EndTime - self.StartTime
        if self.ElapsedTime is not None:
            timelist.append(
                "ElapsedTime %.2f (%s)\n"
                % (self.ElapsedTime, Time.inttopretty(self.ElapsedTime))
            )
        return "".join(timelist)

    def _get_filestats_string(self) -> str:
        """Return portion of statistics string about files and bytes"""

        def fileline(stat_file_pair: tuple[str, bool]):
            """Return zero or one line of the string"""
            attr, in_bytes = stat_file_pair
            val: typing.Optional[float] = self.__getattribute__(attr)
            if val is None:
                return ""
            if in_bytes:
                return "%s %s (%s)\n" % (attr, val, convert.to_human_size_str(int(val)))
            else:
                return "%s %s\n" % (attr, val)

        return "".join(map(fileline, self._stat_file_pairs))

    def _get_miscstats_string(self) -> str:
        """Return portion of extended stat string about misc attributes"""
        misc_string: str = ""
        tdsc: typing.Optional[float] = self._get_total_dest_size_change()
        if tdsc is not None:
            misc_string += "TotalDestinationSizeChange %s (%s)\n" % (
                tdsc,
                convert.to_human_size_str(int(tdsc)),
            )
        if self.Errors is not None:
            misc_string += "Errors %d\n" % self.Errors
        return misc_string

    def _set_stats_from_string(self, s: str) -> Self:
        """Initialize attributes from string, return self for convenience"""

        def error(line: str):
            raise StatsException("Bad line '%s'" % line)

        for line in s.split("\n"):
            if not line:
                continue
            line_parts = line.split()
            if len(line_parts) < 2:
                error(line)
            attr, value_string = line_parts[:2]
            if attr not in self._stat_attrs:
                error(line)
            try:
                val = float(value_string)
                if val.is_integer():
                    self.__setattr__(attr, int(val))  # use integer val
                else:
                    self.__setattr__(attr, val)  # use float
            except ValueError:
                error(line)
        return self

    def _stats_equal(self, s: Self) -> bool:
        """Return true if s has same statistics as self"""
        assert isinstance(
            s, SessionStatsCalc
        ), "Can only compare with SessionStatsCalc not {stype}.".format(stype=type(s))
        for attr in self._stat_file_attrs:
            if self.__getattribute__(attr) != s.__getattribute__(attr):
                return False
        return True


class SessionStatsTracker(SessionStatsCalc):
    """Build on SessionStatsCalc, add functions for processing files"""

    def __init__(self, start_time: typing.Optional[float] = None) -> None:
        """StatFileObj initializer - zero out file attributes"""
        super().__init__()
        for attr in self._stat_file_attrs:
            self.__setattr__(attr, 0)
        if start_time is None:
            self.StartTime = Time.getcurtime() or time.time()
        else:
            self.StartTime = start_time
        self.Errors = 0

    def add_source_file(self, src_rorp):
        """Add stats of source file"""
        self.SourceFiles += 1
        if src_rorp.isreg():
            self.SourceFileSize += src_rorp.getsize()

    def add_dest_file(self, dest_rorp):
        """Add stats of destination size"""
        self.MirrorFiles += 1
        if dest_rorp.isreg():
            self.MirrorFileSize += dest_rorp.getsize()

    def add_changed(self, src_rorp, dest_rorp):
        """Update stats when src_rorp changes to dest_rorp"""
        if src_rorp and src_rorp.lstat() and dest_rorp and dest_rorp.lstat():
            self.ChangedFiles += 1
            if src_rorp.isreg():
                self.ChangedSourceSize += src_rorp.getsize()
            if dest_rorp.isreg():
                self.ChangedMirrorSize += dest_rorp.getsize()
        elif src_rorp and src_rorp.lstat():
            self.NewFiles += 1
            if src_rorp.isreg():
                self.NewFileSize += src_rorp.getsize()
        elif dest_rorp and dest_rorp.lstat():
            self.DeletedFiles += 1
            if dest_rorp.isreg():
                self.DeletedFileSize += dest_rorp.getsize()

    def add_increment(self, inc_rorp):
        """Update stats with increment rorp"""
        self.IncrementFiles += 1
        if inc_rorp.isreg():
            self.IncrementFileSize += inc_rorp.getsize()

    def add_error(self):
        """Increment error stat by 1"""
        if specifics.is_backup_writer:
            self.add_error_local()
        elif generics.backup_writer:
            generics.backup_writer.sstats.SessionStats.add_error_local()

    # @API(SessionStats.add_error_local, 300)
    def add_error_local(self):
        """Record error on active statfileobj, if there is one"""
        self.Errors += 1

    def finish(self, end_time=None):
        """Record end time and set other stats"""
        if end_time is None:
            self.EndTime = time.time()
        else:
            self.EndTime = end_time


def reset_statistics():
    global SessionStats
    SessionStats = SessionStatsTracker()


reset_statistics()
