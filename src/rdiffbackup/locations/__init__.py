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

All those classes should be considered abstract and not instantiated directly.
"""

import os
from rdiff_backup import log


class Location():
    """
    Abstract location class representing a user@hostname::/dir location
    """

    def __init__(self, base_dir, force):
        self.base_dir = base_dir
        self.force = force

    def _is_existing(self):
        """
        check that the location exists and is a directory
        """
        if not self.base_dir.lstat():
            log.Log("Source path {sp} does not exist".format(
                sp=self.base_dir), log.ERROR)
            return False
        elif not self.base_dir.isdir():
            log.Log("Source path {sp} is not a directory".format(
                sp=self.base_dir), log.ERROR)
            return False
        return True

    def _is_writable(self):
        """
        check that target is a directory or doesn't exist
        """
        # TODO The writable aspect hasn't yet been implemented
        if (self.base_dir.lstat() and not self.base_dir.isdir()):
            if self.force:
                log.Log("Target path {tp} exists but isn't a directory, "
                        "and will be force deleted".format(
                            tp=self.base_dir), log.WARNING)
            else:
                log.Log("Target path {tp} exists and is not a directory, "
                        "call with '--force' to overwrite".format(
                            tp=self.base_dir), log.ERROR)
                return False
        return True

    def _create(self):
        """
        create the location if it doesn't yet exist
        """
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
            log.Log("Unable to delete and/or create directory {di}".format(
                di=self.base_dir), log.ERROR)
            return False

        return True  # all is good


class ReadLocation(Location):
    """
    Abstract read-only, pre-existing location class
    """

    def check(self):
        if self._is_existing():
            return 0
        else:
            return 1

    def setup(self):
        return 0


class WriteLocation(Location):
    """
    Abstract writable location class, possibly not pre-existing
    """

    def __init__(self, base_dir, force, create_full_path):
        super().__init__(base_dir, force)
        self.create_full_path = create_full_path

    def check(self):
        if self._is_writable():
            return 0
        else:
            return 1

    def setup(self):
        # make sure the target directory is present
        if self._create():
            return 0
        else:
            return 1
