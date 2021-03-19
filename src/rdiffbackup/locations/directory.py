# Copyright 2021 the rdiff-backup project
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
A built-in rdiff-backup action plug-in to test servers.

This plug-in tests that all remote locations are properly reachable and
usable for a back-up.
"""

import sys
from rdiffbackup import locations


class Dir():
    pass


class ReadDir(Dir, locations.ReadLocation):
    selections = []
    select_files = []

    def check(self):
        return_code = 0
        # check that the source exists and is a directory
        if not self.base_dir.lstat():
            self.log("Source path {rp} does not exist".format(
                rp=self.base_dir.get_safepath()), self.log.ERROR)
            return_code |= 1
        elif not self.base_dir.isdir():
            self.log("Source path {rp} is not a directory".format(
                rp=self.base_dir.get_safepath()), self.log.ERROR)
            return_code |= 1
        return return_code

    def set_select(self, selections):
        """
        Accepts a list of selection tuple made of (selection method, parameter)

        Saves the selections list and makes it ready for usage on the source
        side over its connection.
        """
        def sel_fl(filename):
            """
            Helper function for including/excluding filelists below
            """
            if filename is True:  # we really mean the boolean True
                return sys.stdin.buffer
            try:
                return open(filename, "rb")  # files match paths hence bytes/bin
            except IOError:
                self.log.FatalError("Error opening file %s" % filename)

        if selections:
            # the following loop is a compatibility measure # compat200
            for selection in selections:
                if 'filelist' in selection[0]:
                    if selection[0].endswith("-stdin"):
                        self.selections.append((
                            "--" + selection[0][:-6],  # remove '-stdin'
                            "standard input"))
                    else:
                        self.selections.append(("--" + selection[0],
                                                selection[1]))
                    self.select_files.append(sel_fl(selection[1]))
                else:
                    self.selections.append(("--" + selection[0], selection[1]))
        else:
            self.selections = []

        # FIXME not sure we couldn't support symbolic links nowadays on Windows
        if self.base_dir.conn.os.name == 'nt':
            self.log("Symbolic links excluded by default on Windows",
                     self.log.INFO)
            self.selections.append(("--exclude-symbolic-links", None))
        self.base_dir.conn.backup.SourceStruct.set_source_select(
            self.base_dir, self.selections, *self.select_files)
