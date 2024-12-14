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
"""Generate and process aggregated backup information"""

import time
import typing

from rdiff_backup import Time
from rdiffbackup.locations import increment
from rdiffbackup.singletons import log
from rdiffbackup.utils import convert, quoting

_active_statfileobj = None

if typing.TYPE_CHECKING:  # pragma: no cover
    from rdiff_backup import rpath


class StatsWriter(typing.Protocol):  # pragma: no cover
    """Protocol representing a subset of io.BufferedWriter methods"""

    def write(self, buffer: str) -> int:
        """Write a string buffer to the stats, returns the number of written bytes"""
        ...

    def close(self) -> None:
        """Close the stats writer"""
        ...


class StatsReader(typing.Protocol):  # pragma: no cover
    """Protocol representing a subset of io.BufferedReader methods"""

    def read(self) -> str:
        """Read a string from the file and return it"""
        ...

    def close(self) -> None:
        """Close the stats reader"""
        ...


class FileStatsWriter(typing.Protocol):  # pragma: no cover
    """Protocol representing a subset of io.BufferedWriter methods"""

    def write(self, buffer: bytes) -> int:
        """Write a bytes buffer to the stats, returns the number of written bytes"""
        ...

    def close(self) -> None:
        """Close the stats writer"""
        ...


# TODO need to update and refine based on run_stats
class FileStatsReader(typing.Protocol):  # pragma: no cover
    """Protocol representing a subset of io.BufferedReader methods"""

    def readline(self) -> bytes:
        """Read a line of bytes from the file and return it"""
        ...

    def close(self) -> None:
        """Close the stats reader"""
        ...


class StatsException(Exception):
    pass


class StatsObj:
    """Contains various statistics, provide string conversion functions"""

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
    _stat_attrs = ("Filename",) + _stat_time_attrs + _stat_misc_attrs + _stat_file_attrs

    # Below, the second value in each pair is true iff the value
    # indicates a number of bytes
    _stat_file_pairs = (
        ("SourceFiles", None),
        ("SourceFileSize", 1),
        ("MirrorFiles", None),
        ("MirrorFileSize", 1),
        ("NewFiles", None),
        ("NewFileSize", 1),
        ("DeletedFiles", None),
        ("DeletedFileSize", 1),
        ("ChangedFiles", None),
        ("ChangedSourceSize", 1),
        ("ChangedMirrorSize", 1),
        ("IncrementFiles", None),
        ("IncrementFileSize", 1),
    )

    def __init__(self):
        """Set attributes to None"""
        for attr in self._stat_attrs:
            self.__dict__[attr] = None

    def get_stat(self, attribute):
        """Get a statistic"""
        return self.__dict__[attribute]

    def set_stat(self, attr, value):
        """Set attribute to given value"""
        self.__dict__[attr] = value

    def get_stats_logstring(self, title):
        """Like _get_stats_string, but add header and footer"""
        header = "--------------[ %s ]--------------" % title
        footer = "-" * len(header)
        return "%s\n%s%s\n" % (header, self._get_stats_string(), footer)

    def write_stats_to_rp(self, rp):
        """Write statistics string to given rpath"""
        fp = rp.open("w")  # statistics are a text file
        fp.write(self._get_stats_string())
        fp.close()

    def read_stats_from_rp(self, rp):
        """Set statistics from rpath, return self for convenience"""
        fp = rp.open("r")  # statistics are a text file
        self._set_stats_from_string(fp.read())
        fp.close()
        return self

    def set_to_average(self, statobj_list):
        """Set self's attributes to average of those in statobj_list"""
        for attr in self._stat_attrs:
            self.set_stat(attr, 0)
        for statobj in statobj_list:
            for attr in self._stat_attrs:
                if statobj.get_stat(attr) is None:
                    self.set_stat(attr, None)
                elif self.get_stat(attr) is not None:
                    self.set_stat(attr, statobj.get_stat(attr) + self.get_stat(attr))

        # Don't compute average starting/stopping time
        self.StartTime = None
        self.EndTime = None

        for attr in self._stat_attrs:
            if self.get_stat(attr) is not None:
                self.set_stat(attr, self.get_stat(attr) / float(len(statobj_list)))
        return self

    def _get_total_dest_size_change(self):
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
            result = sum(addvals) - sum(subtractvals)
        self.TotalDestinationSizeChange = result
        return result

    def _get_stats_line(self, index, quote_filename=1):
        """TEST: Return one line abbreviated version of full stats string"""
        file_attrs = [str(self.get_stat(attr)) for attr in self._stat_file_attrs]
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

    def _get_stats_string(self):
        """Return extended string printing out statistics"""
        return "%s%s%s" % (
            self._get_timestats_string(),
            self._get_filestats_string(),
            self._get_miscstats_string(),
        )

    def _get_timestats_string(self):
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
        if self.ElapsedTime or (
            self.StartTime is not None and self.EndTime is not None
        ):
            if self.ElapsedTime is None:
                self.ElapsedTime = self.EndTime - self.StartTime
            timelist.append(
                "ElapsedTime %.2f (%s)\n"
                % (self.ElapsedTime, Time.inttopretty(self.ElapsedTime))
            )
        return "".join(timelist)

    def _get_filestats_string(self):
        """Return portion of statistics string about files and bytes"""

        def fileline(stat_file_pair):
            """Return zero or one line of the string"""
            attr, in_bytes = stat_file_pair
            val = self.get_stat(attr)
            if val is None:
                return ""
            if in_bytes:
                return "%s %s (%s)\n" % (attr, val, convert.to_human_size_str(val))
            else:
                return "%s %s\n" % (attr, val)

        return "".join(map(fileline, self._stat_file_pairs))

    def _get_miscstats_string(self):
        """Return portion of extended stat string about misc attributes"""
        misc_string = ""
        tdsc = self._get_total_dest_size_change()
        if tdsc is not None:
            misc_string += "TotalDestinationSizeChange %s (%s)\n" % (
                tdsc,
                convert.to_human_size_str(tdsc),
            )
        if self.Errors is not None:
            misc_string += "Errors %d\n" % self.Errors
        return misc_string

    def _set_stats_from_string(self, s):
        """Initialize attributes from string, return self for convenience"""

        def error(line):
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
                try:
                    val1 = int(value_string)
                except ValueError:
                    val1 = None
                val2 = float(value_string)
                if val1 == val2:
                    self.set_stat(attr, val1)  # use integer val
                else:
                    self.set_stat(attr, val2)  # use float
            except ValueError:
                error(line)
        return self

    def _stats_equal(self, s):
        """Return true if s has same statistics as self"""
        assert isinstance(
            s, StatsObj
        ), "Can only compare with StatsObj not {stype}.".format(stype=type(s))
        for attr in self._stat_file_attrs:
            if self.get_stat(attr) != s.get_stat(attr):
                return None
        return 1


class StatFileObj(StatsObj):
    """Build on StatsObj, add functions for processing files"""

    def __init__(self, start_time=None):
        """StatFileObj initializer - zero out file attributes"""
        StatsObj.__init__(self)
        for attr in self._stat_file_attrs:
            self.set_stat(attr, 0)
        if start_time is None:
            start_time = Time.getcurtime()
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
        self.Errors += 1

    def finish(self, end_time=None):
        """Record end time and set other stats"""
        if end_time is None:
            end_time = time.time()
        self.EndTime = end_time


class FileStatsTracker:
    """
    Keep track of less detailed stats on file-by-file basis.
    Because the object is only used by the repository, we don't need to handle
    the client/server complexity.
    """

    _fileobj: typing.Optional[FileStatsWriter] = None
    _line_sep: bytes = b"\n"
    _line_buffer: list[bytes] = []
    _header: bytes = b""

    def open_stats_file(self, stats_writer: FileStatsWriter, separator: bytes) -> None:
        """Open file stats object and prepare to write"""
        assert not self._fileobj, "FileStats has already been initialized."
        self._fileobj = stats_writer
        self._line_sep = separator
        self._write_header()

    def add_stats(
        self,
        source_rorp: typing.Optional["rpath.RORPath"],
        dest_rorp: typing.Optional["rpath.RORPath"],
        changed: bool,
        inc: typing.Optional["rpath.RORPath"],
    ) -> None:
        """Update file stats with given information"""
        if source_rorp:
            filename = source_rorp.get_indexpath()
        else:
            assert dest_rorp, (
                "At least one of source {sp} or destination {dp} "
                "must be defined".format(sp=source_rorp, dp=dest_rorp)
            )
            filename = dest_rorp.get_indexpath()
        filename = quoting.quote_path(filename)

        size_list = list(map(self._get_size, [source_rorp, dest_rorp, inc]))
        line = b" ".join([filename, str(changed).encode()] + size_list)
        self._line_buffer.append(line)
        if len(self._line_buffer) >= 100:
            self._write_buffer()

    def close(self) -> None:
        """Close file stats file"""
        assert self._fileobj, "FileStats hasn't been properly initialized."
        if self._line_buffer:
            self._write_buffer()
        self._fileobj.close()
        self._fileobj = None

    def _write_header(self) -> None:
        """Write the first line (a documentation string) into file"""
        assert self._fileobj, "FileStats hasn't been properly initialized."
        # we keep a copy of the header to simplify testing
        self._header = self._line_sep.join(
            (
                b"# Format of each line in file statistics file:",
                b"# Filename Changed SourceSize MirrorSize IncrementSize",
                b"",  # for a final line separator
            )
        )
        self._fileobj.write(self._header)

    def _get_size(self, rorp: typing.Optional["rpath.RORPath"]) -> bytes:
        """Return the size of rorp as bytes, or "NA" if not a regular file"""
        if not rorp:
            return b"NA"
        if rorp.isreg():
            return str(rorp.getsize()).encode()
        else:
            return b"0"

    # FIXME: actually this class shouldn't know anything about the underlying file
    # implementation, gzip or not gzip, and the StatsFileWriter should handle it
    # transparently as a wrapper to the underlying implementation
    def _write_buffer(self) -> None:
        """
        Write buffer to file because buffer is full

        The buffer part is necessary because the GzipFile.write()
        method seems fairly slow.
        """
        assert (
            self._line_buffer and self._fileobj
        ), "FileStats hasn't been properly initialized."
        self._line_buffer.append(b"")  # have join add _line_sep to end also
        self._fileobj.write(self._line_sep.join(self._line_buffer))
        self._line_buffer = []


def init_statfileobj():
    """Return new stat file object, record as active stat object"""
    global _active_statfileobj
    assert not _active_statfileobj, "Can't set an already set stats object."
    _active_statfileobj = StatFileObj()
    return _active_statfileobj


def get_active_statfileobj():
    """Return active stat file object if it exists"""
    if _active_statfileobj:
        return _active_statfileobj
    else:
        return None


# @API(record_error, 200)
def record_error():
    """Record error on active statfileobj, if there is one"""
    if _active_statfileobj:
        _active_statfileobj.add_error()


def process_increment(inc_rorp):
    """Add statistics of increment rp incrp if there is active statfile"""
    if _active_statfileobj:
        _active_statfileobj.add_increment(inc_rorp)


def write_active_statfileobj(data_dir, end_time=None):
    """Write active StatFileObj object to session statistics file"""
    global _active_statfileobj
    assert _active_statfileobj, "Stats object must be set before writing."
    rp_base = data_dir.append(b"session_statistics")
    session_stats_rp = increment.get_increment(rp_base, "data", Time.getcurtime())
    _active_statfileobj.finish(end_time)
    _active_statfileobj.write_stats_to_rp(session_stats_rp)
    _active_statfileobj = None


def print_active_stats(end_time=None):
    """Print statistics of active statobj to stdout and log"""
    global _active_statfileobj
    assert _active_statfileobj, "Stats object must be set before printing."
    _active_statfileobj.finish(end_time)
    statmsg = _active_statfileobj.get_stats_logstring("Session statistics")
    log.Log(statmsg, log.NONE)


FileStats = FileStatsTracker()
