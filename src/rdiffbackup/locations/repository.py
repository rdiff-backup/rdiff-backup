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
A location module to define repository classes as created by rdiff-backup
"""

import io
import os
import re

from rdiffbackup.locations import fs_abilities, location

from rdiff_backup import Globals, log


class Repo(location.Location):
    """
    Represent a Backup Repository as created by rdiff-backup
    """

    def __init__(
        self,
        orig_path,
        values,
        must_be_writable,
        must_exist,
        can_be_sub_path=False,
    ):
        """
        Initialize the repository class

        can_be_sub_path is True if the orig_path can actually be a repository,
        but also a sub-directory or even an increment file, mostly used for
        restore actions.
        """
        super().__init__(orig_path, values)
        if orig_path.conn is Globals.local_connection:
            # should be more efficient than going through the connection
            from rdiffbackup.locations import _repo_shadow

            self._shadow = _repo_shadow.RepoShadow
        else:
            self._shadow = orig_path.conn._repo_shadow.RepoShadow
        (self.base_dir, self.ref_index, self.ref_type) = self._shadow.init(
            orig_path, values, must_be_writable, must_exist, can_be_sub_path
        )
        self.must_be_writable = must_be_writable
        self.must_exist = must_exist

    def setup(self, src_dir=None):
        # we have a local transfer is there is no src_dir _or_
        # if both dir and repo have the same connection
        self.local_transfer = (
            (not src_dir) or (src_dir.base_dir.conn is self.base_dir.conn)
        )

        ret_code = self._shadow.setup()
        if ret_code & Globals.RET_CODE_ERR:
            return ret_code

        self.fs_abilities = self.get_fs_abilities()
        if not self.fs_abilities:
            return Globals.RET_CODE_ERR
        else:
            log.Log(
                "--- Repository file system capabilities ---\n"
                + str(self.fs_abilities),
                log.INFO,
            )

        if src_dir is None:
            ret_code |= fs_abilities.SingleRepoSetGlobals(self)()
            if ret_code & Globals.RET_CODE_ERR:
                return ret_code
        else:
            # FIXME this shouldn't be necessary, and the setting of variable
            # across the connection should happen through the shadow
            Globals.set_all("backup_writer", self.base_dir.conn)
            self.base_dir.conn.Globals.set_local("isbackup_writer", True)
            # this is the new way, more dedicated but not sufficient yet
            ret_code |= fs_abilities.Dir2RepoSetGlobals(src_dir, self)()
            if ret_code & Globals.RET_CODE_ERR:
                return ret_code
        self.base_dir = self.setup_quoting()

        if self.values.get("not_compressed_regexp") is not None:
            ret_code |= self.setup_not_compressed_regexp(
                self.values["not_compressed_regexp"]
            )
            if ret_code & Globals.RET_CODE_ERR:
                return ret_code

        ret_code |= self.init_owners_mapping(
            users_map=self.values.get("user_mapping_file"),
            groups_map=self.values.get("group_mapping_file"),
            preserve_num_ids=self.values.get("preserve_numerical_ids", False),
        )
        if ret_code & Globals.RET_CODE_ERR:
            return ret_code

        return ret_code

    def exit(self):
        """
        Close the repository
        """
        # FIXME this shouldn't be necessary, and the setting of variable
        # across the connection should happen through the shadow
        Globals.set_all("backup_writer", None)
        self.base_dir.conn.Globals.set_local("isbackup_writer", False)
        self._shadow.exit()

    def get_mirror_time(self, must_exist=False, refresh=False):
        """
        Shadow function for RepoShadow.get_mirror_time
        """
        return self._shadow.get_mirror_time(must_exist, refresh)

    def setup_quoting(self):
        """
        Shadow function for RepoShadow.setup_quoting
        """
        return self._shadow.setup_quoting()

    @classmethod  # so that we can easily use in tests
    def setup_not_compressed_regexp(cls, not_compressed_regexp=None):
        """
        Sets the not_compressed_regexp setting globally
        """
        not_compressed_regexp = os.fsencode(not_compressed_regexp)
        try:
            not_compressed_regexp = re.compile(not_compressed_regexp)
        except re.error:
            log.Log(
                "No compression regular expression '{ex}' doesn't "
                "compile".format(ex=not_compressed_regexp),
                log.ERROR,
            )
            return Globals.RET_CODE_ERR

        Globals.set_all("not_compressed_regexp", not_compressed_regexp)

        return Globals.RET_CODE_OK

    def needs_regress(self):
        """
        Shadow function for RepoShadow.needs_regress
        """
        return self._shadow.needs_regress()

    def regress(self):
        """
        Shadow function for RepoShadow.regress
        """
        return self._shadow.regress()

    def force_regress(self):
        """
        Shadow function for RepoShadow.force_regress
        """
        return self._shadow.force_regress()

    def set_select(self, select_opts, select_data, target_rp):
        """
        Set the selection and selection data on the repository

        Accepts a tuple of two lists:
        * one of selection tuple made of (selection method, parameter)
        * and one of the content of the selection files
        And an rpath of the target directory to map the selection criteria.

        Saves the selections list and makes it ready for usage on the source
        side over its connection.
        """

        # compat201 we're retransforming bytes into a file pointer
        if select_opts:
            self._shadow.set_select(
                target_rp, select_opts, *list(map(io.BytesIO, select_data))
            )

    def get_sigs(self, source_iter, use_increment):
        """
        Shadow function for RepoShadow.get_sigs
        """
        return self._shadow.get_sigs(source_iter, use_increment, self.remote_transfer)

    def apply(self, source_diffiter, previous_time):
        """
        Shadow function for RepoShadow.apply
        """
        return self._shadow.apply(source_diffiter, previous_time)

    def touch_current_mirror(self, current_time_str):
        """
        Shadow function for RepoShadow.touch_current_mirror
        """
        return self._shadow.touch_current_mirror(current_time_str)

    def remove_current_mirror(self):
        """
        Shadow function for RepoShadow.remove_current_mirror
        """
        return self._shadow.remove_current_mirror()

    def close_statistics(self, end_time):
        """
        Shadow function for RepoShadow.close_statistics
        """
        return self._shadow.close_statistics(end_time)

    def init_loop(self, restore_time):
        """
        Shadow function for RepoShadow.init_loop
        """
        return self._shadow.init_loop(restore_time)

    def finish_loop(self):
        """
        Shadow function for RepoShadow.finish_loop
        """
        return self._shadow.finish_loop()

    def get_diffs(self, target_iter):
        """
        Shadow function for RepoShadow.get_diffs
        """
        return self._shadow.get_diffs(target_iter)

    def remove_increments_older_than(self, time_string=None, show_sizes=None):
        """
        Shadow function for RepoShadow.remove_increments_older_than
        """
        return self._shadow.remove_increments_older_than(time_string, show_sizes)

    def list_files_changed_since(self, reftime):
        """
        Shadow function for RepoShadow.list_files_changed_since
        """
        return self._shadow.list_files_changed_since(reftime)

    def list_files_at_time(self, reftime):
        """
        Shadow function for RepoShadow.list_files_at_time
        """
        return self._shadow.list_files_at_time(reftime)

    def get_increments(self):
        """
        Shadow function for RepoShadow.get_increments
        """
        return self._shadow.get_increments()

    def get_increments_sizes(self):
        """
        Shadow function for RepoShadow.get_increments_sizes
        """
        return self._shadow.get_increments_sizes()

    def get_parsed_time(self, timestr):
        """
        Shadow function for RepoShadow.get_parsed_time
        """
        return self._shadow.get_parsed_time(timestr)

    def get_increment_times(self, rp=None):
        """
        Shadow function for RepoShadow.get_increment_times()
        """
        return self._shadow.get_increment_times(rp)

    def init_and_get_loop(self, compare_time, src_iter=None):
        """
        Shadow function for RepoShadow.init_and_get_loop
        """
        return self._shadow.init_and_get_loop(compare_time, src_iter)

    def verify(self, verify_time):
        """
        Shadow function for RepoShadow.verify
        """
        return self._shadow.verify(verify_time)

    def get_chars_to_quote(self):
        """
        Shadow function for RepoShadow.get_config for chars_to_quote
        """
        return self._shadow.get_config("chars_to_quote")

    def set_chars_to_quote(self, chars_to_quote):
        """
        Shadow function for RepoShadow.set_config for chars_to_quote
        """
        return self._shadow.set_config("chars_to_quote", chars_to_quote)

    def get_special_escapes(self):
        """
        Shadow function for RepoShadow.get_config for special_escapes
        """
        return self._shadow.get_config("special_escapes")

    def set_special_escapes(self, special_escapes):
        """
        Shadow function for RepoShadow.set_config for special_escapes
        """
        return self._shadow.set_config("special_escapes", special_escapes)
