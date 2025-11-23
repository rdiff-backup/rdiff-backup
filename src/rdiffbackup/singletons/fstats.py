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

import re
import sys
import typing

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


class FileStatisticsTree:
    """Holds a tree of important files/directories, along with cutoffs"""

    def __init__(self, cutoff_fs, fs_root):
        """Initialize with FileStat cutoff object, and root of tree"""
        self.cutoff_fs = cutoff_fs
        self.fs_root = fs_root

    def __iadd__(self, other):
        """Add cutoffs, and merge the other's fs_root"""
        self.cutoff_fs += other.cutoff_fs
        self.merge_tree(self.fs_root, other.fs_root)
        return self

    def __add__(self, other):
        """Add cutoffs, and merge the other's fs_root"""
        new_fst = self.__class__(self.cutoff_fs, self.fs_root)
        new_fst += other
        return new_fst

    def merge_tree(self, myfs, otherfs):
        """Add other_fs's tree to one of my fs trees"""
        if myfs.nametuple != otherfs.nametuple:
            raise RuntimeError(
                "Only trees of the same name tuple can be merged but "
                "{name1} and {name2} are different.".format(
                    name1=myfs.nametuple, name2=otherfs.nametuple
                )
            )
        total_children = {}
        mine = dict([(child.nametuple, child) for child in myfs.children])
        others = dict([(child.nametuple, child) for child in otherfs.children])
        # Remove duplicate children
        for name in list(mine.keys()) + list(others.keys()):
            if name not in total_children:
                total_children[name] = (mine.get(name), others.get(name))

        # Subtract subdirectories so we can rebuild
        for child in myfs.children:
            myfs -= child
        for child in otherfs.children:
            otherfs -= child
        myfs.children = []

        for name, (mychild, otherchild) in total_children.items():
            if mychild:
                if otherchild:
                    self.merge_tree(mychild, otherchild)
                myfs += mychild
                myfs.children.append(mychild)
            elif otherchild:
                myfs += otherchild
                myfs.children.append(otherchild)
            else:
                raise RuntimeError("Either of both childs should have been defined.")
        myfs += otherfs

    def get_top_fs(self, fs_func):
        """Process the FileStat tree and find everything above the cutoff

        fs_func will be used to evaluate cutoff_fs and those in the
        tree.  Of course the root will be above the cutoff, but we try
        to find the most specific directories still above the cutoff.
        The value of any directories that make the cutoff will be
        excluded from the value of parent directories.

        """
        abs_cutoff = fs_func(self.cutoff_fs)

        def helper(subtree):
            """Returns ([list of (top fs, value)], total excluded amount)"""
            subtree_val = fs_func(subtree)
            if subtree_val <= abs_cutoff:
                return ([], 0)

            top_children, total_excluded = [], 0
            for child in subtree.children:
                top_sublist, excluded = helper(child)
                top_children.extend(top_sublist)
                total_excluded += excluded

            current_value = subtree_val - total_excluded
            if current_value >= abs_cutoff:
                return ([(subtree, current_value)] + top_children, subtree_val)
            else:
                return (top_children, total_excluded)

        return helper(self.fs_root)[0]

    def get_stats_as_string(self, label, fs_func):
        """Print the top directories in sorted order"""

        def get_line(fs, val):
            percentage = float(val) / fs_func(self.fs_root) * 100
            path = fs.nametuple and b"/".join(fs.nametuple) or b"."
            return "%s (%02.1f%%)" % (convert.to_safe_str(path), percentage)

        s = ["Top directories by {lb} (percent of total)".format(lb=label)]
        s.append("-" * len(s[0]))
        top_fs_pair_list = self.get_top_fs(fs_func)
        top_fs_pair_list.sort(key=lambda pair: pair[1], reverse=1)
        for fs, val in top_fs_pair_list:
            s.append(get_line(fs, val))
        return "\n" + "\n".join(s)


def make_fst(filestat_reader, cutoff, separator: bytes):
    """
    Construct FileStatisticsTree given session and file stat rps

    We would like a full tree, but this in general will take too much
    memory.  Instead we will build a tree that has only the
    files/directories with some stat exceeding the min ratio.
    """
    cutoff_fs = FileStat((), *cutoff)
    filestat_fileobj = buffer.LinesBuffer(filestat_reader, separator)
    accumulated_iter = _accumulate_fs(_yield_fs_objs(filestat_fileobj, separator))
    important_iter = filter(lambda fs: fs >= cutoff_fs, accumulated_iter)
    trimmed_tree = _make_root_tree(important_iter)
    # TODO close the filestat_fileobj before returning?
    return FileStatisticsTree(cutoff_fs, trimmed_tree)


def _yield_fs_objs(filestatsobj, separator):
    """Iterate FileStats by processing file_statistics fileobj"""
    r = re.compile(
        b"^(.*) ([0-9]+) ([0-9]+|NA) ([0-9]+|NA) " b"([0-9]+|NA)%b?$" % (separator,)
    )
    for line in filestatsobj:
        if line.startswith(b"#"):
            continue
        match = r.match(line)
        if not match:
            sys.stderr.write(
                "Error parsing line: '{li}'\n".format(li=convert.to_safe_str(line))
            )
            continue

        filename = match.group(1)
        if filename == b".":
            nametuple = ()
        else:
            nametuple = tuple(filename.split(b"/"))

        sourcesize_str = match.group(3)
        if sourcesize_str == b"NA":
            sourcesize = 0
        else:
            sourcesize = int(sourcesize_str)

        incsize_str = match.group(5)
        if incsize_str == b"NA":
            incsize = 0
        else:
            incsize = int(incsize_str)

        yield FileStat(nametuple, int(match.group(2)), sourcesize, incsize)


def _accumulate_fs(fs_iter):
    """Yield the FileStat objects in fs_iter, but with total statistics

    In fs_iter, the statistics of directories FileStats only apply
    to themselves.  This will iterate the same FileStats, but
    directories will include all the files under them.  As a
    result, the directories will come after the files in them
    (e.g. '.' will be last.).

    Naturally this would be written recursively, but profiler said
    it was too slow in python.

    """
    root = next(fs_iter)
    if root.nametuple != ():
        raise RuntimeError(
            "Name tuple of root should be empty but is {name}.".format(
                name=root.nametuple
            )
        )
    stack = [root]
    try:
        fs = next(fs_iter)
    except StopIteration:
        yield root
        return

    while 1:
        if fs and fs.is_child(stack[-1]):
            stack.append(fs)
            try:
                fs = next(fs_iter)
            except StopIteration:
                fs = None
        else:
            expired = stack.pop()
            yield expired
            if not stack:
                return
            else:
                stack[-1].add_child(expired)


def _make_root_tree(fs_iter):
    """Like make_tree, but assume fs_iter starts at the root"""
    try:
        fs = next(fs_iter)
    except StopIteration:
        return None

    while fs.nametuple != ():
        fs = _make_tree_one_level(fs_iter, fs)
    return fs


def _make_tree_one_level(fs_iter, first_fs):
    """Populate a tree of FileStat objects from fs_iter

    This function wants the fs_iter in the reverse direction as
    usual, with the parent coming directly after all the children.
    It will return the parent of first_fs.

    """
    children = [first_fs]
    fs = next(fs_iter)
    while 1:
        if first_fs.is_child(fs):
            fs.children = children
            return fs
        elif first_fs.is_brother(fs):
            children.append(fs)
            fs = next(fs_iter)
        else:
            fs = _make_tree_one_level(fs_iter, fs)


class FileStat:
    """
    Hold the information in one line of file_statistics

    However, unlike file_statistics, a File can have subdirectories
    under it.  In that case, the information should be cumulative.
    """

    def __init__(self, nametuple, changed, sourcesize, incsize):
        self.nametuple = nametuple
        self.changed = changed
        self.sourcesize, self.incsize = sourcesize, incsize
        self.children = []

    def add_child(self, child):
        self += child

    def is_subdir(self, parent):
        """Return True if self is an eventual subdir of parent"""
        return self.nametuple[: len(parent.nametuple)] == parent.nametuple

    def is_child(self, parent):
        """Return True if self is an immediate child of parent"""
        return self.nametuple and self.nametuple[:-1] == parent.nametuple

    def is_brother(self, brother):
        """Return True if self is in same directory as brother"""
        if not self.nametuple or not brother.nametuple:
            return 0
        return self.nametuple[:-1] == brother.nametuple[:-1]

    def __str__(self):
        return "%s %s %s %s" % (
            self.nametuple,
            self.changed,
            self.sourcesize,
            self.incsize,
        )

    def __eq__(self, other):
        return (
            self.changed == other.changed
            and self.sourcesize == other.sourcesize
            and self.incsize == other.incsize
        )

    def __ge__(self, other):
        """Note the 'or' -- this relation is not a well ordering"""
        return (
            self.changed >= other.changed
            or self.sourcesize >= other.sourcesize
            or self.incsize >= other.incsize
        )

    def __iadd__(self, other):
        """Add values of other to self"""
        self.changed += other.changed
        self.sourcesize += other.sourcesize
        self.incsize += other.incsize
        return self

    def __isub__(self, other):
        """Subtract values of other from self"""
        self.changed -= other.changed
        self.sourcesize -= other.sourcesize
        self.incsize -= other.incsize
        return self
