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
    FilenameMapping, Globals, log, selection, Security, Time,
)


class Repo(locations.Location):
    """
    Represent a Backup Repository as created by rdiff-backup
    """
    # is there an open logfile to close?
    logging_to_file = False

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
            (base_dir, ref_index, ref_type) = base_dir.get_repository_dirs()
            self.ref_index = ref_index
            self.ref_type = ref_type
            # we delay the error handling until the check step,
            # and as well the definition of ref_path and ref_inc
        else:
            self.ref_type = self.ref_index = None

        # Finish the initialization with the identified base_dir
        super().__init__(base_dir, force)
        self.create_full_path = create_full_path
        self.must_be_writable = must_be_writable
        self.must_exist = must_exist
        self.can_be_sub_path = can_be_sub_path
        self.data_dir = self.base_dir.append_path(b"rdiff-backup-data")
        self.incs_dir = self.data_dir.append_path(b"increments")
        self.lockfile = self.data_dir.append(locations.LOCK)
        self.has_been_locked = False

    def check(self):
        if self.can_be_sub_path:
            if self.ref_type is None:
                # nothing to save, the user must first give a correct path
                return Globals.RET_CODE_ERR
            else:
                self.ref_path = self.base_dir.new_index(self.ref_index)
                self.ref_inc = self.data_dir.append_path(b'increments',
                                                         self.ref_index)
        else:
            self.ref_path = self.ref_inc = None
            log.Log("Using repository '{re}'".format(re=self.base_dir),
                    log.INFO)
        ret_code = Globals.RET_CODE_OK

        if self.must_exist and not self._is_existing():
            ret_code |= Globals.RET_CODE_ERR

        if self.must_be_writable and not self._is_writable():
            ret_code |= Globals.RET_CODE_ERR

        return ret_code

    def setup(self, src_dir=None, owners_map=None, action_name=None):
        if self.must_be_writable and not self._create():
            return Globals.RET_CODE_ERR

        if (self.can_be_sub_path
                and self.base_dir.conn is Globals.local_connection):
            Security.reset_restrict_path(self.base_dir)

        Globals.set_all('rbdir', self.data_dir)  # compat200

        ret_code = Globals.RET_CODE_OK

        if Globals.get_api_version() >= 201:  # compat200
            if self.base_dir.conn is Globals.local_connection:
                # should be more efficient than going through the connection
                from rdiffbackup.locations import _repo_shadow
                self._shadow = _repo_shadow.RepoShadow
            else:
                self._shadow = self.base_dir.conn._repo_shadow.RepoShadow

            lock_result = self.lock()
            if lock_result is False:
                if self.force:
                    log.Log("Repository is locked by file {lf}, another "
                            "action is probably on-going. Enforcing anyway "
                            "at your own risk".format(lf=self.lockfile),
                            log.WARNING)
                else:
                    log.Log("Repository is locked by file {lf}, another "
                            "is probably on-going, or something went "
                            "wrong. Either wait, remove the lock "
                            "or use the --force option".format(
                                lf=self.lockfile), log.ERROR)
                    return Globals.RET_CODE_ERR
            elif lock_result is None:
                log.Log("Repository couldn't be locked by file {lf}, probably "
                        "because the repository was never written with "
                        "API >= 201, ignoring".format(lf=self.lockfile),
                        log.NOTE)

            self.fs_abilities = self.get_fs_abilities()
            if not self.fs_abilities:
                return Globals.RET_CODE_ERR
            else:
                log.Log("--- Repository file system capabilities ---\n"
                        + str(self.fs_abilities), log.INFO)

            if src_dir is None:
                self.remote_transfer = None  # just in case
                ret_code |= fs_abilities.SingleRepoSetGlobals(self)()
                if ret_code & Globals.RET_CODE_ERR:
                    return ret_code
            else:
                # FIXME this shouldn't be necessary, and the setting of variable
                # across the connection should happen through the shadow
                Globals.set_all("backup_writer", self.base_dir.conn)
                self.base_dir.conn.Globals.set_local("isbackup_writer", True)
                # this is the new way, more dedicated but not sufficient yet
                self.remote_transfer = (src_dir.base_dir.conn
                                        is not self.base_dir.conn)
                ret_code |= fs_abilities.Dir2RepoSetGlobals(src_dir, self)()
                if ret_code & Globals.RET_CODE_ERR:
                    return ret_code
            self.setup_quoting()
            self.setup_paths()

        if owners_map is not None:
            ret_code |= self.init_owners_mapping(**owners_map)
            if ret_code & Globals.RET_CODE_ERR:
                return ret_code

        if log.Log.verbosity > 0 and action_name:
            ret_code |= self._open_logfile(action_name, self.must_be_writable)
            if ret_code & Globals.RET_CODE_ERR:
                return ret_code

        return ret_code

    def exit(self):
        """
        Close the repository, mainly unlock it if it's been previously locked
        """
        self.unlock()
        if self.logging_to_file:
            log.Log.close_logfile()

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
                return Globals.RET_CODE_OK
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
            if self.ref_type:
                self.ref_path = FilenameMapping.get_quotedrpath(self.ref_path)
                self.ref_inc = FilenameMapping.get_quotedrpath(self.ref_inc)
        else:
            self.base_dir = map_filenames.get_quotedrpath(self.base_dir)
            self.data_dir = map_filenames.get_quotedrpath(self.data_dir)
            self.incs_dir = map_filenames.get_quotedrpath(self.incs_dir)
            if self.ref_type:
                self.ref_path = map_filenames.get_quotedrpath(self.ref_path)
                self.ref_inc = map_filenames.get_quotedrpath(self.ref_inc)

        Globals.set_all('rbdir', self.data_dir)  # compat200

        return True

    def setup_paths(self):
        """
        Shadow function for RepoShadow.setup_paths
        """
        return self._shadow.setup_paths(
            self.base_dir, self.data_dir, self.incs_dir)

    def get_fs_abilities(self):
        """
        Shadow function for RepoShadow.get_fs_abilities_readonly/write
        """
        if self.must_be_writable:
            # base dir can be _potentially_ writable but actually read-only
            # to map the actual rights of the root directory, whereas the
            # data dir is alway writable
            return self._shadow.get_fs_abilities_readwrite(self.data_dir)
        else:
            return self._shadow.get_fs_abilities_readonly(self.base_dir)

    def is_locked(self):
        """
        Shadow function for RepoShadow.is_locked
        """
        return self._shadow.is_locked(self.lockfile, self.must_be_writable)

    def lock(self):
        """
        Shadow function for RepoShadow.lock
        """
        return self._shadow.lock(self.lockfile, self.must_be_writable)

    def unlock(self):
        """
        Shadow function for RepoShadow.unlock
        """
        if hasattr(self, '_shadow'):
            return self._shadow.unlock(self.lockfile, self.must_be_writable)

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

        Note that this function won't catch an initial failed backup, this
        needs to be done during the repository creation phase.

        Return None if the repository can't be found or is new,
        True if it needs regressing, False otherwise.
        """
        # detect an initial repository which doesn't need a regression
        if not (self.base_dir.isdir() and self.data_dir.isdir()
                and self.incs_dir.isdir() and self.incs_dir.listdir()):
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

    def force_regress(self):
        """
        Try to fake a failed backup to force a regress

        Return True if the fake was succesful, else False, e.g. if the
        repository contains only the mirror and no increment.
        """
        inc_times = self.get_increment_times()
        if len(inc_times) < 2:
            log.Log(
                "Repository with only a mirror can't be forced to regress, "
                "just remove it and start from scratch",
                log.WARNING)
            return False
        mirror_time = self.get_mirror_time()
        if inc_times[-1] != mirror_time:
            log.Log(
                "Repository's increment times are inconsistent, "
                "it's too dangerous to force a regress",
                log.WARNING)
            return False
        self.touch_current_mirror(Time.timetostring(inc_times[-2]))
        return True

    def regress(self):
        """
        Regress the backup repository in case the last backup failed

        This can/should be run before any action on the repository to start
        with a clean state.
        """
        try:
            self._shadow.regress(self.base_dir, self.incs_dir)
            return Globals.RET_CODE_OK
        except Security.Violation:
            log.Log(
                "Security violation while attempting to regress destination, "
                "perhaps due to --restrict-read-only or "
                "--restrict-update-only", log.ERROR)
            return Globals.RET_CODE_ERR

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

    def get_sigs(self, source_iter, use_increment):
        """
        Shadow function for RepoShadow.get_sigs
        """
        return self._shadow.get_sigs(self.base_dir, source_iter,
                                     use_increment, self.remote_transfer)

    def apply(self, source_diffiter, previous_time):
        """
        Shadow function for RepoShadow.apply
        """
        return self._shadow.apply(
            self.base_dir, source_diffiter, self.incs_dir, previous_time)

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

    def init_loop(self, restore_time):
        """
        Shadow function for RepoShadow.init_loop
        """
        return self._shadow.init_loop(self.data_dir, self.ref_path,
                                      self.ref_inc, restore_time)

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

    def remove_increments_older_than(self, reftime):
        """
        Shadow function for RepoShadow.remove_increments_older_than
        """
        return self._shadow.remove_increments_older_than(self.data_dir, reftime)

    def list_files_changed_since(self, reftime):
        """
        Shadow function for RepoShadow.list_files_changed_since
        """
        return self._shadow.list_files_changed_since(
            self.base_dir, self.incs_dir, self.data_dir, reftime)

    def list_files_at_time(self, reftime):
        """
        Shadow function for RepoShadow.list_files_at_time
        """
        return self._shadow.list_files_at_time(
            self.base_dir, self.incs_dir, self.data_dir, reftime)

    def get_parsed_time(self, timestr):
        """
        Parse time string, potentially using the reference increment as anchor

        Returns None if the time string couldn't be parsed, else the time in
        seconds.
        The reference increment is used when the time string consists in a
        number of past backups.
        """
        try:
            if Globals.get_api_version() < 201:  # compat200
                return Time.genstrtotime(timestr, rp=self.ref_inc)
            else:
                sessions = self.get_increment_times(self.ref_inc)
                return Time.genstrtotime(timestr, session_times=sessions)
        except Time.TimeException as exc:
            log.Log("Time string '{ts}' couldn't be parsed "
                    "due to '{ex}'".format(ts=timestr, ex=exc), log.ERROR)
            return None

    def get_increments(self):
        """
        Return a list of increments (without size) with their time, type
        and basename.

        The list is sorted by increasing time stamp, meaning that the mirror
        is last in the list
        """
        incs_list = self.ref_inc.get_incfiles_list()
        incs = [{"time": inc.getinctime(),
                 "type": self._get_inc_type(inc),
                 "base": inc.dirsplit()[1].decode(errors="replace")}
                for inc in incs_list]

        # append the mirror itself
        mirror_time = self.get_mirror_time(must_exist=True)
        incs.append({
            "time": mirror_time,
            "type": self._get_file_type(self.ref_path),
            "base": self.ref_path.dirsplit()[1].decode(errors="replace")})

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
            mirror_select = selection.Select(self.ref_path)
            if not self.ref_index:  # must exclude rdiff-backup-directory
                mirror_select.parse_rbdir_exclude()
            return mirror_select.get_select_iter()

        def get_inc_select():
            """Return iterator of increment rpaths"""
            for base_inc in self.ref_inc.get_incfiles_list():
                yield base_inc
            if self.ref_inc.isdir():
                inc_select = selection.Select(self.ref_inc).get_select_iter()
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

    def init_and_get_loop(self, compare_time, src_iter=None):
        """
        Shadow function for RepoShadow.init_and_get_loop
        """
        return self._shadow.init_and_get_loop(
            self.data_dir, self.ref_path, self.ref_inc, compare_time, src_iter)

    def verify(self, verify_time):
        """
        Shadow function for RepoShadow.verify
        """
        return self._shadow.verify(self.data_dir, self.ref_path,
                                   self.ref_inc, verify_time)

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

        if self._is_failed_initial_backup():
            # poor man's locking mechanism to protect starting backup
            # independently from the API version
            self.lockfile.setdata()
            if self.lockfile.lstat():
                if self.force:
                    log.Log("An initial backup in a strange state with "
                            "lockfile {lf}. Enforcing continuation, "
                            "hopefully you know what you're doing".format(
                                lf=self.lockfile), log.WARNING)
                else:
                    log.Log("An initial backup in a strange state with "
                            "lockfile {lf}. Either it's just an initial backup "
                            "running, wait a bit and try again later, or "
                            "something is really wrong. --force will remove "
                            "the complete repo, at your own risk".format(
                                lf=self.lockfile), log.ERROR)
                    return False
            log.Log("Found interrupted initial backup in data directory {dd}. "
                    "Removing...".format(dd=self.data_dir), log.NOTE)
            self._clean_failed_initial_backup()

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
            # If we have no current_mirror marker, and one or less error logs
            # and metadata files, we most likely have a failed backup.
            return not mirror_markers and len(error_logs) <= 1 and \
                len(metadata_mirrors) <= 1
        return False

    def _clean_failed_initial_backup(self):
        """
        Clear the given rdiff-backup-data if possible, it's faster than
        trying to do a regression, which would probably anyway fail.
        """
        self.data_dir.delete()  # setdata is implicit
        self.incs_dir.setdata()

    def _open_logfile(self, base_name, must_be_writable):
        """
        Open logfile with base name in the repository
        """
        try:  # the target repository must be writable
            logfile = self.data_dir.append(base_name + ".log")
            log.Log.open_logfile(logfile)
        except (log.LoggerError, Security.Violation) as exc:
            if must_be_writable:
                log.Log("Unable to open logfile '{lf}' due to '{ex}'".format(
                    lf=logfile, ex=exc), log.ERROR)
                return Globals.RET_CODE_ERR
            else:
                log.Log("Unable to open logfile '{lf}' due to '{ex}'".format(
                    lf=logfile, ex=exc), log.WARNING)
                return Globals.RET_CODE_WARN
        else:
            self.logging_to_file = True
        return Globals.RET_CODE_OK

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
