# Copyright 2024 Eric Lavarde
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
"""
Classes to improve performance of an opened file by buffering lines
"""

import typing

Line = typing.TypeVar("Line", str, bytes)


class LinesBuffer(typing.Generic[Line]):
    """
    Iterate lines like a normal filelike descriptor

    This can be used to improve performance of a normal file, e.g. compressed.
    """

    blocksize: int = 65536
    max_lines: int = 100
    buffer: list[Line]
    at_end: bool = False
    separator: Line
    _rest: typing.Optional[Line] = None

    def __init__(self, filedesc, separator: Line) -> None:
        """Initialize with file descriptor and line separator"""
        self.filedesc = filedesc
        self.separator = separator
        # we need to initialize anew with each instance or the buffer is shared
        self.buffer = []

    def __iter__(self) -> typing.Iterable[Line]:
        """Yield the lines in self.filedesc"""
        while self.buffer or not self.at_end:
            if self.buffer:
                yield self.buffer.pop(0)
            else:
                self._replenish_buffer()

    def close(self) -> None:
        if self.filedesc.writable() and self.buffer:
            self.flush()
        self.filedesc.close()

    def flush(self) -> None:
        if self.buffer:
            self.filedesc.write(self.separator.join(self.buffer) + self.separator)
            self.buffer = []
        self.filedesc.flush()

    def write(self, line: Line) -> None:
        self.buffer.append(line)
        if len(self.buffer) >= self.max_lines:
            self.flush()

    def _replenish_buffer(self) -> None:
        """Read next block from filedesc, split and add to buffer list"""
        block: Line = self.filedesc.read(self.blocksize)
        # most of the complexity is due to the fact that a line might be split
        # between two blocks
        if block:
            split = block.split(self.separator)
            if self._rest:
                split[0] = self._rest + split[0]
            self._rest = split.pop()
            self.buffer.extend(split)
        else:
            if self._rest:
                self.buffer.append(self._rest)
                self._rest = None
            self.at_end = True
