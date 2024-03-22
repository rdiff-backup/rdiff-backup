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
from rdiff_backup import Globals, log
from rdiffbackup.locations import fs_abilities
from rdiffbackup.locations.map import owners as map_owners


class Location:
    """
    Abstract location class representing a user@hostname::/dir location
    """

    def __init__(self, orig_path, values):
        self.orig_path = orig_path
        self.values = values
        # self.base_dir must be defined by the child class
        # self._shadow must be defined by the child class

    def __str__(self):
        return str(self.base_dir)

    def check(self):
        return self._shadow.check()

    def setup(self):
        return self._shadow.setup()

    def get_fs_abilities(self):
        return self._shadow.get_fs_abilities()

    def exit(self):
        """
        Put the location in a consistent state before leaving it
        """
        pass


class LocationShadow:
    """
    Abstract class representing the remote side of a location.

    It is used as a singleton representing a directory or a repository,
    meaning all functions must be class methods
    """

    @classmethod
    def init(cls, orig_path, values, must_be_writable, must_exist):
        """
        Initialize the location based on values not depending on other locations

        Returns the base directory of the location as derived from the original
        path given by the user
        """
        cls._orig_path = orig_path
        cls._base_dir = orig_path
        cls._values = values
        cls._must_be_writable = must_be_writable
        cls._must_exist = must_exist
        return cls._base_dir

    @classmethod
    def check(cls):
        """
        Check anything which can be checked about the location

        Returns error codes as defined with Globals.RET_CODE_*
        """
        ret_code = Globals.RET_CODE_OK

        if cls._must_exist and not cls._is_existing():
            ret_code |= Globals.RET_CODE_ERR

        if cls._must_be_writable and not cls._is_writable():
            ret_code |= Globals.RET_CODE_ERR

        return ret_code

    @classmethod
    def setup(cls):
        """
        Setup the location, preparing it for usage.
        The main difference to the init function is that it can be used to
        link two locations together (e.g. for backup resp. restore from
        one to the other).

        Returns error codes as defined with Globals.RET_CODE_*
        """
        if cls._must_be_writable and not cls._create():
            return Globals.RET_CODE_ERR

        return Globals.RET_CODE_OK

    @classmethod
    def get_fs_abilities(cls):
        return fs_abilities.detect_fs_abilities(
            cls._base_dir, cls._must_be_writable
        )

    @classmethod
    def _is_existing(cls):
        """
        check that the location exists and is a directory
        """
        if not cls._base_dir.lstat():
            log.Log(
                "Source path {sp} does not exist".format(sp=cls._base_dir), log.ERROR
            )
            return False
        elif not cls._base_dir.isdir():
            log.Log(
                "Source path {sp} is not a directory".format(sp=cls._base_dir),
                log.ERROR,
            )
            return False
        return True

    @classmethod
    def _is_writable(cls):
        """
        check that target is a directory or doesn't exist
        """
        # TODO The writable aspect hasn't yet been implemented
        if cls._base_dir.lstat() and not cls._base_dir.isdir():
            if cls._values["force"]:
                log.Log(
                    "Target path {tp} exists but isn't a directory, "
                    "and will be force deleted".format(tp=cls._base_dir),
                    log.WARNING,
                )
            else:
                log.Log(
                    "Target path {tp} exists and is not a directory, "
                    "call with '--force' to overwrite".format(tp=cls._base_dir),
                    log.ERROR,
                )
                return False
        return True

    @classmethod
    def _create(cls):
        """
        create the location if it doesn't yet exist
        """
        try:
            # if the target exists and isn't a directory, force delete it
            if (
                cls._base_dir.lstat()
                and not cls._base_dir.isdir()
                and cls._values["force"]
            ):
                cls._base_dir.delete()

            # if the target doesn't exist, create it
            if not cls._base_dir.lstat():
                if cls._values["create_full_path"]:
                    cls._base_dir.makedirs()
                else:
                    cls._base_dir.mkdir()
                cls._base_dir.chmod(0o700)  # only read-writable by its owner
        except os.error:
            log.Log(
                "Unable to delete and/or create directory {di}".format(
                    di=cls._base_dir
                ),
                log.ERROR,
            )
            return False

        return True  # all is good

    @classmethod
    def _init_owners_mapping(
        cls, users_map=None, groups_map=None, preserve_num_ids=None
    ):
        if users_map is None:
            users_map = cls._values.get("user_mapping_file")
        if groups_map is None:
            groups_map = cls._values.get("group_mapping_file")
        if preserve_num_ids is None:
            preserve_num_ids = cls._values.get("preserve_num_ids", False)
        map_owners.init_users_mapping(users_map, preserve_num_ids)
        map_owners.init_groups_mapping(groups_map, preserve_num_ids)
        return Globals.RET_CODE_OK
