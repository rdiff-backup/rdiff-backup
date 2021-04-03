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

import io
from rdiffbackup import locations


class Dir():
    pass


class ReadDir(Dir, locations.ReadLocation):
    selections = []
    select_files = []

    def set_select(self, select_opts, select_data):
        """
        Set the selection and selection data on the directory

        Accepts a tuple of two lists:
        * one of selection tuple made of (selection method, parameter)
        * and one of the content of the selection files

        Saves the selections list and makes it ready for usage on the source
        side over its connection.
        """

        # FIXME not sure we couldn't support symbolic links nowadays on Windows
        if self.base_dir.conn.os.name == 'nt':
            self.log("Symbolic links excluded by default on Windows",
                     self.log.NOTE)
            select_opts.append(("--exclude-symbolic-links", None))
        # FIXME we're retransforming bytes into a file pointer
        self.base_dir.conn.backup.SourceStruct.set_source_select(
            self.base_dir, select_opts, *list(map(io.BytesIO, select_data)))


class WriteDir(Dir, locations.WriteLocation):

    def check(self):
        ret_code = super().check()

        # if the target is a non-empty existing directory
        if (self.base_dir.lstat()
                and self.base_dir.isdir()
                and self.base_dir.listdir()):
            if self.force:
                self.log(
                    "Target {rp} exists and isn't empty, "
                    "content might be force overwritten by restore".format(
                        rp=self.base_dir.get_safepath()),
                    self.log.WARNING)
            else:
                self.log(
                    "Target {rp} exists and isn't empty, "
                    "call with '--force' to overwrite".format(
                        rp=self.base_dir.get_safepath()),
                    self.log.ERROR)
                ret_code |= 1

        return ret_code

    def set_select(self, select_opts, select_data):
        """
        Set the selection and selection data on the directory

        Accepts a tuple of two lists:
        * one of selection tuple made of (selection method, parameter)
        * and one of the content of the selection files

        Saves the selections list and makes it ready for usage on the source
        side over its connection.
        """

        # FIXME we're retransforming bytes into a file pointer
        if select_opts:
            self.base_dir.conn.restore.TargetStruct.set_target_select(
                self.base_dir, select_opts, *list(map(io.BytesIO, select_data)))
