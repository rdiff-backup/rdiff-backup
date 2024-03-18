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

from rdiffbackup.locations import fs_abilities, location
from rdiff_backup import Globals, log


class ReadDir(location.Location):
    def __init__(self, orig_path, values):
        super().__init__(orig_path, values)
        if orig_path.conn is Globals.local_connection:
            # should be more efficient than going through the connection
            from rdiffbackup.locations import _dir_shadow

            self._shadow = _dir_shadow.ReadDirShadow
        else:
            self._shadow = orig_path.conn._dir_shadow.ReadDirShadow
        # initiate an existing directory, only for reading
        self.base_dir = self._shadow.init(orig_path, values, False, True)

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

    def set_select(self):
        """
        Shadow function for ReadDirShadow.set_select
        """
        self._shadow.set_select()

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


class WriteDir(location.Location):
    def __init__(self, orig_path, values):
        super().__init__(orig_path, values)
        if orig_path.conn is Globals.local_connection:
            # should be more efficient than going through the connection
            from rdiffbackup.locations import _dir_shadow

            self._shadow = _dir_shadow.WriteDirShadow
        else:
            self._shadow = orig_path.conn._dir_shadow.WriteDirShadow
        # initiate a writable potentially non-existing directory
        self.base_dir = self._shadow.init(orig_path, values, True, False)

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

        if ret_code & Globals.RET_CODE_ERR:
            return ret_code

        return ret_code

    def set_select(self):
        """
        Shadow function for WriteDirShadow.set_select
        """
        return self._shadow.set_select()

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
