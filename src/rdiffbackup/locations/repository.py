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

from rdiffbackup import locations

from rdiff_backup import (
    FilenameMapping,
    Globals,
    restore,  # FIXME shouldn't be necessary!
    rpath,
    Security,
    SetConnections,
)


class Repo():
    """
    Represent a Backup Repository as created by rdiff-backup
    """

    def get_mirror_time(self):
        """
        Return time in seconds of previous mirror if possible

        Return -1 if there is more than one mirror,
        or 0 if there is no backup yet.
        """
        incbase = self.data_dir.append_path(b"current_mirror")
        mirror_rps = restore.get_inclist(incbase)  # FIXME is probably better here
        if mirror_rps:
            if len(mirror_rps) == 1:
                return mirror_rps[0].getinctime()
            else:  # there is a failed backup and 2+ current_mirror files
                return -1
        else:  # it's the first backup
            return 0  # is always in the past

    def init_quoting(self, chars_to_quote):
        """
        Set QuotedRPath versions of important RPaths if chars_to_quote is set.

        Return True if quoting needed to be done, False else.
        """
        # FIXME the problem is that the chars_to_quote can come from the command
        # line but can also be a value coming from the repository itself,
        # set globally by the fs_abilities.xxx_set_globals functions.
        if not Globals.chars_to_quote:
            return False

        FilenameMapping.set_init_quote_vals()  # compat200

        self.base_dir = FilenameMapping.get_quotedrpath(self.base_dir)
        self.data_dir = FilenameMapping.get_quotedrpath(self.data_dir)
        self.incs_dir = FilenameMapping.get_quotedrpath(self.incs_dir)

        SetConnections.UpdateGlobal('rbdir', self.data_dir)  # compat200

        return True

    def needs_regress(self):
        """
        Checks if the repository contains a previously failed backup and needs
        to be regressed

        Return None if the repository can't be found,
        True if it needs regressing, False otherwise.
        """
        if not self.base_dir.isdir() or not self.data_dir.isdir():
            return None
        for filename in self.data_dir.listdir():
            # check if we can find any file of importance
            if filename not in [
                    b'chars_to_quote', b'special_escapes',
                    b'backup.log', b'increments'
            ]:
                break
        else:  # This may happen the first backup just after we test for quoting
            if not self.incs_dir.isdir() or not self.incs_dir.listdir():
                return None
        curmirroot = self.data_dir.append(b"current_mirror")
        curmir_incs = restore.get_inclist(curmirroot)  # FIXME belongs here
        if not curmir_incs:
            self.log.FatalError(
                """Bad rdiff-backup-data dir on destination side

The rdiff-backup data directory
{data}
exists, but we cannot find a valid current_mirror marker.  You can
avoid this message by removing the rdiff-backup-data directory;
however any data in it will be lost.

Probably this error was caused because the first rdiff-backup session
into a new directory failed.  If this is the case it is safe to delete
the rdiff-backup-data directory because there is no important
information in it.

""".format(data=self.data_dir.get_safepath()))
        elif len(curmir_incs) == 1:
            return False
        else:
            if not self.force:
                try:
                    curmir_incs[0].conn.regress.check_pids(curmir_incs)
                except (OSError, IOError) as exc:
                    self.log.FatalError(
                        "Could not check if rdiff-backup is currently"
                        "running due to\n{exc}".format(exc=exc))
            assert len(curmir_incs) == 2, (
                "Found more than 2 current_mirror incs in '{rp!s}'.".format(
                    rp=self.data_dir))
            return True

    def regress(self):
        """
        Regress the backup repository in case the last backup failed

        This can/should be run before any action on the repository to start
        with a clean state.
        """
        self.log(
            "Previous backup seems to have failed, regressing "
            "destination now.", self.log.WARNING)
        try:
            self.base_dir.conn.regress.Regress(self.base_dir)
            return 0
        except Security.Violation:
            self.log(
                "Security violation while attempting to regress destination, "
                "perhaps due to --restrict-read-only or "
                "--restrict-update-only.", self.log.ERROR)
            return 1


class ReadRepo(Repo, locations.ReadLocation):
    """
    A read-only Repository as source for a restore or other read actions.
    """

    def __init__(self, base_dir, log, force):
        # the base_dir can actually be a repository, but also a sub-directory
        # or even an increment file, hence we need to process it accordingly
        self.orig_path = base_dir
        (base_dir, restore_index, restore_type) = base_dir.get_repository_dirs()
        super().__init__(base_dir, log, force)
        if restore_type:
            self.data_dir = self.base_dir.append_path(b"rdiff-backup-data")
            self.incs_dir = self.data_dir.append_path(b"increments")
        self.restore_index = restore_index
        self.restore_type = restore_type

    def check(self):
        if self.restore_type is None:
            # there is nothing to save, the user must first give a correct path
            return 1
        else:
            self.log("Using repository '{rp}'".format(
                rp=self.base_dir.get_safepath()), self.log.INFO)
        ret_code = super().check()
        if not self.data_dir.isdir():
            self.log("Source '{rp}' doesn't have an 'rdiff-backup-data' "
                     "sub-directory".format(rp=self.base_dir.get_safepath()),
                     self.log.ERROR)
            ret_code |= 1
        elif not self.incs_dir.isdir():
            self.log("Data directory '{rp}' doesn't have an 'increments' "
                     "sub-directory".format(rp=self.data_dir.get_safepath()),
                     self.log.WARNING)  # used to be normal  # compat200
            # ret_code |= 1  # compat200
        return ret_code

    def setup(self):
        ret_code = super().setup()
        if ret_code != 0:
            return ret_code

        if self.base_dir.conn is Globals.local_connection:
            Security.reset_restrict_path(self.base_dir)
        SetConnections.UpdateGlobal('rbdir', self.data_dir)  # compat200

        return 0  # all is good

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

        # FIXME we're retransforming bytes into a file pointer
        if select_opts:
            self.base_dir.conn.restore.MirrorStruct.set_mirror_select(
                target_rp, select_opts, *list(map(io.BytesIO, select_data)))


class WriteRepo(Repo, locations.WriteLocation):
    """
    A writable/updatable Repository as target for a backup
    """

    def __init__(self, base_dir, log, force, create_full_path):
        super().__init__(base_dir, log, force, create_full_path)
        self.data_dir = self.base_dir.append_path(b"rdiff-backup-data")
        self.incs_dir = self.data_dir.append_path(b"increments")

    def check(self):
        ret_code = super().check()

        # if the target is a non-empty existing directory
        # without rdiff-backup-data sub-directory
        if (self.base_dir.lstat()
                and self.base_dir.isdir()
                and self.base_dir.listdir()
                and not self.data_dir.lstat()):
            if self.force:
                self.log(
                    "Target '{repo}' does not look like a rdiff-backup "
                    "repository but will be force overwritten".format(
                        repo=self.base_dir.get_safepath()),
                    self.log.WARNING)
            else:
                self.log(
                    "Target '{repo}' does not look like a rdiff-backup "
                    "repository, "
                    "call with '--force' to overwrite".format(
                        repo=self.base_dir.get_safepath()),
                    self.log.ERROR)
                ret_code |= 1

        return ret_code

    def setup(self):
        ret_code = super().setup()
        if ret_code != 0:
            return ret_code

        Globals.rbdir = self.data_dir  # compat200

        # define a few essential subdirectories
        if not self.data_dir.lstat():
            try:
                self.data_dir.mkdir()
            except (OSError, IOError) as exc:
                self.log("Could not create 'rdiff-backup-data' sub-directory "
                         "in '{rp}' due to '{exc}'. "
                         "Please fix the access rights and retry.".format(
                             rp=self.base_dir, exc=exc), self.log.ERROR)
                return 1
        elif self._is_failed_initial_backup():
            self._fix_failed_initial_backup()
        if not self.incs_dir.lstat():
            try:
                self.incs_dir.mkdir()
            except (OSError, IOError) as exc:
                self.log("Could not create 'increments' sub-directory "
                         "in '{rp}' due to '{exc}'. "
                         "Please fix the access rights and retry.".format(
                             rp=self.data_dir, exc=exc), self.log.ERROR)
                return 1

        SetConnections.UpdateGlobal('rbdir', self.data_dir)  # compat200

        return 0

    def _is_failed_initial_backup(self):
        """
        Returns True if it looks like the rdiff-backup-data directory contains
        a failed initial backup, else False.
        """
        if self.data_dir.lstat():
            rbdir_files = self.data_dir.listdir()
            mirror_markers = [
                x for x in rbdir_files if x.startswith(b"current_mirror")
            ]
            error_logs = [x for x in rbdir_files if x.startswith(b"error_log")]
            metadata_mirrors = [
                x for x in rbdir_files if x.startswith(b"mirror_metadata")
            ]
            # If we have no current_mirror marker, and the increments directory
            # is empty, we most likely have a failed backup.
            return not mirror_markers and len(error_logs) <= 1 and \
                len(metadata_mirrors) <= 1
        return False

    def _fix_failed_initial_backup(self):
        """
        Clear the given rdiff-backup-data if possible, it's faster than
        trying to do a regression, which would probably anyway fail.
        """
        self.log("Found interrupted initial backup in {rp}. "
                 "Removing...".format(rp=self.data_dir.get_safepath()),
                 self.log.NOTE)
        rbdir_files = self.data_dir.listdir()

        # Try to delete the increments dir first
        if b'increments' in rbdir_files:
            rbdir_files.remove(b'increments')
            rp = self.data_dir.append(b'increments')
            # FIXME I don't really understand the logic here: either it's
            # a failed initial backup and we can remove everything, or we
            # should fail and not continue.
            try:
                rp.conn.rpath.delete_dir_no_files(rp)
            except rpath.RPathException:
                self.log("Increments dir contains files.", self.log.INFO)
                return
            except Security.Violation:
                self.log("Server doesn't support resuming.", self.log.WARNING)
                return

        # then delete all remaining files
        for file_name in rbdir_files:
            rp = self.data_dir.append_path(file_name)
            if not rp.isdir():  # Only remove files, not folders
                rp.delete()
