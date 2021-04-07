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
Generic classes for locations
"""

import os


class Location():

    def __init__(self, base_dir, log, force):
        self.base_dir = base_dir
        self.log = log
        self.force = force


class ReadLocation(Location):

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

    def setup(self):
        return 0


class WriteLocation(Location):

    def __init__(self, base_dir, log, force, create_full_path):
        super().__init__(base_dir, log, force)
        self.create_full_path = create_full_path

    def check(self):
        ret_code = 0

        # check that target is a directory or doesn't exist
        if (self.base_dir.lstat() and not self.base_dir.isdir()):
            if self.force:
                self.log(
                    "Target {rp} exists but isn't a directory, "
                    "and will be force deleted".format(
                        rp=self.base_dir.get_safepath()),
                    self.log.WARNING)
            else:
                self.log(
                    "Target {rp} exists and is not a directory, "
                    "call with '--force' to overwrite".format(
                        rp=self.base_dir.get_safepath()),
                    self.log.ERROR)
                ret_code |= 1

        return ret_code

    def setup(self):
        # make sure the target directory is present
        try:
            # if the target exists and isn't a directory, force delete it
            if (self.base_dir.lstat() and not self.base_dir.isdir()
                    and self.force):
                self.base_dir.delete()

            # if the target doesn't exist, create it
            if not self.base_dir.lstat():
                if self.create_full_path:
                    self.base_dir.makedirs()
                else:
                    self.base_dir.mkdir()
                self.base_dir.chmod(0o700)  # only read-writable by its owner
        except os.error:
            self.log("Unable to delete and/or create directory {rp}".format(
                rp=self.base_dir.get_safepath()), self.log.ERROR)
            return 1

        return 0  # all is good
