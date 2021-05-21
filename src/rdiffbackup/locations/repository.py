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
    log,
    restore,  # FIXME shouldn't be necessary!
    rpath,
    Security,
    SetConnections,
)


class Repo(locations.Location):
    """
    Represent a Backup Repository as created by rdiff-backup
    """
    def __init__(self, base_dir, force, must_be_writable, must_exist,
                 create_full_path=False, can_be_sub_path=False):
        """
        Initialize the repository class

        can_be_sub_path is True if the base_dir can actually be a repository,
        but also a sub-directory or even an increment file, mostly used for
        restore actions.
        """
        # if the base_dir can be a sub-file, we need to identify the actual
        # base directory of the repository
        if can_be_sub_path:
            self.orig_path = base_dir
            (base_dir, restore_index, restore_type) = \
                base_dir.get_repository_dirs()
            self.restore_index = restore_index
            self.restore_type = restore_type
            # we delay the error handling until the check step
        else:
            self.restore_index = None
            self.restore_type = None

        # Finish the initialization with the identified base_dir
        super().__init__(base_dir, force)
        self.create_full_path = create_full_path
        self.must_be_writable = must_be_writable
        self.must_exist = must_exist
        self.can_be_sub_path = can_be_sub_path
        self.data_dir = self.base_dir.append_path(b"rdiff-backup-data")
        self.incs_dir = self.data_dir.append_path(b"increments")

    def check(self):
        if self.can_be_sub_path and self.restore_type is None:
            # there is nothing to save, the user must first give a correct path
            return 1
        else:
            log.Log("Using repository '{re}'".format(re=self.base_dir),
                    log.INFO)
        ret_code = 0

        if self.must_exist and not self._is_existing():
            ret_code |= 1

        if self.must_be_writable and not self._is_writable():
            ret_code |= 1

        return ret_code

    def setup(self):
        if self.must_be_writable and not self._create():
            return 1

        if (self.can_be_sub_path
                and self.base_dir.conn is Globals.local_connection):
            Security.reset_restrict_path(self.base_dir)

        SetConnections.UpdateGlobal('rbdir', self.data_dir)  # compat200

        return 0  # all is good

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
            log.Log.FatalError(
                """Bad rdiff-backup-data dir on destination side

The rdiff-backup data directory
{dd}
exists, but we cannot find a valid current_mirror marker.  You can
avoid this message by removing the rdiff-backup-data directory;
however any data in it will be lost.

Probably this error was caused because the first rdiff-backup session
into a new directory failed.  If this is the case it is safe to delete
the rdiff-backup-data directory because there is no important
information in it.

""".format(dd=self.data_dir))
        elif len(curmir_incs) == 1:
            return False
        else:
            if not self.force:
                try:
                    curmir_incs[0].conn.regress.check_pids(curmir_incs)
                except OSError as exc:
                    log.Log.FatalError(
                        "Could not check if rdiff-backup is currently"
                        "running due to exception {ex}".format(ex=exc))
            assert len(curmir_incs) == 2, (
                "Found more than 2 current_mirror incs in '{ci}'.".format(
                    ci=self.data_dir))
            return True

    def regress(self):
        """
        Regress the backup repository in case the last backup failed

        This can/should be run before any action on the repository to start
        with a clean state.
        """
        log.Log("Previous backup seems to have failed, regressing "
                "destination now", log.WARNING)
        try:
            self.base_dir.conn.regress.Regress(self.base_dir)
            return 0
        except Security.Violation:
            log.Log(
                "Security violation while attempting to regress destination, "
                "perhaps due to --restrict-read-only or "
                "--restrict-update-only", log.ERROR)
            return 1

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

    def _is_existing(self):
        # check first that the directory itself exists
        if not super()._is_existing():
            return False

        if not self.data_dir.isdir():
            log.Log("Source directory '{sd}' doesn't have a sub-directory "
                    "'rdiff-backup-data'".format(sd=self.base_dir), log.ERROR)
            return False
        elif not self.incs_dir.isdir():
            log.Log("Data directory '{dd}' doesn't have an 'increments' "
                    "sub-directory".format(dd=self.data_dir),
                    log.WARNING)  # used to be normal  # compat200
            # return False # compat200
        return True

    def _is_writable(self):
        # check first that the directory itself is writable
        # (or doesn't yet exist)
        if not super()._is_writable():
            return False
        # if the target is a non-empty existing directory
        # without rdiff-backup-data sub-directory
        if (self.base_dir.lstat()
                and self.base_dir.isdir()
                and self.base_dir.listdir()
                and not self.data_dir.lstat()):
            if self.force:
                log.Log("Target path '{tp}' does not look like a rdiff-backup "
                        "repository but will be force overwritten".format(
                            tp=self.base_dir), log.WARNING)
            else:
                log.Log("Target path '{tp}' does not look like a rdiff-backup "
                        "repository, call with '--force' to overwrite".format(
                            tp=self.base_dir), log.ERROR)
                return False
        return True

    def _create(self):
        # create the underlying location/directory
        if not super()._create():
            return False

        # define a few essential subdirectories
        if not self.data_dir.lstat():
            try:
                self.data_dir.mkdir()
            except OSError as exc:
                log.Log("Could not create 'rdiff-backup-data' sub-directory "
                        "in base directory '{bd}' due to exception '{ex}'. "
                        "Please fix the access rights and retry.".format(
                            bd=self.base_dir, ex=exc), log.ERROR)
                return False
        elif self._is_failed_initial_backup():
            self._fix_failed_initial_backup()
        if not self.incs_dir.lstat():
            try:
                self.incs_dir.mkdir()
            except OSError as exc:
                log.Log("Could not create 'increments' sub-directory "
                        "in data directory '{dd}' due to exception '{ex}'. "
                        "Please fix the access rights and retry.".format(
                            dd=self.data_dir, ex=exc), log.ERROR)
                return False

        return True

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
        log.Log("Found interrupted initial backup in data directory {dd}. "
                "Removing...".format(dd=self.data_dir), log.NOTE)
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
                log.Log("Increments dir contains files", log.INFO)
                return
            except Security.Violation:
                log.Log("Server doesn't support resuming", log.WARNING)
                return

        # then delete all remaining files
        for file_name in rbdir_files:
            rp = self.data_dir.append_path(file_name)
            if not rp.isdir():  # Only remove files, not folders
                rp.delete()
