#!/usr/bin/env python3
# rdiff-backup-statistics -- Summarize rdiff-backup statistics files
# Copyright 2005 Dean Gaudet, Ben Escoto
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

import getopt
import os
import re
import subprocess
import sys

from rdiff_backup import (
    FilenameMapping,
    Globals,
    robust,
    rpath,
    Time,
)
from rdiffbackup.utils import safestr

begin_time = None  # Parse statistics at or after this time...
end_time = None  # ... and at or before this time (epoch seconds)
min_ratio = 0.05  # report only files/directories over this number
separator = b"\n"  # The line separator in file_statistics file
quiet = False  # Suppress the "Processing statistics from session ..." lines


def parse_args():
    global begin_time, end_time, min_ratio, separator, quiet
    try:
        optlist, args = getopt.getopt(
            sys.argv[1:],
            "hV",
            ["begin-time=", "end-time=", "help", "minimum-ratio=", "null-separator", "quiet", "version"],
        )
    except getopt.GetoptError:
        usage(1)

    for opt, arg in optlist:
        if opt == "--begin-time":
            begin_time = Time.genstrtotime(arg)
        elif opt == "--end-time":
            end_time = Time.genstrtotime(arg)
        elif opt == "--minimum-ratio":
            min_ratio = float(arg)
        elif opt == "--null-separator":
            separator = b"\0"
        elif opt == "--quiet":
            quiet = True
        elif opt == "-h" or opt == "--help":
            usage(0)
        elif opt == "-V" or opt == "--version":
            version(0)
        else:
            usage(1)

    if len(args) != 1:
        usage(1)

    Globals.rbdir = rpath.RPath(
        Globals.local_connection,
        os.path.join(os.fsencode(args[0]), b"rdiff-backup-data"),
    )
    if not Globals.rbdir.isdir():
        sys.exit("Directory {rp} not found".format(rp=Globals.rbdir))


def usage(rc):
    sys.stderr.write("""
Usage: {cmd}
       [--begin-time <time>] [--end-time <time>]
       [--minimum-ratio <float>] [--null-separator]
       [--help|-h] [-V|--version]
       <backup-dir>

See the rdiff-backup-statistics man page for more information.
""".format(cmd=sys.argv[0]))
    sys.exit(rc)


def version(rc):
    print("{cmd} {ver}".format(cmd=sys.argv[0], ver=Globals.version))
    sys.exit(rc)


def os_system(cmd):
    sys.stdout.flush()
    if subprocess.call(cmd):
        sys.exit("Error running command '{rc}'".format(rc=safestr.to_str(cmd)))


class StatisticsRPaths:
    """Hold file_statistics and session_statistics rpaths"""

    def __init__(self, rbdir):
        """Initializer - read increment files from rbdir"""
        self.rbdir = rbdir
        self.session_rps = self.get_sorted_inc_rps("session_statistics")
        self.filestat_rps = self.get_sorted_inc_rps("file_statistics")
        self.combined_pairs = self.get_combined_pairs()

    def get_sorted_inc_rps(self, prefix):
        """Return list of sorted rps with given prefix"""
        incs = self.rbdir.append(prefix).get_incfiles_list()
        if begin_time:
            incs = filter(lambda i: i.getinctime() >= begin_time, incs)
        if end_time:
            incs = filter(lambda i: i.getinctime() <= end_time, incs)
        incs = list(incs)
        incs.sort(key=lambda i: i.getinctime())
        return incs

    def get_combined_pairs(self):
        """Return list of matched (session_rp, file_rp) pairs"""
        session_dict = {}
        for inc in self.session_rps:
            session_dict[inc.getinctime()] = inc
        filestat_dict = {}
        for inc in self.filestat_rps:
            filestat_dict[inc.getinctime()] = inc

        result = []
        keylist = list(session_dict)  # get a list of keys
        keylist.sort()
        for time in keylist:
            if time in filestat_dict:
                result.append((session_dict[time], filestat_dict[time]))
            else:
                sys.stderr.write("No file_statistics to match '{rp}'".format(
                    rp=session_dict[time]))
        return result


def print_session_statistics(stat_rpaths):
    print("Session statistics:")
    os_system([b"rdiff-backup", b"calculate"]
              + [inc.path for inc in stat_rpaths.session_rps])


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

    def merge_tree(self, myfs, otherfs):
        """Add other_fs's tree to one of my fs trees"""
        if myfs.nametuple != otherfs.nametuple:
            raise RuntimeError(
                "Only trees of the same name tuple can be merged but "
                "{name1} and {name2} are different.".format(
                    name1=myfs.nametuple, name2=otherfs.nametuple))
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

        for (name, (mychild, otherchild)) in total_children.items():
            if mychild:
                if otherchild:
                    self.merge_tree(mychild, otherchild)
                myfs += mychild
                myfs.children.append(mychild)
            elif otherchild:
                myfs += otherchild
                myfs.children.append(otherchild)
            else:
                raise RuntimeError(
                    "Either of both childs should have been defined.")
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

    def print_top_dirs(self, label, fs_func):
        """Print the top directories in sorted order"""

        def print_line(fs, val):
            percentage = float(val) / fs_func(self.fs_root) * 100
            path = fs.nametuple and b"/".join(fs.nametuple) or b"."
            print("%s (%02.1f%%)" % (path.decode(errors="replace"), percentage))

        s = "Top directories by %s (percent of total)" % (label,)
        print("\n%s\n%s" % (s, ("-" * len(s))))
        top_fs_pair_list = self.get_top_fs(fs_func)
        top_fs_pair_list.sort(key=lambda pair: pair[1], reverse=1)
        for fs, val in top_fs_pair_list:
            print_line(fs, val)


def make_fst(session_rp, filestat_rp):
    """Construct FileStatisticsTree given session and file stat rps

    We would like a full tree, but this in general will take too much
    memory.  Instead we will build a tree that has only the
    files/directories with some stat exceeding the min ratio.

    """
    cutoff_fs = _get_cutoff_fs(_get_ss_dict(session_rp))
    filestat_fileobj = ReadlineBuffer(filestat_rp)
    accumulated_iter = _accumulate_fs(_yield_fs_objs(filestat_fileobj))
    important_iter = filter(lambda fs: fs >= cutoff_fs, accumulated_iter)
    trimmed_tree = _make_root_tree(important_iter)
    return FileStatisticsTree(cutoff_fs, trimmed_tree)


def _get_ss_dict(session_rp):
    """Parse session statistics file and return dictionary with ss data"""
    fileobj = session_rp.open("rb", session_rp.isinccompressed())
    return_val = {}
    for line in fileobj:
        if line.startswith(b"#"):
            continue
        comps = line.split()
        if len(comps) < 2:
            sys.stderr.write("Unable to parse session statistics line: " + line)
            continue
        return_val[comps[0]] = float(comps[1])
    return return_val


def _get_cutoff_fs(session_dict):
    """Return FileStat object set with absolute cutoffs

    Any FileStat object that is bigger than the result in any
    aspect will be considered "important".

    """

    def get_min(attrib):
        return min_ratio * session_dict[attrib]

    min_changed = min_ratio * (
        session_dict[b"NewFiles"]
        + session_dict[b"ChangedFiles"]
        + session_dict[b"NewFiles"]
    )
    return FileStat(
        (), min_changed, get_min(b"SourceFileSize"), get_min(b"IncrementFileSize")
    )


def _yield_fs_objs(filestatsobj):
    """Iterate FileStats by processing file_statistics fileobj"""
    r = re.compile(
        b"^(.*) ([0-9]+) ([0-9]+|NA) ([0-9]+|NA) " b"([0-9]+|NA)%b?$" % (separator,)
    )
    for line in filestatsobj:
        if line.startswith(b"#"):
            continue
        match = r.match(line)
        if not match:
            sys.stderr.write("Error parsing line: '{li}'\n".format(
                li=safestr.to_str(line)))
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
                name=root.nametuple))
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
        sys.exit("No files in iterator")

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
    """Hold the information in one line of file_statistics

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


class ReadlineBuffer:
    """Iterate lines like a normal filelike obj

    Use this because gzip doesn't provide any buffering, so readline()
    is very slow.

    """

    blocksize = 65536

    def __init__(self, rp):
        """Initialize with rpath"""
        self.buffer = [b""]
        self.at_end = 0

        if rp.isincfile():
            self.fileobj = rp.open("rb", rp.isinccompressed())
        else:
            self.fileobj = rp.open("rb")

    def __iter__(self):
        """Yield the lines in self.fileobj"""
        while self.buffer or not self.at_end:
            if len(self.buffer) > 1:
                yield self.buffer.pop(0)
            elif not self.at_end:
                self.addtobuffer()
            else:
                last = self.buffer.pop()
                if last:
                    yield last

    def addtobuffer(self):
        """Read next block from fileobj, split and add to bufferlist"""
        block = self.fileobj.read(self.blocksize)
        if block:
            split = block.split(separator)
            self.buffer[0] += split[0]
            self.buffer.extend(split[1:])
        else:
            self.at_end = 1


def sum_fst(rp_pairs):
    """Add the file statistics given as list of (session_rp, file_rp) pairs"""
    global quiet
    n = len(rp_pairs)
    if not quiet:
        print("Processing statistics from session 1 of %d" % (n,))
    total_fst = make_fst(*rp_pairs[0])
    for i in range(1, n):
        if not quiet:
            print("Processing statistics from session %d of %d" % (i + 1, n))
        session_rp, filestat_rp = rp_pairs[i]
        fst = make_fst(session_rp, filestat_rp)
        total_fst += fst
    return total_fst


def set_chars_to_quote():
    ctq_rp = Globals.rbdir.append("chars_to_quote")
    if ctq_rp.lstat():
        Globals.chars_to_quote = ctq_rp.get_bytes()
    if Globals.chars_to_quote:
        FilenameMapping.set_init_quote_vals()
        Globals.rbdir = FilenameMapping.get_quotedrpath(Globals.rbdir)


def main_run():
    Time.set_current_time()
    parse_args()
    set_chars_to_quote()
    srp = StatisticsRPaths(Globals.rbdir)
    if not srp.combined_pairs:
        sys.exit("No matching sessions found")
    if len(srp.combined_pairs) == 1:
        fst = make_fst(*srp.combined_pairs[0])
    else:
        fst = sum_fst(srp.combined_pairs)

    print_session_statistics(srp)
    fst.print_top_dirs("source size", lambda fs: fs.sourcesize)
    fst.print_top_dirs("increment size", lambda fs: fs.incsize)
    fst.print_top_dirs("number of files changed", lambda fs: fs.changed)


def main():
    """Run main_run on arglist, suppressing stack trace for routine errors"""
    try:
        main_run()
    except SystemExit:
        raise
    except KeyboardInterrupt:
        print("User abort")
    except (Exception, KeyboardInterrupt) as exc:
        if robust.catch_error(exc):
            print(exc)
        else:
            raise


if __name__ == "__main__":
    main()
