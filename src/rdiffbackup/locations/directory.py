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
from rdiffbackup.locations import fs_abilities
from rdiff_backup import Globals, log


class ReadDir(locations.Location):

    def __init__(self, orig_path, values):
        super().__init__(orig_path, values)
        if orig_path.conn is Globals.local_connection:
            # should be more efficient than going through the connection
            from rdiffbackup.locations import _dir_shadow

            self._shadow = _dir_shadow.ReadDirShadow
        else:
            self._shadow = orig_path.conn._dir_shadow.ReadDirShadow
        self.base_dir = self._shadow.init(
            orig_path, values, must_be_writable=False, must_exist=True
        )

    def setup(self):
        ret_code = super().setup()
        if ret_code & Globals.RET_CODE_ERR:
            return ret_code

        self.fs_abilities = self.get_fs_abilities()
        if not self.fs_abilities:
            return ret_code | Globals.RET_CODE_ERR
        else:
            log.Log(
                "--- Read directory file system capabilities ---\n"
                + str(self.fs_abilities),
                log.INFO,
            )

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

        is_windows = self.base_dir.conn.platform.system() == "Windows"

        # FIXME not sure we couldn't support symbolic links nowadays on Windows
        # knowing that it would require specific handling when reading the link:
        #   File "rdiff_backup\rpath.py", line 771, in symlink
        #   TypeError: symlink: src should be string, bytes or os.PathLike, not NoneType
        # I suspect that not all users can read symlinks with os.readlink
        if is_windows and ("--exclude-symbolic-links", None) not in select_opts:
            log.Log("Symbolic links excluded on Windows", log.NOTE)
            select_opts.insert(0, ("--exclude-symbolic-links", None))
        self._shadow.set_select(
            self.base_dir, select_opts, *list(map(io.BytesIO, select_data))
        )

    def get_select(self):
        """
        Shadow function for ReadDirShadow.get_source_select
        """
        return self._shadow.get_select()

    def get_diffs(self, dest_sigiter):
        """
        Shadow function for ReadDirShadow.get_diffs
        """
        return self._shadow.get_diffs(dest_sigiter)

    def compare_meta(self, repo_iter):
        """
        Shadow function for ReadDirShadow.compare_meta
        """
        return self._shadow.compare_meta(repo_iter)

    def compare_hash(self, repo_iter):
        """
        Shadow function for ReadDirShadow.compare_hash
        """
        return self._shadow.compare_hash(repo_iter)

    def compare_full(self, repo_iter):
        """
        Shadow function for ReadDirShadow.compare_full
        """
        return self._shadow.compare_full(repo_iter)


class WriteDir(locations.Location):

    def __init__(self, orig_path, values):
        super().__init__(orig_path, values)
        if orig_path.conn is Globals.local_connection:
            # should be more efficient than going through the connection
            from rdiffbackup.locations import _dir_shadow

            self._shadow = _dir_shadow.WriteDirShadow
        else:
            self._shadow = orig_path.conn._dir_shadow.WriteDirShadow
        self.base_dir = self._shadow.init(
            orig_path, values, must_be_writable=True, must_exist=False
        )

    def setup(self, src_repo):
        ret_code = super().setup()
        if ret_code & Globals.RET_CODE_ERR:
            return ret_code

        self.fs_abilities = self.get_fs_abilities()
        if not self.fs_abilities:
            return ret_code | Globals.RET_CODE_ERR
        else:
            log.Log(
                "--- Write directory file system capabilities ---\n"
                + str(self.fs_abilities),
                log.INFO,
            )
        ret_code |= fs_abilities.Repo2DirSetGlobals(src_repo, self)()
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
            self._shadow.set_select(
                select_opts, *list(map(io.BytesIO, select_data))
            )

    def get_sigs_select(self):
        """
        Shadow function for WriteDirShadow.get_sigs_select
        """
        return self._shadow.get_sigs_select()

    def apply(self, source_diff_iter):
        """
        Shadow function for WriteDirShadow.apply
        """
        return self._shadow.apply(source_diff_iter)
