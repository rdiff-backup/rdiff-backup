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
"""Generate and process aggregated backup files information"""

import typing

from rdiffbackup.singletons import generics, specifics
from rdiffbackup.utils import convert, buffer, quoting

_active_statfileobj = None

if typing.TYPE_CHECKING:  # pragma: no cover
    from rdiff_backup import rpath


class FileStatsWriter(typing.Protocol):  # pragma: no cover
    """Protocol representing a subset of io.BufferedWriter methods"""

    def write(self, buffer: bytes) -> int:
        """Write a bytes buffer to the stats, returns the number of written bytes"""
        ...

    def close(self) -> None:
        """Close the stats writer"""
        ...

    def flush(self) -> None:
        """Flush the stats writer"""
        ...


# TODO need to update and refine based on run_stats
class FileStatsReader(typing.Protocol):  # pragma: no cover
    """Protocol representing a subset of io.BufferedReader methods"""

    def __iter__(self) -> bytes:
        """Iterate over the input"""
        ...

    def close(self) -> None:
        """Close the stats reader"""
        ...


class FileStatsTracker:
    """
    Keep track of less detailed stats on file-by-file basis.
    Because the object is only used by the repository, we don't need to handle
    the client/server complexity.
    """

    _fileobj: typing.Optional[FileStatsWriter] = None
    _line_buffer: list[bytes] = []
    _HEADER: typing.Final[tuple[bytes, bytes]] = (
        b"# Format of each line in file statistics file:",
        b"# Filename Changed SourceSize MirrorSize IncrementSize",
    )

    def open_stats_file(self, stats_writer: FileStatsWriter, separator: bytes) -> None:
        """Open file stats object and prepare to write"""
        assert not self._fileobj, "FileStats has already been initialized."
        self._fileobj = typing.cast(
            FileStatsWriter, buffer.LinesBuffer(stats_writer, separator)
        )
        for line in self._HEADER:
            self._fileobj.write(line)

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
        assert self._fileobj, "FileStats hasn't been properly initialized."
        self._fileobj.write(line)

    def close(self) -> None:
        """Close file stats file"""
        assert self._fileobj, "FileStats hasn't been properly initialized."
        self._fileobj.close()
        self._fileobj = None

    def flush(self) -> None:
        """Flushing the underlying IO object, needed mostly for tests"""
        assert self._fileobj, "FileStats hasn't been properly initialized."
        self._fileobj.flush()

    def _get_size(self, rorp: typing.Optional["rpath.RORPath"]) -> bytes:
        """Return the size of rorp as bytes, or "NA" if not a regular file"""
        if not rorp:
            return b"NA"
        if rorp.isreg():
            return str(rorp.getsize()).encode()
        else:
            return b"0"


def reset_statistics():
    global FileStats
    FileStats = FileStatsTracker()


reset_statistics()
