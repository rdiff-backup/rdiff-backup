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
from rdiffbackup.locations import fs_abilities
from rdiffbackup.locations.map import filenames as map_filenames

from rdiff_backup import (
    FilenameMapping,
    Globals,
    log,
    rpath,
    selection,
    Security,
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

    def setup(self, src_dir=None, owners_map=None):
        if self.must_be_writable and not self._create():
            return 1

        if (self.can_be_sub_path
                and self.base_dir.conn is Globals.local_connection):
            Security.reset_restrict_path(self.base_dir)

        Globals.set_all('rbdir', self.data_dir)  # compat200

        if Globals.get_api_version() >= 201:  # compat200
            if self.base_dir.conn is Globals.local_connection:
                # should be more efficient than going through the connection
                from rdiffbackup.locations import _repo_shadow
                self._shadow = _repo_shadow.RepoShadow
            else:
                self._shadow = self.base_dir.conn._repo_shadow.RepoShadow
            if self.must_be_writable:
                self.fs_abilities = self._shadow.get_fs_abilities_readwrite(
                    self.base_dir)
            else:
                self.fs_abilities = self._shadow.get_fs_abilities_readonly(
                    self.base_dir)
            if not self.fs_abilities:
                return 1  # something was wrong
            else:
                log.Log("--- Repository file system capabilities ---\n"
                        + str(self.fs_abilities), log.INFO)

            if src_dir is None:
                self.remote_transfer = None  # just in case
                ret_code = fs_abilities.SingleRepoSetGlobals(self)()
                if ret_code != 0:
                    return ret_code
            else:
                # FIXME this shouldn't be necessary, and the setting of variable
                # across the connection should happen through the shadow
                Globals.set_all("backup_writer", self.base_dir.conn)
                self.base_dir.conn.Globals.set_local("isbackup_writer", True)
                # this is the new way, more dedicated but not sufficient yet
                self.remote_transfer = (src_dir.base_dir.conn
                                        is not self.base_dir.conn)
                ret_code = fs_abilities.Dir2RepoSetGlobals(src_dir, self)()
                if ret_code != 0:
                    return ret_code
            self.setup_quoting()
            self.setup_paths()

        if owners_map is not None:
            ret_code = self.init_owners_mapping(**owners_map)
            if ret_code != 0:
                return ret_code

        return 0  # all is good

    def get_mirror_time(self, must_exist=False, refresh=False):
        """
        Shadow function for RepoShadow.get_mirror_time
        """
        if Globals.get_api_version() < 201:  # compat200
            incbase = self.data_dir.append_path(b"current_mirror")
            mirror_rps = incbase.get_incfiles_list()
            if mirror_rps:
                if len(mirror_rps) == 1:
                    return mirror_rps[0].getinctime()
                else:  # there is a failed backup and 2+ current_mirror files
                    return -1
            else:  # it's the first backup
                return 0  # is always in the past
        else:
            return self._shadow.get_mirror_time(must_exist, refresh)

    def setup_quoting(self):
        """
        Set QuotedRPath versions of important RPaths if chars_to_quote is set.

        Return True if quoting needed to be done, False else.
        """
        # FIXME the problem is that the chars_to_quote can come from the command
        # line but can also be a value coming from the repository itself,
        # set globally by the fs_abilities.xxx_set_globals functions.
        if not Globals.chars_to_quote:
            return False

        if Globals.get_api_version() < 201:  # compat200
            FilenameMapping.set_init_quote_vals()
            self.base_dir = FilenameMapping.get_quotedrpath(self.base_dir)
            self.data_dir = FilenameMapping.get_quotedrpath(self.data_dir)
            self.incs_dir = FilenameMapping.get_quotedrpath(self.incs_dir)
        else:
            self.base_dir = map_filenames.get_quotedrpath(self.base_dir)
            self.data_dir = map_filenames.get_quotedrpath(self.data_dir)
            self.incs_dir = map_filenames.get_quotedrpath(self.incs_dir)

        Globals.set_all('rbdir', self.data_dir)  # compat200

        return True

    def setup_paths(self):
        """
        Shadow function for RepoShadow.setup_paths
        """
        return self._shadow.setup_paths(
            self.base_dir, self.data_dir, self.incs_dir)

    def needs_regress(self):
        """
        Shadow function for RepoShadow.needs_regress
        """
        return self._shadow.needs_regress(
            self.base_dir, self.data_dir, self.incs_dir, self.force)

    def needs_regress_compat200(self):
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
        curmir_incs = curmirroot.get_incfiles_list()
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
                        "running due to exception '{ex}'".format(ex=exc))
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
            if Globals.get_api_version() >= 201:  # compat200
                self._shadow.set_select(
                    target_rp, select_opts, *list(map(io.BytesIO, select_data)))
            else:
                self.base_dir.conn.restore.MirrorStruct.set_mirror_select(
                    target_rp, select_opts, *list(map(io.BytesIO, select_data)))

    def set_rorp_cache(self, source_iter, use_increment):
        """
        Shadow function for RepoShadow.set_rorp_cache
        """
        return self._shadow.set_rorp_cache(self.base_dir, source_iter,
                                           use_increment)

    def get_sigs(self):
        """
        Shadow function for RepoShadow.get_sigs
        """
        return self._shadow.get_sigs(self.base_dir, self.remote_transfer)

    def patch_or_increment(self, source_diffiter, previous_time):
        """
        Shadow function for RepoShadow.patch and .patch_and_increment
        """
        if previous_time:
            return self._shadow.patch_and_increment(
                self.base_dir, source_diffiter, self.incs_dir, previous_time)
        else:
            return self._shadow.patch(
                self.base_dir, source_diffiter)

    def touch_current_mirror(self, current_time_str):
        """
        Shadow function for RepoShadow.touch_current_mirror
        """
        return self._shadow.touch_current_mirror(self.data_dir,
                                                 current_time_str)

    def remove_current_mirror(self):
        """
        Shadow function for RepoShadow.remove_current_mirror
        """
        return self._shadow.remove_current_mirror(self.data_dir)

    def close_statistics(self, end_time):
        """
        Shadow function for RepoShadow.close_statistics
        """
        return self._shadow.close_statistics(end_time)

    def initialize_restore(self, restore_time):
        """
        Shadow function for RepoShadow.initialize_restore
        """
        return self._shadow.initialize_restore(self.data_dir, restore_time)

    def initialize_rf_cache(self, inc_rpath):
        """
        Shadow function for RepoShadow.initialize_rf_cache
        """
        return self._shadow.initialize_rf_cache(
            self.base_dir.new_index(self.restore_index), inc_rpath)

    def close_rf_cache(self):
        """
        Shadow function for RepoShadow.close_rf_cache
        """
        return self._shadow.close_rf_cache()

    def get_diffs(self, target_iter):
        """
        Shadow function for RepoShadow.get_diffs
        """
        return self._shadow.get_diffs(target_iter)

    def remove_increments_older_than(self, time):
        """
        Shadow function for RepoShadow.remove_increments_older_than
        """
        return self._shadow.remove_increments_older_than(self.base_dir, time)

    def list_files_changed_since(self, time):
        """
        Shadow function for RepoShadow.list_files_changed_since
        """
        return self._shadow.list_files_changed_since(
            self.base_dir, self.incs_dir, self.data_dir, time)

    def list_files_at_time(self, time):
        """
        Shadow function for RepoShadow.list_files_at_time
        """
        return self._shadow.list_files_at_time(
            self.base_dir, self.incs_dir, self.data_dir, time)

    def get_increments(self):
        """
        Return a list of increments (without size) with their time, type
        and basename.

        The list is sorted by increasing time stamp, meaning that the mirror
        is last in the list
        """
        inc_base = self.data_dir.append_path(b'increments', self.restore_index)
        incs_list = inc_base.get_incfiles_list()
        incs = [{"time": inc.getinctime(),
                 "type": self._get_inc_type(inc),
                 "base": inc.dirsplit()[1].decode(errors="replace")}
                for inc in incs_list]

        # append the mirror itself
        mirror_time = self.get_mirror_time(must_exist=True)
        mirror_path = self.base_dir.new_index(self.restore_index)
        incs.append({
            "time": mirror_time,
            "type": self._get_file_type(mirror_path),
            "base": mirror_path.dirsplit()[1].decode(errors="replace")})

        return sorted(incs, key=lambda x: x["time"])

    def get_increments_sizes(self):
        """
        Return list of triples summarizing the size of all the increments

        The list contains tuples of the form (time, size, cumulative size)
        """

        def get_total(rp_iter):
            """Return the total size of everything in rp_iter"""
            total = 0
            for rp in rp_iter:
                total += rp.getsize()
            return total

        def get_time_dict(inc_iter):
            """Return dictionary pairing times to total size of incs"""
            time_dict = {}
            for inc in inc_iter:
                if not inc.isincfile():
                    continue
                t = inc.getinctime()
                if t not in time_dict:
                    time_dict[t] = 0
                time_dict[t] += inc.getsize()
            return time_dict

        def get_mirror_select():
            """Return iterator of mirror rpaths"""
            mirror_base = self.base_dir.new_index(self.restore_index)
            mirror_select = selection.Select(mirror_base)
            if not self.restore_index:  # must exclude rdiff-backup-directory
                mirror_select.parse_rbdir_exclude()
            return mirror_select.set_iter()

        def get_inc_select():
            """Return iterator of increment rpaths"""
            inc_base = self.data_dir.append_path(b'increments',
                                                 self.restore_index)
            for base_inc in inc_base.get_incfiles_list():
                yield base_inc
            if inc_base.isdir():
                inc_select = selection.Select(inc_base).set_iter()
                for inc in inc_select:
                    yield inc

        def get_summary_triples(mirror_total, time_dict):
            """Return list of triples (time, size, cumulative size)"""
            triples = []

            cur_mir_base = self.data_dir.append(b'current_mirror')
            mirror_time = (cur_mir_base.get_incfiles_list())[0].getinctime()
            triples.append({"time": mirror_time, "size": mirror_total,
                            "total_size": mirror_total})

            inc_times = list(time_dict.keys())
            inc_times.sort()
            inc_times.reverse()
            cumulative_size = mirror_total
            for inc_time in inc_times:
                size = time_dict[inc_time]
                cumulative_size += size
                triples.append({"time": inc_time, "size": size,
                                "total_size": cumulative_size})
            return triples

        mirror_total = get_total(get_mirror_select())
        time_dict = get_time_dict(get_inc_select())
        triples = get_summary_triples(mirror_total, time_dict)

        return sorted(triples, key=lambda x: x["time"])

    def get_increment_times(self, rp=None):
        """
        Shadow function for RepoShadow.get_increment_times()
        """
        return self._shadow.get_increment_times(rp)

    def init_and_get_iter(self, compare_time):
        """
        Shadow function for RepoShadow.init_and_get_iter
        """
        mirror_rp = self.base_dir.new_index(self.restore_index)
        inc_rp = self.data_dir.append_path(b'increments', self.restore_index)
        return self._shadow.init_and_get_iter(self.data_dir, mirror_rp, inc_rp,
                                              compare_time)

    def attach_files(self, src_iter, compare_time):
        """
        Shadow function for RepoShadow.attach_files
        """
        mirror_rp = self.base_dir.new_index(self.restore_index)
        inc_rp = self.data_dir.append_path(b'increments', self.restore_index)
        return self._shadow.attach_files(self.data_dir, src_iter,
                                         mirror_rp, inc_rp, compare_time)

    def verify(self, verify_time):
        """
        Shadow function for RepoShadow.verify
        """
        mirror_rp = self.base_dir.new_index(self.restore_index)
        inc_rp = self.data_dir.append_path(b'increments', self.restore_index)
        return self._shadow.verify(self.data_dir, mirror_rp, inc_rp,
                                   verify_time)

    def get_chars_to_quote(self):
        """
        Shadow function for RepoShadow.get_config for chars_to_quote
        """
        return self._shadow.get_config(self.data_dir, "chars_to_quote")

    def set_chars_to_quote(self, chars_to_quote):
        """
        Shadow function for RepoShadow.set_config for chars_to_quote
        """
        return self._shadow.set_config(self.data_dir, "chars_to_quote",
                                       chars_to_quote)

    def get_special_escapes(self):
        """
        Shadow function for RepoShadow.get_config for special_escapes
        """
        return self._shadow.get_config(self.data_dir, "special_escapes")

    def set_special_escapes(self, special_escapes):
        """
        Shadow function for RepoShadow.set_config for special_escapes
        """
        return self._shadow.set_config(self.data_dir, "special_escapes",
                                       special_escapes)

    def update_quoting(self):
        """
        Shadow function for RepoShadow.update_quoting
        """
        return self._shadow.update_quoting(self.base_dir)

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

    @classmethod
    def _get_inc_type(cls, inc):
        """Return file type increment represents"""
        assert inc.isincfile(), (
            "File '{inc!s}' must be an increment.".format(inc=inc))
        inc_type = inc.getinctype()
        if inc_type == b"dir":
            return "directory"
        elif inc_type == b"diff":
            return "regular"
        elif inc_type == b"missing":
            return "missing"
        elif inc_type == b"snapshot":
            return cls._get_file_type(inc)
        else:
            log.Log.FatalError("Unknown type '{ut}' of increment '{ic}'".format(
                ut=inc_type, ic=inc))

    @classmethod
    def _get_file_type(cls, rp):
        """Returns one of "regular", "directory", "missing", or "special"."""
        if not rp.lstat():
            return "missing"
        elif rp.isdir():
            return "directory"
        elif rp.isreg():
            return "regular"
        else:
            return "special"
