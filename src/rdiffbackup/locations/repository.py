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

import os

from rdiffbackup import locations

from rdiff_backup import (
    FilenameMapping,
    Globals,
    restore,  # FIXME shouldn't be necessary!
    rpath,
    Security,
    SetConnections,
    Time,
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


class ReadRepo(Repo, locations.ReadLocation):
    """
    A writable/updatable Repository as target for a backup
    """

    def __init__(self, base_dir, log, force):
        super().__init__(base_dir, log, force)
        self.data_dir = self.base_dir.append_path(b"rdiff-backup-data")
        self.incs_dir = self.data_dir.append_path(b"increments")


class WriteRepo(Repo, locations.WriteLocation):
    """
    A writable/updatable Repository as target for a backup
    """

    def __init__(self, base_dir, log, force, create_full_path):
        super().__init__(base_dir, log, force, create_full_path)
        self.data_dir = self.base_dir.append_path(b"rdiff-backup-data")
        self.incs_dir = self.data_dir.append_path(b"increments")

    def check(self):
        return_code = 0
        # check that target is a directory or doesn't exist
        if (self.base_dir.lstat() and not self.base_dir.isdir()):
            if self.force:
                self.log(
                    "Destination {rp} exists but isn't a directory, "
                    "and will be force deleted".format(
                        rp=self.base_dir.get_safepath()),
                    self.log.WARNING)
            else:
                self.log(
                    "Destination {rp} exists and is not a directory, "
                    "call with '--force' to overwrite".format(
                        rp=self.base_dir.get_safepath()),
                    self.log.ERROR)
                return_code |= 1
        # if the target is a non-empty existing directory
        # without rdiff-backup-data sub-directory
        elif (self.base_dir.lstat()
              and self.base_dir.isdir()
              and self.base_dir.listdir()):
            if self.data_dir.lstat():
                previous_time = self.get_mirror_time()
                if previous_time >= Time.curtime:
                    self.log("Time of last backup is not in the past. "
                             "This is probably caused by running two backups "
                             "in less than a second. "
                             "Wait a second and try again.",
                             self.log.ERROR)
                    return_code |= 1
            else:
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
                    return_code |= 1
        return return_code

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

    def init_quoting(self, chars_to_quote):
        """
        Set QuotedRPath versions of important RPaths if chars_to_quote is set.

        Return True if quoting needed to be done, False else.
        """
        if not chars_to_quote:
            return False

        SetConnections.UpdateGlobal(  # compat200
            'rbdir', FilenameMapping.get_quotedrpath(self.data_dir))
        self.incs_dir = FilenameMapping.get_quotedrpath(self.incs_dir)
        self.base_dir = FilenameMapping.get_quotedrpath(self.base_dir)

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
        except Security.Violation:
            self.log.FatalError(
                "Security violation while attempting to regress destination, "
                "perhaps due to --restrict-read-only or "
                "--restrict-update-only.")

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
                 self.log.DEFAULT)
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
