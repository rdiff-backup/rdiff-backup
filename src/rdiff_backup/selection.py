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
"""
Iterate exactly the requested files in a directory

Parses includes and excludes to yield correct files.  More
documentation on what this code does can be found on the man page.
"""

import os
import re
import sys
from rdiff_backup import Globals, log, robust, rorpiter, rpath
from rdiffbackup.utils import safestr


class SelectError(Exception):
    """Some error dealing with the Select class"""
    pass


class FilePrefixError(SelectError):
    """Signals that a specified file doesn't start with correct prefix"""
    pass


class GlobbingError(SelectError):
    """Something has gone wrong when parsing a glob string"""
    pass


class Select:
    """Iterate appropriate RPaths in given directory

    This class acts as an iterator on account of its next() method.
    Basically, it just goes through all the files in a directory in
    order (depth-first) and subjects each file to a bunch of tests
    (selection functions) in order.  The first test that includes or
    excludes the file means that the file gets included (iterated) or
    excluded.  The default is include, so with no tests we would just
    iterate all the files in the directory in order.

    The one complication to this is that sometimes we don't know
    whether or not to include a directory until we examine its
    contents.  For instance, if we want to include all the **.py
    files.  If /home/ben/foo.py exists, we should also include /home
    and /home/ben, but if these directories contain no **.py files,
    they shouldn't be included.  For this reason, a test may not
    include or exclude a directory, but merely "scan" it.  If later a
    file in the directory gets included, so does the directory.

    As mentioned above, each test takes the form of a selection
    function.  The selection function takes an rpath, and returns:

    None - means the test has nothing to say about the related file
    0 - the file is excluded by the test
    1 - the file is included
    2 - the test says the file (must be directory) should be scanned

    Also, a selection function f has a variable f.exclude which should
    be true iff f could potentially exclude some file.  This is used
    to signal an error if the last function only includes, which would
    be redundant and presumably isn't what the user intends.

    """
    # This re should not match normal filenames, but usually just globs
    glob_re = re.compile(b"(.*[*?[\\\\]|ignorecase\\:)", re.I | re.S)

    # Constants to express exclusion or inclusion
    EXCLUDE = 0
    INCLUDE = 1
    # Constants to express if min size or max size
    MIN = 0
    MAX = 1

    def __init__(self, rootrp):
        """Select initializer.  rpath is the root directory"""
        assert isinstance(rootrp, rpath.RPath), (
            "Root path '{rp}' must be a real remote path.".format(rp=rootrp))
        self.selection_functions = []
        self.rpath = rootrp
        self.prefix = self.rpath.path
        self.prefixindex = tuple([x for x in self.prefix.split(b"/") if x])
        self._init_parsing_mapping()

    def get_select_iter(self):
        """
        Initialize more variables, get ready to iterate

        Selection function sel_func is called on each rpath and is
        usually self.select_default.  Returns self.iter just for convenience.
        """
        self.rpath.setdata()  # this may have changed since Select init
        select_iter = self._iterate_rpath(self.rpath, self.select_default)
        return select_iter

    def select_default(self, rp):
        """Run through the selection functions and return dominant val 0/1/2"""
        scanned = 0  # 0, by default, or 2 if prev sel func scanned rp
        for sf in self.selection_functions:
            result = sf(rp)
            if result == 1:
                return 1
            elif result == 0:
                return scanned
            elif result == 2:
                scanned = 2
        return 1

    def parse_selection_args(self, argtuples, filelists):
        """
        Create selection functions based on list of tuples

        The tuples have the form (option string, additional argument)
        and are created when the initial commandline arguments are
        read.  The reason for the extra level of processing is that
        the filelists may only be openable by the main connection, but
        the selection functions need to be on the backup reader or
        writer side.  When the initial arguments are parsed the right
        information is sent over the link.
        """
        filelists_index = 0
        try:
            for opt, arg in argtuples:
                if opt in self._sel_noargs_mapping:
                    sel_func, sel_val = self._sel_noargs_mapping[opt]
                    self._add_selection_func(sel_func(sel_val))
                elif opt in self._sel_onearg_mapping:
                    sel_func, sel_val = self._sel_onearg_mapping[opt]
                    self._add_selection_func(sel_func(arg, sel_val))
                elif opt in self._sel_filelist_mapping:
                    self._add_selection_func(
                        self._filelist_get_sf(
                            filelists[filelists_index], self._sel_filelist_mapping[opt], arg))
                    filelists_index += 1
                elif opt in self._sel_globfilelist_mapping:
                    list(
                        map(
                            self._add_selection_func,
                            self._filelist_globbing_get_sfs(
                                filelists[filelists_index], self._sel_globfilelist_mapping[opt], arg)))
                    filelists_index += 1
                else:
                    raise RuntimeError(
                        "Bad selection option {opt}.".format(opt=opt))
        except SelectError as e:
            self._parse_catch_error(e)
        assert filelists_index == len(filelists), (
            "There must be as many selection options with arguments than "
            "lists of files.")

        self._parse_last_excludes()
        self.parse_rbdir_exclude()

    def parse_rbdir_exclude(self):
        """Add exclusion of rdiff-backup-data dir to front of list"""
        self._add_selection_func(
            self._glob_get_tuple_sf((b"rdiff-backup-data", ), 0), 1)

    def _init_parsing_mapping(self):
        """
        Initiates the mapping dictionaries necessary to map command line
        arguments to selection functions
        """

        self._sel_noargs_mapping = {
            "--exclude-special-files": (self._special_get_sf, Select.EXCLUDE),
            "--exclude-symbolic-links": (self._symlinks_get_sf, Select.EXCLUDE),
            "--exclude-device-files": (self._devfiles_get_sf, Select.EXCLUDE),
            "--exclude-sockets": (self._sockets_get_sf, Select.EXCLUDE),
            "--exclude-fifos": (self._fifos_get_sf, Select.EXCLUDE),
            "--exclude-other-filesystems": (self._other_filesystems_get_sf, Select.EXCLUDE),
            "--include-special-files": (self._special_get_sf, Select.INCLUDE),
            "--include-symbolic-links": (self._symlinks_get_sf, Select.INCLUDE),
        }
        self._sel_onearg_mapping = {
            "--exclude": (self._glob_get_sf, Select.EXCLUDE),
            "--exclude-regexp": (self._regexp_get_sf, Select.EXCLUDE),
            "--exclude-if-present": (self._presence_get_sf, Select.EXCLUDE),
            "--include": (self._glob_get_sf, Select.INCLUDE),
            "--include-regexp": (self._regexp_get_sf, Select.INCLUDE),
            "--include-if-present": (self._presence_get_sf, Select.INCLUDE),
            "--min-file-size": (self._size_get_sf, Select.MIN),
            "--max-file-size": (self._size_get_sf, Select.MAX),
        }
        self._sel_filelist_mapping = {
            "--exclude-filelist": Select.EXCLUDE,
            "--include-filelist": Select.INCLUDE,
        }
        self._sel_globfilelist_mapping = {
            "--exclude-globbing-filelist": Select.EXCLUDE,
            "--include-globbing-filelist": Select.INCLUDE,
        }

    def _iterate_rpath(self, rpath, sel_func):
        """
        Return iterator yielding rpaths in rpath

        sel_func is the selection function to use on the rpaths.
        It is usually self.Select.
        """

        def error_handler(exc, filename):
            log.ErrorLog.write_if_open("ListError", rpath.index + (filename, ),
                                       exc)
            return None

        def diryield(rpath):
            """
            Generate relevant files in directory rpath

            Returns (rpath, num) where num == 0 means rpath should be
            generated normally, num == 1 means the rpath is a directory
            and should be included iff something inside is included.
            """
            for filename in self._listdir_sorted(rpath):
                new_rpath = robust.check_common_error(
                    error_handler, rpath.append, (filename, ))
                if new_rpath and new_rpath.lstat():
                    s = sel_func(new_rpath)
                    if s == 1:
                        yield (new_rpath, 0)
                    elif s == 2 and new_rpath.isdir():
                        yield (new_rpath, 1)

        yield rpath
        if not rpath.isdir():
            return
        diryield_stack = [diryield(rpath)]
        delayed_rp_stack = []

        while diryield_stack:
            try:
                rpath, val = next(diryield_stack[-1])
            except StopIteration:
                diryield_stack.pop()
                if delayed_rp_stack:
                    delayed_rp_stack.pop()
                continue
            if val == 0:
                if delayed_rp_stack:
                    for delayed_rp in delayed_rp_stack:
                        yield delayed_rp
                    del delayed_rp_stack[:]
                yield rpath
                if rpath.isdir():
                    diryield_stack.append(diryield(rpath))
            elif val == 1:
                delayed_rp_stack.append(rpath)
                diryield_stack.append(diryield(rpath))

    def _get_relative_index(self, filename):
        """return the index of a file relative to the current prefix
        or fail if they're not relative to each other"""

        fileindex = tuple([x for x in filename.split(b"/") if x])

        # are the first elements of the path the same?
        if fileindex[:len(self.prefixindex)] != self.prefixindex:
            raise FilePrefixError(filename)
        return fileindex[len(self.prefixindex):]

    def _listdir_sorted(self, dir_rp):
        """List directory rpath with error logging and sorting entries"""

        def error_handler(exc):
            log.ErrorLog.write_if_open("ListError", dir_rp, exc)
            return []

        dir_listing = robust.check_common_error(error_handler, dir_rp.listdir)
        dir_listing.sort()
        return dir_listing

    def _parse_catch_error(self, exc):
        """Deal with selection error exc"""
        if isinstance(exc, FilePrefixError):
            log.Log.FatalError("""The file specification '{fs}'
cannot match any files in the base directory '{bd}'.
Useful file specifications begin with the base directory or some
pattern (such as '**') which matches the base directory""".format(
                fs=exc, bd=self.prefix))
        elif isinstance(exc, GlobbingError):
            log.Log.FatalError("Fatal Error while processing expression "
                               "'{ex}'".format(ex=exc))
        else:
            raise

    def _parse_last_excludes(self):
        """Exit with error if last selection function isn't an exclude"""
        if (self.selection_functions
                and not self.selection_functions[-1].exclude):
            log.Log.FatalError("""Last selection expression {se}
only specifies that files be included.  Because the default is to
include all files, the expression is redundant.  Exiting because this
probably isn't what you meant""".format(se=self.selection_functions[-1].name))

    def _add_selection_func(self, sel_func, add_to_start=None):
        """Add another selection function at the end or beginning"""
        if add_to_start:
            self.selection_functions.insert(0, sel_func)
        else:
            self.selection_functions.append(sel_func)

    def _filelist_get_sf(self, filelist_fp, inc_default, filelist_name):
        """Return selection function by reading list of files

        The format of the filelist is documented in the man page.
        filelist_fp should be an (open) file object.
        inc_default should be true if this is an include list,
        false for an exclude list.
        filelist_name is just a string used for logging.

        """
        log.Log("Reading filelist {fl}".format(fl=filelist_name), log.INFO)
        tuple_list, something_excluded = \
            self._filelist_read(filelist_fp, inc_default, filelist_name)
        log.Log("Sorting filelist {fl}".format(fl=filelist_name), log.INFO)
        tuple_list.sort()
        i = [0]  # We have to put index in list because of stupid scoping rules

        def selection_function(rp):
            while 1:
                if i[0] >= len(tuple_list):
                    return None
                include, move_on = self._filelist_pair_match(rp, tuple_list[i[0]])
                if move_on:
                    i[0] += 1
                    if include is None:
                        continue  # later line may match
                return include

        selection_function.exclude = something_excluded or inc_default == Select.EXCLUDE
        selection_function.name = "Filelist: " + filelist_name
        return selection_function

    def _filelist_read(self, filelist_fp, include, filelist_name):
        """Read filelist from fp, return (tuplelist, something_excluded)"""
        prefix_warnings = [0]

        def incr_warnings(exc):
            """Warn if prefix is incorrect"""
            prefix_warnings[0] += 1
            if prefix_warnings[0] < 6:
                log.Log(
                    "File specification '{fs}' in filelist {fl} "
                    "doesn't start with correct prefix {cp}. Ignoring.".format(
                        fs=exc, fl=filelist_name, cp=self.prefix), log.WARNING)
                if prefix_warnings[0] == 5:
                    log.Log("Future prefix errors will not be logged",
                            log.WARNING)

        something_excluded, tuple_list = None, []
        separator = Globals.null_separator and b"\0" or b"\n"
        for line in filelist_fp.read().split(separator):
            line = line.rstrip(b'\r')  # for Windows/DOS endings
            if not line:
                continue  # skip blanks
            try:
                tuple = self._filelist_parse_line(line, include)
            except FilePrefixError as exc:
                incr_warnings(exc)
                continue
            tuple_list.append(tuple)
            if not tuple[1]:
                something_excluded = 1
        if filelist_fp.close():
            log.Log("Failed closing filelist {fl}".format(fl=filelist_name),
                    log.WARNING)
        return (tuple_list, something_excluded)

    def _filelist_parse_line(self, line, include):
        """Parse a single line of a filelist, returning a pair

        pair will be of form (index, include), where index is another
        tuple, and include is 1 if the line specifies that we are
        including a file.  The default is given as an argument.
        prefix is the string that the index is relative to.

        """
        if line[:2] == b"+ ":  # Check for "+ "/"- " syntax
            include = Select.INCLUDE
            line = line[2:]
        elif line[:2] == b"- ":
            include = Select.EXCLUDE
            line = line[2:]

        index = self._get_relative_index(line)
        return (index, include)

    def _filelist_pair_match(self, rp, pair):
        """Matches a filelist tuple against a rpath

        Returns a pair (include, move_on).  include is None if the
        tuple doesn't match either way, and 0/1 if the tuple excludes
        or includes the rpath.

        move_on is true if the tuple cannot match a later index, and
        so we should move on to the next tuple in the index.

        """
        index, include = pair
        if include == Select.INCLUDE:
            if index < rp.index:
                return (None, True)
            if index == rp.index:
                return (Select.INCLUDE, True)
            elif index[:len(rp.index)] == rp.index:
                return (Select.INCLUDE, False)  # /foo/bar implicitly includes /foo
            else:
                return (None, False)  # rp greater, not initial sequence
        elif include == Select.EXCLUDE:
            if rp.index[:len(index)] == index:
                return (Select.EXCLUDE, False)  # /foo implicitly excludes /foo/bar
            elif index < rp.index:
                return (None, True)
            else:
                return (None, False)  # rp greater, not initial sequence
        else:
            raise ValueError(
                "Include is {ival}, should be 0 or 1.".format(ival=include))

    def _filelist_globbing_get_sfs(self, filelist_fp, inc_default, list_name):
        """Return list of selection functions by reading fileobj

        filelist_fp should be an open file object
        inc_default is true iff this is an include list
        list_name is just the name of the list, used for logging
        See the man page on --[include/exclude]-globbing-filelist

        """
        log.Log("Reading globbing filelist {gf}".format(gf=list_name), log.INFO)
        separator = Globals.null_separator and b"\0" or b"\n"
        for line in filelist_fp.read().split(separator):
            line = line.rstrip(b'\r')  # for Windows/DOS endings
            if not line:
                continue  # skip blanks
            if line[:2] == b"+ ":
                yield self._glob_get_sf(line[2:], 1)
            elif line[:2] == b"- ":
                yield self._glob_get_sf(line[2:], 0)
            else:
                yield self._glob_get_sf(line, inc_default)

    def _other_filesystems_get_sf(self, include):
        """Return selection function matching files on other filesystems"""
        assert include == Select.EXCLUDE or include == Select.INCLUDE, (
            "Include is {ival}, should be 0 or 1.".format(ival=include))
        root_devloc = self.rpath.getdevloc()

        def sel_func(rp):
            if rp.getdevloc() == root_devloc:
                return None
            else:
                return include

        sel_func.exclude = not include
        sel_func.name = "Match other filesystems"
        return sel_func

    def _regexp_get_sf(self, regexp_string, include):
        """Return selection function given by regexp_string"""
        assert include == Select.EXCLUDE or include == Select.INCLUDE, (
            "Include is {ival}, should be 0 or 1.".format(ival=include))
        try:
            regexp = re.compile(os.fsencode(regexp_string))
        except re.error:
            log.Log("Failed compiling regular expression {rx}".format(
                rx=regexp_string), log.ERROR)
            raise

        def sel_func(rp):
            if regexp.search(rp.path):
                return include
            else:
                return None

        sel_func.exclude = not include
        sel_func.name = "Regular expression: %s" % regexp_string
        return sel_func

    def _presence_get_sf(self, presence_filename, include):
        """Return selection function given by a file if present"""
        assert include == Select.EXCLUDE or include == Select.INCLUDE, (
            "Include is {ival}, should be 0 or 1.".format(ival=include))

        def sel_func(rp):
            if (rp.isdir() and rp.readable()
                    and rp.append(presence_filename).lstat()):
                return include
            elif (include and not rp.isdir()
                    and rp.get_parent_rp().append(presence_filename).lstat()):
                return include
            return None

        sel_func.exclude = not include
        sel_func.name = "Presence file: %s" % presence_filename
        return sel_func

    def _gen_get_sf(self, pred, include, name):
        """Returns a selection function that uses pred to test

        RPath is matched if pred returns true on it.  Name is a string
        summarizing the test to the user.

        """

        def sel_func(rp):
            if pred(rp):
                return include
            return None

        sel_func.exclude = not include
        sel_func.name = (include and "include " or "exclude ") + name
        return sel_func

    def _devfiles_get_sf(self, include):
        """Return a selection function matching all dev files"""
        return self._gen_get_sf(rpath.RORPath.isdev, include, "device files")

    def _symlinks_get_sf(self, include):
        """Return a selection function matching all symlinks"""
        return self._gen_get_sf(rpath.RORPath.issym, include, "symbolic links")

    def _sockets_get_sf(self, include):
        """Return a selection function matching all sockets"""
        return self._gen_get_sf(rpath.RORPath.issock, include, "socket files")

    def _fifos_get_sf(self, include):
        """Return a selection function matching all fifos"""
        return self._gen_get_sf(rpath.RORPath.isfifo, include, "fifo files")

    def _special_get_sf(self, include):
        """Return sel function matching sockets, symlinks, sockets, devs"""

        def sel_func(rp):
            if rp.issym() or rp.issock() or rp.isfifo() or rp.isdev():
                return include
            else:
                return None

        sel_func.exclude = not include
        sel_func.name = (include and "include" or "exclude") + " special files"
        return sel_func

    def _size_get_sf(self, sizestr, min_max):
        """Return selection function given by filesize"""
        try:
            size = int(sizestr)
            if size <= 0:
                raise ValueError()
        except ValueError:
            log.Log.FatalError(
                "Max and min file size must be a positive integer "
                "and not '{fs}'".format(fs=sizestr))

        def sel_func(rp):
            if not rp.isreg():
                return None
            if min_max:
                return ((rp.getsize() <= size) and None)
            else:
                return ((rp.getsize() >= size) and None)

        sel_func.exclude = True  # min/max-file-size are exclusions
        sel_func.name = "%s size %d" % (min_max and "Maximum" or "Minimum",
                                        size)
        return sel_func

    def _glob_get_sf(self, glob_str, include):
        """Return selection function given by glob string"""
        assert include == Select.EXCLUDE or include == Select.INCLUDE, (
            "Include is {ival}, should be 0 or 1.".format(ival=include))
        glob_str = os.fsencode(glob_str)  # paths and glob must be bytes
        if glob_str == b"**":
            def sel_func(rp):
                return include
        elif not self.glob_re.match(glob_str):  # normal file
            sel_func = self._glob_get_filename_sf(glob_str, include)
        else:
            sel_func = self._glob_get_normal_sf(glob_str, include)

        sel_func.exclude = not include
        sel_func.name = "Command-line %s glob: %s" % \
            (include and "include" or "exclude", glob_str)
        return sel_func

    def _glob_get_filename_sf(self, filename, include):
        """Get a selection function given a normal filename

        Some of the parsing is better explained in
        _filelist_parse_line.  The reason this is split from normal
        globbing is things are a lot less complicated if no special
        globbing characters are used.

        """
        index = self._get_relative_index(filename)
        return self._glob_get_tuple_sf(index, include)

    def _glob_get_tuple_sf(self, tuple, include):
        """Return selection function based on tuple"""

        def include_sel_func(rp):
            if (rp.index == tuple[:len(rp.index)]
                    or rp.index[:len(tuple)] == tuple):
                return 1  # /foo/bar implicitly matches /foo, vice-versa
            else:
                return None

        def exclude_sel_func(rp):
            if rp.index[:len(tuple)] == tuple:
                return 0  # /foo excludes /foo/bar, not vice-versa
            else:
                return None

        if include == Select.INCLUDE:
            sel_func = include_sel_func
        elif include == Select.EXCLUDE:
            sel_func = exclude_sel_func
        sel_func.exclude = not include
        sel_func.name = "Tuple select %s" % (tuple, )
        return sel_func

    def _glob_get_normal_sf(self, glob_str, include):
        """Return selection function based on glob_str

        The basic idea is to turn glob_str into a regular expression,
        and just use the normal regular expression.  There is a
        complication because the selection function should return '2'
        (scan) for directories which may contain a file which matches
        the glob_str.  So we break up the glob string into parts, and
        any file which matches an initial sequence of glob parts gets
        scanned.

        Thanks to Donovan Baarda who provided some code which did some
        things similar to this.

        """
        if glob_str.lower().startswith(b"ignorecase:"):
            def re_comp(r):
                return re.compile(r, re.I | re.S)
            glob_str = glob_str[len(b"ignorecase:"):]
        else:
            def re_comp(r):
                return re.compile(r, re.S)

        # matches what glob matches and any files in directory
        glob_comp_re = re_comp(b"^%b($|/)" % self._glob_to_re(glob_str))

        if glob_str.find(b"**") != -1:
            glob_str = glob_str[:glob_str.find(b"**") + 2]  # truncate after **

        scan_comp_re = re_comp(
            b"^(%s)$" % b"|".join(self._glob_get_prefix_res(glob_str)))

        def include_sel_func(rp):
            if glob_comp_re.match(rp.path):
                return 1
            elif scan_comp_re.match(rp.path):
                return 2
            else:
                return None

        def exclude_sel_func(rp):
            if glob_comp_re.match(rp.path):
                return 0
            else:
                return None

        # Check to make sure prefix is ok
        if not include_sel_func(self.rpath):
            raise FilePrefixError(glob_str)

        if include:
            return include_sel_func
        else:
            return exclude_sel_func

    def _glob_get_prefix_res(self, glob_str):
        """Return list of regexps equivalent to prefixes of glob_str"""

        glob_parts = glob_str.split(b"/")
        if b"" in glob_parts[1:
                             -1]:  # "" OK if comes first or last, as in /foo/
            raise GlobbingError(
                "Consecutive '/'s found in globbing string {gs}".format(
                    gs=safestr.to_str(glob_str)))

        prefixes = [
            b"/".join(glob_parts[:i + 1]) for i in range(len(glob_parts))
        ]
        # we must make exception for root "/", or "X:/" under Windows,
        # only dirs to end in slash
        if prefixes[0] == b"" or re.fullmatch(b"[a-zA-Z]:", prefixes[0]):
            prefixes[0] += b"/"
        return list(map(self._glob_to_re, prefixes))

    def _glob_to_re(self, pat):
        """
        Returned regular expression equivalent to shell glob pat

        Currently only the ?, *, [], and ** expressions are supported.
        Ranges like [a-z] are also currently unsupported.  These special
        characters can be quoted by prepending them with a backslash.

        This function taken with minor modifications from efnmatch.py
        by Donovan Baarda.
        """
        # trying to analyze bytes would be quite complicated hence back to str
        str_pat = os.fsdecode(pat)
        i, n, res = 0, len(str_pat), ''
        while i < n:
            c, s = str_pat[i], str_pat[i:i + 2]
            i = i + 1
            if c == '\\':
                res = res + re.escape(s[-1])
                i = i + 1
            elif s == '**':
                res = res + '.*'
                i = i + 1
            elif c == '*':
                res = res + '[^/]*'
            elif c == '?':
                res = res + '[^/]'
            elif c == '[':
                j = i
                if j < n and str_pat[j] in '!^':
                    j = j + 1
                if j < n and str_pat[j] == ']':
                    j = j + 1
                while j < n and str_pat[j] != ']':
                    j = j + 1
                if j >= n:
                    res = res + '\\['  # interpret the [ literally
                else:  # Deal with inside of [..]
                    stuff = str_pat[i:j].replace('\\', '\\\\')
                    i = j + 1
                    if stuff[0] in '!^':
                        stuff = '^' + stuff[1:]
                    res = res + '[' + stuff + ']'
            else:
                res = res + re.escape(c)
        return os.fsencode(res)  # but we want a bytes matching pattern


class FilterIter:
    """Filter rorp_iter using a Select object, removing excluded rorps"""

    def __init__(self, select, rorp_iter):
        """
        Constructor for FilterIter

        Input is the Select object to use and the iter of rorps to be
        filtered. The rorps will be converted to rps using the Select
        base.
        """
        self.rorp_iter = rorp_iter
        self.base_rp = select.rpath
        self.stored_rorps = []
        self.ITR = rorpiter.IterTreeReducer(_FilterIterITRB,
                                            [select.select_default,
                                             self.stored_rorps])
        self.itr_finished = 0

    def __iter__(self):
        return self

    def __next__(self):
        """Return next object, or StopIteration"""
        while not self.stored_rorps:
            try:
                next_rorp = next(self.rorp_iter)
            except StopIteration:
                if self.itr_finished:
                    raise
                else:
                    self.ITR.finish_processing()
                    self.itr_finished = 1
            else:
                next_rp = rpath.RPath(self.base_rp.conn, self.base_rp.base,
                                      next_rorp.index, next_rorp.data)
                self.ITR(next_rorp.index, next_rp, next_rorp)
        return self.stored_rorps.pop(0)


class _FilterIterITRB(rorpiter.ITRBranch):
    """ITRBranch used in above FilterIter class

    The reason this is necessary is because for directories sometimes
    we don't know whether a rorp is excluded until we see what is in
    the directory.

    """

    def __init__(self, select, rorp_cache):
        """Initialize _FilterIterITRB.  Called by IterTreeReducer.

        select should be the relevant Select object used to test the
        rps.  rorp_cache is the list rps should be appended to if they
        aren't excluded.

        """
        self.select, self.rorp_cache = select, rorp_cache
        self.branch_excluded = None
        self.base_queue = None  # holds branch base while examining contents

    def can_fast_process(self, index, next_rp, next_rorp):
        return not next_rp.isdir()

    def fast_process_file(self, index, next_rp, next_rorp):
        """For ordinary files, just append if select is positive"""
        if self.branch_excluded:
            return
        s = self.select(next_rp)
        if s == 1:
            if self.base_queue:
                self.rorp_cache.append(self.base_queue)
                self.base_queue = None
            self.rorp_cache.append(next_rorp)
        elif s != 0:
            raise ValueError("Unexpected select value {sel}.".format(sel=s))

    def start_process_directory(self, index, next_rp, next_rorp):
        s = self.select(next_rp)
        if s == 0:
            self.branch_excluded = 1
        elif s == 1:
            self.rorp_cache.append(next_rorp)
        elif s == 2:
            self.base_queue = next_rorp
        else:
            raise ValueError("Unexpected select value {sel}.".format(sel=s))


def get_prepared_selections(selections):
    """
    Accepts a list of selection tuple made of (selection method, parameter)

    Return a tuple of two lists, the first one being the modified selection
    list (for compatibility reasons), the 2nd one being a list containing the
    content of the selection files given on the command line.
    """

    # TODO this function returns the content as bytes, whereas the functions
    # above expect them as file pointer, this doesn't make much sense and
    # should be optimized, perhaps returning directly as list of file lines.
    # TODO the two lists returned could also be merged into one, the content
    # of the file just replacing the file name.
    select_opts = []
    select_data = []

    def sel_fl(filename):
        """
        Helper function for including/excluding filelists below
        """
        # TODO we should do this in pre_check so that we can earlier handle
        # any IO error, at the same time where we get rid of select_data
        if filename is True:  # we really mean the boolean True
            fp = sys.stdin.buffer
        else:
            fp = open(filename, "rb")  # files match paths hence bytes/bin
        buf = fp.read()
        fp.close()
        return buf

    if selections:
        # the following loop is a compatibility measure # compat200
        for selection in selections:
            if 'filelist' in selection[0]:
                if selection[0].endswith("-stdin"):
                    select_opts.append((
                        "--" + selection[0][:-6],  # remove '-stdin'
                        "standard input"))
                else:
                    select_opts.append(("--" + selection[0], selection[1]))
                select_data.append(sel_fl(selection[1]))
            else:
                select_opts.append(("--" + selection[0], selection[1]))

    return (select_opts, select_data)
