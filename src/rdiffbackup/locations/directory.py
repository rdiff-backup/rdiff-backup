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


class Dir():
    pass


class ReadDir(Dir, locations.ReadLocation):

    def setup(self):
        ret_code = super().setup()
        if ret_code & Globals.RET_CODE_ERR:
            return ret_code

        if Globals.get_api_version() >= 201:  # compat200
            if self.base_dir.conn is Globals.local_connection:
                # should be more efficient than going through the connection
                from rdiffbackup.locations import _dir_shadow
                self._shadow = _dir_shadow.ReadDirShadow
            else:
                self._shadow = self.base_dir.conn._dir_shadow.ReadDirShadow
            self.fs_abilities = self.get_fs_abilities()
            if not self.fs_abilities:
                return ret_code | Globals.RET_CODE_ERR
            else:
                log.Log("--- Read directory file system capabilities ---\n"
                        + str(self.fs_abilities), log.INFO)

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

        if Globals.get_api_version() < 201:  # compat200
            is_windows = self.base_dir.conn.os.name == "nt"
        else:
            is_windows = self.base_dir.conn.platform.system() == "Windows"

        # FIXME not sure we couldn't support symbolic links nowadays on Windows
        # knowing that it would require specific handling when reading the link:
        #   File "rdiff_backup\rpath.py", line 771, in symlink
        #   TypeError: symlink: src should be string, bytes or os.PathLike, not NoneType
        # I suspect that not all users can read symlinks with os.readlink
        if (is_windows
                and ("--exclude-symbolic-links", None) not in select_opts):
            log.Log("Symbolic links excluded by default on Windows",
                    log.NOTE)
            select_opts.insert(0, ("--exclude-symbolic-links", None))
        if Globals.get_api_version() < 201:  # compat200
            self.base_dir.conn.backup.SourceStruct.set_source_select(
                self.base_dir, select_opts, *list(map(io.BytesIO, select_data)))
        else:  # FIXME we're retransforming bytes into a file pointer
            self._shadow.set_select(self.base_dir, select_opts,
                                    *list(map(io.BytesIO, select_data)))

    def get_fs_abilities(self):
        """
        Shadow function for ReadDirShadow.get_fs_abilities
        """
        return self._shadow.get_fs_abilities(self.base_dir)

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
        return self._shadow.compare_full(self.base_dir, repo_iter)


class WriteDir(Dir, locations.WriteLocation):

    def setup(self, src_repo, owners_map=None):
        ret_code = super().setup()
        if ret_code & Globals.RET_CODE_ERR:
            return ret_code

        if Globals.get_api_version() >= 201:  # compat200
            if self.base_dir.conn is Globals.local_connection:
                # should be more efficient than going through the connection
                from rdiffbackup.locations import _dir_shadow
                self._shadow = _dir_shadow.WriteDirShadow
            else:
                self._shadow = self.base_dir.conn._dir_shadow.WriteDirShadow
            self.fs_abilities = self.get_fs_abilities()
            if not self.fs_abilities:
                return ret_code | Globals.RET_CODE_ERR
            else:
                log.Log("--- Write directory file system capabilities ---\n"
                        + str(self.fs_abilities), log.INFO)

            return ret_code | fs_abilities.Repo2DirSetGlobals(src_repo, self)()

        if owners_map is not None:
            ret_code |= self.init_owners_mapping(**owners_map)
            if ret_code & Globals.RET_CODE_ERR:
                return ret_code

        return ret_code

    def check(self):
        ret_code = super().check()

        # if the target is a non-empty existing directory
        if (self.base_dir.lstat()
                and self.base_dir.isdir()
                and self.base_dir.listdir()):
            if self.force:
                log.Log("Target path {tp} exists and isn't empty, content "
                        "might be force overwritten by restore".format(
                            tp=self.base_dir), log.WARNING)
                ret_code |= Globals.RET_CODE_WARN
            else:
                log.Log("Target path {tp} exists and isn't empty, "
                        "call with '--force' to overwrite".format(
                            tp=self.base_dir), log.ERROR)
                ret_code |= Globals.RET_CODE_ERR

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
            if Globals.get_api_version() >= 201:  # compat200
                self._shadow.set_select(self.base_dir, select_opts,
                                        *list(map(io.BytesIO, select_data)))
            else:
                self.base_dir.conn.restore.TargetStruct.set_target_select(
                    self.base_dir, select_opts,
                    *list(map(io.BytesIO, select_data)))

    def get_fs_abilities(self):
        """
        Shadow function for WriteDirShadow.get_fs_abilities
        """
        return self._shadow.get_fs_abilities(self.base_dir)

    def get_sigs_select(self):
        """
        Shadow function for WriteDirShadow.get_sigs_select
        """
        return self._shadow.get_sigs_select(self.base_dir)

    def apply(self, source_diff_iter):
        """
        Shadow function for WriteDirShadow.apply
        """
        return self._shadow.apply(self.base_dir, source_diff_iter)
