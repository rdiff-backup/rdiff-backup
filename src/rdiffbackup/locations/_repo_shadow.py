# Copyright 2002, 2003 Ben Escoto
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
A shadow repository is called like this because like a shadow it does
what the local representation of the repository is telling it to do, but
it has no real life of itself, i.e. it has only class methods and can't
be instantiated.
"""

import errno
import io
import os
import re
import socket
import tempfile
import yaml
from rdiff_backup import (
    C,
    Globals,
    hash,
    iterfile,
    log,
    Rdiff,
    robust,
    rorpiter,
    rpath,
    Security,
    selection,
    statistics,
    Time,
)
from rdiffbackup import meta_mgr
from rdiffbackup.locations import fs_abilities, increment, location
from rdiffbackup.locations.map import filenames as map_filenames
from rdiffbackup.locations.map import hardlinks as map_hardlinks
from rdiffbackup.locations.map import longnames as map_longnames
from rdiffbackup.singletons import consts, generics
from rdiffbackup.utils import locking, simpleps

# ### COPIED FROM BACKUP ####


# @API(RepoShadow, 201)
class RepoShadow(location.LocationShadow):
    """
    Shadow repository for the local repository representation
    """

    # If selection command line arguments given, use Select here
    _select = None
    # This will be set to the time of the current mirror
    _mirror_time = None
    # This will be set to the exact time to restore to (not restore_to_time)
    _restore_time = None
    # _regress_time should be set to the time we want to regress back to
    # (usually the time of the last successful backup)
    _regress_time = None
    # This should be set to the latest unsuccessful backup time
    _unsuccessful_backup_time = None

    # keep the lock file open until the lock can be released
    _lockfd = None

    _configs = {
        "chars_to_quote": {"type": bytes},
        "special_escapes": {"type": set},
    }

    LOCK_MODE = {
        True: {
            "open": "r+",
            "truncate": "w",
            "lock": locking.LOCK_EX | locking.LOCK_NB,
        },
        False: {"open": "r", "lock": locking.LOCK_SH | locking.LOCK_NB},
    }

    # @API(RepoShadow.init, 300)
    @classmethod
    def init(
        cls,
        orig_path,
        values,
        must_be_writable,
        must_exist,
        can_be_sub_path=False,
        check_time=False,
    ):
        # if the base_dir can be a sub-file, we need to identify the actual
        # base directory of the repository
        cls._orig_path = orig_path
        if can_be_sub_path:
            (base_dir, ref_index, ref_type) = cls._get_repository_dirs(orig_path)
            cls._base_dir = base_dir
            cls._ref_index = ref_index
            cls._ref_type = ref_type
        else:
            cls._base_dir = orig_path
            cls._ref_index = ()
            cls._ref_type = None
        cls._data_dir = cls._base_dir.append_path(b"rdiff-backup-data")
        cls._incs_dir = cls._data_dir.append_path(b"increments")
        cls._lockfile = cls._data_dir.append(b"lock.yml")
        if can_be_sub_path:
            if cls._ref_type is None:
                # nothing to save, the user must first give a correct path
                log.Log.FatalError(
                    "Something was wrong with the given path '{gp}'".format(
                        gp=orig_path
                    )
                )
            else:
                cls._ref_path = cls._base_dir.new_index(cls._ref_index)
                cls._ref_inc = cls._data_dir.append_path(b"increments", cls._ref_index)
        else:
            cls._ref_path = cls._base_dir
            cls._ref_inc = cls._data_dir.append_path(b"increments", cls._ref_index)
            log.Log("Using repository '{re}'".format(re=cls._base_dir), log.INFO)
        cls._values = values
        cls._must_be_writable = must_be_writable
        cls._must_exist = must_exist
        cls._can_be_sub_path = can_be_sub_path
        cls._check_time = check_time
        cls._has_been_locked = False
        # we need this to be able to use multiple times the class
        cls._mirror_time = None
        cls._restore_time = None
        cls._regress_time = None
        cls._unsuccessful_backup_time = None
        cls._logging_to_file = None

        return (cls._base_dir, cls._ref_index, cls._ref_type)

    # @API(RepoShadow.check, 300)  # inherited

    # @API(RepoShadow.setup, 300)
    @classmethod
    def setup(cls):
        if cls._must_be_writable:
            if not cls._create():
                return consts.RET_CODE_ERR
        if cls._check_time and Globals.current_time <= cls.get_mirror_time():
            log.Log("The last backup is not in the past. Aborting.", log.ERROR)
            return consts.RET_CODE_ERR
        Security.reset_restrict_path(cls._base_dir)
        lock_result = cls._lock()
        ret_code = consts.RET_CODE_OK
        if lock_result is False:
            if cls._values["force"]:
                log.Log(
                    "Repository is locked by file {lf}, another "
                    "action is probably on-going. Enforcing anyway "
                    "at your own risk".format(lf=cls._lockfile),
                    log.WARNING,
                )
            else:
                log.Log(
                    "Repository is locked by file {lf}, another "
                    "is probably on-going, or something went "
                    "wrong. Either wait, remove the lock "
                    "or use the --force option".format(lf=cls._lockfile),
                    log.ERROR,
                )
                return consts.RET_CODE_ERR
        elif lock_result is None:
            log.Log(
                "Repository couldn't be locked by file {lf}, probably "
                "because the repository was never written with "
                "API >= 201, ignoring".format(lf=cls._lockfile),
                log.NOTE,
            )
        ret_code |= cls._init_owners_mapping()
        if ret_code & consts.RET_CODE_ERR:
            return ret_code
        ret_code |= increment.init(
            cls._values.get("compression"),
            cls._values.get("not_compressed_regexp"),
        )
        if ret_code & consts.RET_CODE_ERR:
            return ret_code
        return ret_code

    # @API(RepoShadow.setup_finish, 300)
    @classmethod
    def setup_finish(cls):
        """
        Finish the repository setup, because the quoting must be done before
        files are created, and because quoting depends on the file system
        abilities also from the directory (?)

        Returns the potentially quoted base directory
        """
        cls._setup_quoting()
        map_longnames.setup(cls._data_dir)
        cls._setup_logging()
        return cls._base_dir

    @classmethod
    def _setup_quoting(cls):
        """
        Set QuotedRPath versions of important RPaths if chars_to_quote is set.

        Returns True if quoting has been done, False if not necessary
        """
        # FIXME the problem is that the chars_to_quote can come from the command
        # line but can also be a value coming from the repository itself,
        # set globally by the fs_abilities.xxx_set_globals functions.
        if not Globals.chars_to_quote:
            return False

        cls._base_dir = map_filenames.get_quotedrpath(cls._base_dir)
        cls._data_dir = map_filenames.get_quotedrpath(cls._data_dir)
        cls._incs_dir = map_filenames.get_quotedrpath(cls._incs_dir)
        if cls._ref_type:
            cls._ref_path = map_filenames.get_quotedrpath(cls._ref_path)
            cls._ref_inc = map_filenames.get_quotedrpath(cls._ref_inc)
        return True

    @classmethod
    def _setup_logging(cls):
        """
        Setup logging, opening the relevant files locally
        """
        if cls._must_be_writable:
            if log.Log.file_verbosity > 0:
                cls._open_logfile()
            # FIXME the logic shouldn't be dependent on the action's name
            if cls._values["action"] == "backup":
                log.ErrorLog.open(
                    data_dir=cls._data_dir,
                    time_string=Time.getcurtimestr(),
                    compress=cls._values["compression"],
                )

    # @API(RepoShadow.exit, 300)
    @classmethod
    def exit(cls):
        cls._unlock()
        log.ErrorLog.close()
        if cls._logging_to_file:
            log.Log.close_logfile()

    # @API(RepoShadow.get_sigs, 201)
    @classmethod
    def get_sigs(cls, source_iter, previous_time, is_local):
        """
        Setup cache and return a signatures iterator
        """
        cls._set_rorp_cache(cls._base_dir, source_iter, previous_time)
        return cls._sigs_iterator(cls._base_dir, is_local)

    # @API(RepoShadow.apply, 201)
    @classmethod
    def apply(cls, source_diffiter, previous_time=None):
        """
        Patch the current repo with rorpiter of diffs and optionally write
        increments.

        This function is used for first and follow-up backups
        within a repository.
        """
        if previous_time:
            ITR = rorpiter.IterTreeReducer(
                _RepoIncrementITRB,
                [cls._base_dir, cls._incs_dir, cls.CCPP, previous_time],
            )
            log_msg = "Processing changed file {cf}"
        else:
            ITR = rorpiter.IterTreeReducer(_RepoPatchITRB, [cls._base_dir, cls.CCPP])
            log_msg = "Processing file {cf}"
        for diff in rorpiter.FillInIter(source_diffiter, cls._base_dir):
            log.Log(log_msg.format(cf=diff), log.INFO)
            ITR(diff.index, diff)
        ITR.finish_processing()
        cls.CCPP.close()
        cls._base_dir.setdata()

    @classmethod
    def _is_existing(cls):
        # check first that the directory itself exists
        if not super()._is_existing():
            return False

        if not cls._data_dir.isdir():
            log.Log(
                "Source directory '{sd}' doesn't have a sub-directory "
                "'rdiff-backup-data'".format(sd=cls._base_dir),
                log.ERROR,
            )
            return False
        elif not cls._incs_dir.isdir():
            log.Log(
                "Data directory '{dd}' doesn't have an 'increments' "
                "sub-directory".format(dd=cls._data_dir),
                log.WARNING,
            )  # used to be normal  # compat200repo
            # return False # compat200repo
        return True

    @classmethod
    def _is_writable(cls):
        # check first that the directory itself is writable
        # (or doesn't yet exist)
        if not super()._is_writable():
            return False
        # if the target is a non-empty existing directory
        # without rdiff-backup-data sub-directory
        if (
            cls._base_dir.lstat()
            and cls._base_dir.isdir()
            and cls._base_dir.listdir()
            and not cls._data_dir.lstat()
        ):
            if cls._values["force"]:
                log.Log(
                    "Target path '{tp}' does not look like a rdiff-backup "
                    "repository but will be force overwritten".format(tp=cls._base_dir),
                    log.WARNING,
                )
            else:
                log.Log(
                    "Target path '{tp}' does not look like a rdiff-backup "
                    "repository, call with '--force' to overwrite".format(
                        tp=cls._base_dir
                    ),
                    log.ERROR,
                )
                return False
        return True

    @classmethod
    def _create(cls):
        # create the underlying location/directory
        if not super()._create():
            return False

        if cls._is_failed_initial_backup():
            # poor man's locking mechanism to protect starting backup
            # independently from the API version
            cls._lockfile.setdata()
            if cls._lockfile.lstat():
                if cls._values["force"]:
                    log.Log(
                        "An initial backup in a strange state with "
                        "lockfile {lf}. Enforcing continuation, "
                        "hopefully you know what you're doing".format(lf=cls._lockfile),
                        log.WARNING,
                    )
                else:
                    log.Log(
                        "An initial backup in a strange state with "
                        "lockfile {lf}. Either it's just an initial backup "
                        "running, wait a bit and try again later, or "
                        "something is really wrong. --force will remove "
                        "the complete repo, at your own risk".format(lf=cls._lockfile),
                        log.ERROR,
                    )
                    return False
            log.Log(
                "Found interrupted initial backup in data directory {dd}. "
                "Removing...".format(dd=cls._data_dir),
                log.NOTE,
            )
            cls._clean_failed_initial_backup()

        # define a few essential subdirectories
        if not cls._data_dir.lstat():
            try:
                cls._data_dir.mkdir()
            except OSError as exc:
                log.Log(
                    "Could not create 'rdiff-backup-data' sub-directory "
                    "in base directory '{bd}' due to exception '{ex}'. "
                    "Please fix the access rights and retry.".format(
                        bd=cls._base_dir, ex=exc
                    ),
                    log.ERROR,
                )
                return False
        if not cls._incs_dir.lstat():
            try:
                cls._incs_dir.mkdir()
            except OSError as exc:
                log.Log(
                    "Could not create 'increments' sub-directory "
                    "in data directory '{dd}' due to exception '{ex}'. "
                    "Please fix the access rights and retry.".format(
                        dd=cls._data_dir, ex=exc
                    ),
                    log.ERROR,
                )
                return False

        return True

    @classmethod
    def _is_failed_initial_backup(cls):
        """
        Returns True if it looks like the rdiff-backup-data directory contains
        a failed initial backup, else False.
        """
        if cls._data_dir.lstat():
            rbdir_files = cls._data_dir.listdir()
            mirror_markers = [x for x in rbdir_files if x.startswith(b"current_mirror")]
            error_logs = [x for x in rbdir_files if x.startswith(b"error_log")]
            metadata_mirrors = [
                x for x in rbdir_files if x.startswith(b"mirror_metadata")
            ]
            # If we have no current_mirror marker, and one or less error logs
            # and metadata files, we most likely have a failed backup.
            return (
                not mirror_markers
                and len(error_logs) <= 1
                and len(metadata_mirrors) <= 1
            )
        return False

    @classmethod
    def _clean_failed_initial_backup(cls):
        """
        Clear the given rdiff-backup-data if possible, it's faster than
        trying to do a regression, which would probably anyway fail.
        """
        cls._data_dir.delete()  # setdata is implicit
        cls._incs_dir.setdata()

    @classmethod
    def _get_repository_dirs(cls, orig_path):
        """
        Determine the base_dir of a repo based on a given path.

        The rpath can be either the repository itself, a sub-directory
        (in the mirror) or a dated increment file.
        Return a tuple made of (the identified base directory, a path index,
        the recovery type). The path index is the split relative path of the
        sub-directory to restore (or of the path corresponding to the
        increment). The type is either 'base', 'subpath', 'inc' or None if the
        given rpath couldn't be properly analyzed.

        Note that the current path can be relative but must still
        contain the name of the repository (it can't be just within it).
        """
        # get the path as a list of directories/file
        path_list = orig_path.get_path_as_list()
        if orig_path.isincfile():
            if b"rdiff-backup-data" not in path_list:
                log.Log(
                    "Path '{pa}' looks like an increment but doesn't "
                    "have 'rdiff-backup-data' in its path".format(pa=orig_path),
                    log.ERROR,
                )
                return (orig_path, (), None)
            else:
                data_idx = path_list.index(b"rdiff-backup-data")
                if b"increments" in path_list:
                    inc_idx = path_list.index(b"increments")
                    # base_index is the path within the increments directory,
                    # replacing the name of the increment with the name of the
                    # file it represents
                    base_index = path_list[inc_idx + 1 : -1]
                    base_index.append(orig_path.inc_basestr.split(b"/")[-1])
                elif path_list[-1].startswith(b"increments."):
                    inc_idx = len(path_list) - 1
                    base_index = []
                else:
                    inc_idx = -1
                if inc_idx != data_idx + 1:
                    log.Log(
                        "Path '{pa}' looks like an increment but "
                        "doesn't have 'rdiff-backup-data/increments' "
                        "in its path.".format(pa=orig_path),
                        log.ERROR,
                    )
                    return (orig_path, (), None)
                # base_dir is the directory above the data directory
                base_dir = rpath.RPath(orig_path.conn, b"/".join(path_list[:data_idx]))
                return (base_dir, tuple(base_index), "inc")
        else:
            # rpath is either the base directory itself or a sub-dir of it
            if (
                orig_path.lstat()
                and orig_path.isdir()
                and b"rdiff-backup-data" in orig_path.listdir()
            ):
                # it's a base directory, simple case...
                return (orig_path, (), "base")
            parent_rp = orig_path
            for element in range(1, len(path_list)):
                parent_rp = parent_rp.get_parent_rp()
                if (
                    parent_rp.lstat()
                    and parent_rp.isdir()
                    and b"rdiff-backup-data" in parent_rp.listdir()
                ):
                    return (parent_rp, tuple(path_list[-element:]), "subpath")
            log.Log(
                "Path '{pa}' couldn't be identified as being within "
                "an existing backup repository".format(pa=orig_path),
                log.ERROR,
            )
            return (orig_path, (), None)

    @classmethod
    def _get_dest_select(cls, rpath, previous_time):
        """
        Return destination select rorpath iterator

        If metadata file doesn't exist, select all files on
        destination except rdiff-backup-data directory.
        """

        def get_iter_from_fs():
            """Get the combined iterator from the filesystem"""
            sel = selection.Select(rpath)
            sel.parse_rbdir_exclude()
            return sel.get_select_iter()

        meta_manager = meta_mgr.get_meta_manager(cls._data_dir, True)
        if previous_time:  # it's an increment, not the first mirror
            rorp_iter = meta_manager.get_metas_at_time(previous_time)
            if rorp_iter:
                return rorp_iter
        return get_iter_from_fs()

    @classmethod
    def _set_rorp_cache(cls, baserp, source_iter, previous_time):
        """
        Initialize cls.CCPP, the destination rorp cache

        previous_time should be true (>0) if we are mirror+incrementing,
        representing the epoch in seconds of the previous backup,
        false (==0) if we are just mirroring.
        """
        dest_iter = cls._get_dest_select(baserp, previous_time)
        collated = rorpiter.Collate2Iters(source_iter, dest_iter)
        cls.CCPP = _CacheCollatedPostProcess(
            collated,
            consts.PIPELINE_MAX_LENGTH * 4,
            baserp,
            cls._data_dir,
            cls._values.get("file_statistics"),
        )
        # pipeline len adds some leeway over just*3 (to and from and back)

    @classmethod
    def _sigs_iterator(cls, baserp, is_local):
        """
        Yield signatures of any changed destination files
        """
        flush_threshold = consts.PIPELINE_MAX_LENGTH - 2
        num_rorps_seen = 0
        for src_rorp, dest_rorp in cls.CCPP:
            # If we are backing up across a pipe, we must flush the pipeline
            # every so often so it doesn't get congested on destination end.
            if not is_local:
                num_rorps_seen += 1
                if num_rorps_seen > flush_threshold:
                    num_rorps_seen = 0
                    yield iterfile.MiscIterFlushRepeat
            if not (
                src_rorp
                and dest_rorp
                and src_rorp == dest_rorp
                and (
                    not Globals.preserve_hardlinks
                    or map_hardlinks.rorp_eq(src_rorp, dest_rorp)
                )
            ):
                index = src_rorp and src_rorp.index or dest_rorp.index
                sig = cls._get_one_sig(baserp, index, src_rorp, dest_rorp)
                if sig:
                    cls.CCPP.flag_changed(index)
                    yield sig

    @classmethod
    def _get_one_sig(cls, baserp, index, src_rorp, dest_rorp):
        """Return a signature given source and destination rorps"""
        if (
            Globals.preserve_hardlinks
            and src_rorp
            and map_hardlinks.is_linked(src_rorp)
        ):
            dest_sig = rpath.RORPath(index)
            dest_sig.flaglinked(map_hardlinks.get_link_index(src_rorp))
        elif dest_rorp:
            dest_sig = dest_rorp.getRORPath()
            if dest_rorp.isreg():
                dest_rp = map_longnames.get_mirror_rp(baserp, dest_rorp)
                sig_fp = cls._get_one_sig_fp(dest_rp)
                if sig_fp is None:
                    return None
                dest_sig.setfile(sig_fp)
        else:
            dest_sig = rpath.RORPath(index)
        return dest_sig

    @classmethod
    def _get_one_sig_fp(cls, dest_rp):
        """Return a signature fp of given index, corresponding to reg file"""
        if not dest_rp.isreg():
            log.ErrorLog.write_if_open(
                "UpdateError",
                dest_rp,
                "File changed from regular file before signature",
            )
            return None
        if Globals.process_uid != 0 and not dest_rp.readable() and dest_rp.isowner():
            # This branch can happen with root source and non-root
            # destination.  Permissions are changed permanently, which
            # should propagate to the diffs
            dest_rp.chmod(0o400 | dest_rp.getperms())
        try:
            return Rdiff.get_signature(dest_rp)
        except OSError as e:
            if e.errno == errno.EPERM or e.errno == errno.EACCES:
                try:
                    # Try chmod'ing anyway -- This can work on NFS and AFS
                    # depending on the setup. We keep the if() statement
                    # above for performance reasons.
                    dest_rp.chmod(0o400 | dest_rp.getperms())
                    return Rdiff.get_signature(dest_rp)
                except OSError as exc:
                    log.Log.FatalError(
                        "Could not open file {fi} for reading due to "
                        "exception '{ex}'. Check permissions on file.".format(
                            ex=exc, fi=dest_rp
                        )
                    )
            else:
                raise

    # @API(RepoShadow.touch_current_mirror, 201)
    @classmethod
    def touch_current_mirror(cls, current_time):
        """
        Make a file like current_mirror.<datetime>.data to record time

        When doing an incremental backup, this should happen before any
        other writes, and the file should be removed after all writes.
        That way we can tell whether the previous session aborted if there
        are two current_mirror files.

        When doing the initial full backup, the file can be created after
        everything else is in place.
        """
        current_time_bytes = Time.timetobytes(current_time)
        mirrorrp = cls._data_dir.append(
            b".".join((b"current_mirror", current_time_bytes, b"data"))
        )
        log.Log("Writing mirror marker {mm}".format(mm=mirrorrp), log.INFO)
        try:
            pid = os.getpid()
        except BaseException:
            pid = "NA"
        mirrorrp.write_string("PID {pp}\n".format(pp=pid))
        mirrorrp.fsync_with_dir()

    # @API(RepoShadow.remove_current_mirror, 201)
    @classmethod
    def remove_current_mirror(cls):
        """
        Remove the older of the current_mirror files.

        Use at end of session
        """
        curmir_incs = cls._data_dir.append(b"current_mirror").get_incfiles_list()
        assert (
            len(curmir_incs) == 2
        ), "There must be two current mirrors not '{ilen}'.".format(
            ilen=len(curmir_incs)
        )
        if curmir_incs[0].getinctime() < curmir_incs[1].getinctime():
            older_inc = curmir_incs[0]
        else:
            older_inc = curmir_incs[1]
        if Globals.do_fsync:
            # Make sure everything is written before current_mirror is removed
            C.sync()
        older_inc.delete()

    # @API(RepoShadow.close_statistics, 201)
    @classmethod
    def close_statistics(cls, end_time):
        """
        Close out the tracking of the backup statistics.

        Moved to run at this point so that only the clock of the system on which
        rdiff-backup is run is used (set by passing in time.time() from that
        system). Use at end of session.
        """
        if cls._values.get("print_statistics"):
            statistics.print_active_stats(end_time)
        if cls._values.get("file_statistics"):
            statistics.FileStats.close()
        statistics.write_active_statfileobj(cls._data_dir, end_time)

    # ### COPIED FROM RESTORE ####

    # @API(RepoShadow.init_loop, 201)
    @classmethod
    def init_loop(cls, restore_to_time):
        """
        Initialize repository for looping through the increments
        """
        cls._initialize_restore(restore_to_time)
        cls._initialize_rf_cache(cls._ref_path, cls._ref_inc)

    # @API(RepoShadow.finish_loop, 201)
    @classmethod
    def finish_loop(cls):
        """
        Run anything remaining on _CachedRF object
        """
        cls.rf_cache.close()

    # @API(RepoShadow.get_mirror_time, 201)
    @classmethod
    def get_mirror_time(cls, must_exist=False, refresh=False):
        """
        Return time (in seconds) of latest mirror

        Cache the mirror time for performance reasons

        must_exist defines if there must already be (at least) one mirror or
        not. If True, the function will fail if there is no mirror and return
        the last time if there is more than one (the regress case).
        If False, the default, the function will return 0 if there is no
        mirror, and -1 if there is more than one.
        """
        # this function is only used internally (for now) but it might change
        # hence it looks like an external function potentially called remotely
        if cls._mirror_time is None or refresh:
            cur_mirror_incs = cls._data_dir.append(
                b"current_mirror"
            ).get_incfiles_list()
            if not cur_mirror_incs:
                if must_exist:
                    log.Log.FatalError("Could not get time of current mirror")
                else:
                    cls._mirror_time = 0
            elif len(cur_mirror_incs) > 1:
                log.Log(
                    "Two different times for current mirror were found, "
                    "it seems that the last backup failed, "
                    "you most probably want to regress the repository",
                    log.WARNING,
                )
                if must_exist:
                    cls._mirror_time = cur_mirror_incs[0].getinctime()
                else:
                    cls._mirror_time = -1
            else:
                cls._mirror_time = cur_mirror_incs[0].getinctime()
        return cls._mirror_time

    # @API(RepoShadow.get_parsed_time, 300)
    @classmethod
    def get_parsed_time(cls, timestr):
        """
        Parse time string, potentially using the reference increment as anchor

        Returns None if the time string couldn't be parsed, else the time in
        seconds.
        The reference increment is used when the time string consists in a
        number of past backups.
        """
        try:
            sessions = cls.get_increment_times(cls._ref_inc)
            return Time.genstrtotime(timestr, session_times=sessions)
        except Time.TimeException as exc:
            log.Log(
                "Time string '{ts}' couldn't be parsed "
                "due to '{ex}'".format(ts=timestr, ex=exc),
                log.ERROR,
            )
            return None

    # @API(RepoShadow.get_increment_times, 201)
    @classmethod
    def get_increment_times(cls, rp=None):
        """
        Return list of times of backups, including current mirror

        Take the total list of times from the increments.<time>.dir
        file and the mirror_metadata file.  Sorted ascending.
        """
        # use set to remove duplicate times between increments and metadata
        times_set = {cls.get_mirror_time(must_exist=True)}
        if not rp or not rp.index:
            rp = cls._data_dir.append(b"increments")
        for inc in rp.get_incfiles_list():
            times_set.add(inc.getinctime())
        mirror_meta_rp = cls._data_dir.append(b"mirror_metadata")
        for inc in mirror_meta_rp.get_incfiles_list():
            times_set.add(inc.getinctime())
        return_list = sorted(times_set)
        return return_list

    @classmethod
    def _initialize_restore(cls, restore_to_time):
        """
        Set class variable _restore_time on mirror conn
        """
        cls._set_restore_time(restore_to_time)
        # it's a bit ugly to set the values to another class, but less than
        # the other way around as it used to be
        _RestoreFile.initialize(cls._restore_time, cls.get_mirror_time(must_exist=True))

    @classmethod
    def _initialize_rf_cache(cls, mirror_base, inc_base):
        """Set cls.rf_cache to _CachedRF object"""
        inc_list = inc_base.get_incfiles_list()
        rf = _RestoreFile(mirror_base, inc_base, inc_list)
        cls.mirror_base, cls.inc_base = mirror_base, inc_base
        cls.root_rf = rf
        cls.rf_cache = _CachedRF(rf)

    @classmethod
    def _get_mirror_rorp_iter(cls, rest_time=None, require_metadata=None):
        """
        Return iter of mirror rps at given restore time

        Usually we can use the metadata file, but if this is
        unavailable, we may have to build it from scratch.

        If the cls._select object is set, use it to filter out the
        unwanted files from the metadata_iter.
        """
        if rest_time is None:
            rest_time = cls._restore_time

        meta_manager = meta_mgr.get_meta_manager(cls._data_dir, True)
        rorp_iter = meta_manager.get_metas_at_time(rest_time, cls.mirror_base.index)
        if not rorp_iter:
            if require_metadata:
                log.Log.FatalError("Mirror metadata not found")
            log.Log("Mirror metadata not found, reading from directory", log.WARNING)
            rorp_iter = cls._get_rorp_iter_from_rf(cls.root_rf)

        if cls._select:
            rorp_iter = selection.FilterIter(cls._select, rorp_iter)
        return rorp_iter

    # @API(RepoShadow.set_select, 201)
    @classmethod
    def set_select(cls, target_rp, select_opts=None):
        """
        Initialize the mirror selection object based on the target directory

        This will probably be used only for restoring
        """
        if select_opts is None:
            select_opts = cls._values.get("selections")
            if not select_opts:
                return  # nothing to do...
        cls._select = selection.Select(target_rp)
        cls._select.parse_selection_args(select_opts)

    @classmethod
    def _subtract_indices(cls, index, rorp_iter):
        """
        Subtract index from index of each rorp in rorp_iter

        _subtract_indices is necessary because we
        may not be restoring from the root index.
        """
        if index == ():
            return rorp_iter

        def get_iter():
            for rorp in rorp_iter:
                assert (
                    rorp.index[: len(index)] == index
                ), "Path '{ridx}' must be a sub-path of '{idx}'.".format(
                    ridx=rorp.index, idx=index
                )
                rorp.index = rorp.index[len(index) :]
                yield rorp

        return get_iter()

    # @API(RepoShadow.get_diffs, 201)
    @classmethod
    def get_diffs(cls, target_iter):
        """
        Given rorp iter of target files, return diffs

        Here the target_iter doesn't contain any actual data, just
        attribute listings.  Thus any diffs we generate will be
        snapshots.
        """
        mir_iter = cls._subtract_indices(
            cls.mirror_base.index, cls._get_mirror_rorp_iter()
        )
        collated = rorpiter.Collate2Iters(mir_iter, target_iter)
        return cls._get_diffs_from_collated(collated)

    @classmethod
    def _set_restore_time(cls, restore_to_time):
        """
        Set restore to older time, if restore_to_time is in between two inc
        times

        There is a slightly tricky reason for doing this: The rest of the
        code just ignores increments that are older than restore_to_time.
        But sometimes we want to consider the very next increment older
        than rest time, because rest_time will be between two increments,
        and what was actually on the mirror side will correspond to the
        older one.

        So if restore_to_time is inbetween two increments, return the
        older one.
        """
        inctimes = cls.get_increment_times()
        older_times = [otime for otime in inctimes if otime <= restore_to_time]
        if older_times:
            cls._restore_time = max(older_times)
        else:  # restore time older than oldest increment, just return that
            cls._restore_time = min(inctimes)
        return cls._restore_time

    @classmethod
    def _get_rorp_iter_from_rf(cls, rf):
        """Recursively yield mirror rorps from rf"""
        rorp = rf.get_attribs()
        yield rorp
        if rorp.isdir():
            for sub_rf in rf.yield_sub_rfs():
                for attribs in cls._get_rorp_iter_from_rf(sub_rf):
                    yield attribs

    @classmethod
    def _get_diffs_from_collated(cls, collated):
        """Get diff iterator from collated"""
        for mir_rorp, target_rorp in collated:
            if Globals.preserve_hardlinks and mir_rorp:
                map_hardlinks.add_rorp(mir_rorp, target_rorp)
            if (
                not target_rorp
                or not mir_rorp
                or not mir_rorp == target_rorp
                or (
                    Globals.preserve_hardlinks
                    and not map_hardlinks.rorp_eq(mir_rorp, target_rorp)
                )
            ):
                diff = cls._get_diff(mir_rorp, target_rorp)
            else:
                diff = None
            if Globals.preserve_hardlinks and mir_rorp:
                map_hardlinks.del_rorp(mir_rorp)
            if diff:
                yield diff

    @classmethod
    def _get_diff(cls, mir_rorp, target_rorp):
        """Get a diff for mir_rorp at time"""
        if not mir_rorp:
            mir_rorp = rpath.RORPath(target_rorp.index)
        elif Globals.preserve_hardlinks and map_hardlinks.is_linked(mir_rorp):
            mir_rorp.flaglinked(map_hardlinks.get_link_index(mir_rorp))
        elif mir_rorp.isreg():
            expanded_index = cls.mirror_base.index + mir_rorp.index
            file_fp = cls.rf_cache.get_fp(expanded_index, mir_rorp)
            mir_rorp.setfile(hash.FileWrapper(file_fp))
        mir_rorp.set_attached_filetype("snapshot")
        return mir_rorp

    # ### COPIED FROM RESTORE (LIST) ####

    # @API(RepoShadow.list_files_changed_since, 201)
    @classmethod
    def list_files_changed_since(cls, restore_to_time):
        """
        List the changed files under the repository since rest time

        Notice the output is an iterator of RORPs.  We do this because we
        want to give the remote connection the data in buffered
        increments, and this is done automatically for rorp iterators.
        Encode the lines in the first element of the rorp's index.
        """
        assert cls._base_dir.conn is Globals.local_connection, "Run locally only"
        cls.init_loop(restore_to_time)

        old_iter = cls._get_mirror_rorp_iter(cls._restore_time, True)
        cur_iter = cls._get_mirror_rorp_iter(cls.get_mirror_time(must_exist=True), True)
        collated = rorpiter.Collate2Iters(old_iter, cur_iter)
        for old_rorp, cur_rorp in collated:
            if not old_rorp:
                change = "new"
            elif not cur_rorp:
                change = "deleted"
            elif old_rorp == cur_rorp:
                continue
            else:
                change = "changed"
            path_desc = old_rorp and str(old_rorp) or str(cur_rorp)
            yield rpath.RORPath(("%-7s %s" % (change, path_desc),))
        cls.finish_loop()

    # @API(RepoShadow.list_files_at_time, 201)
    @classmethod
    def list_files_at_time(cls, reftime):
        """
        List the files in archive at the given time

        Output is a RORP Iterator with info in index.
        See list_files_changed_since for details.
        """
        assert cls._base_dir.conn is Globals.local_connection, "Run locally only"
        cls.init_loop(reftime)
        old_iter = cls._get_mirror_rorp_iter()
        for rorp in old_iter:
            yield rorp
        cls.finish_loop()

    # @API(RepoShadow.get_increments, 300)
    @classmethod
    def get_increments(cls):
        """
        Return a list of increments (without size) with their time, type
        and basename.

        The list is sorted by increasing time stamp, meaning that the mirror
        is last in the list
        """
        incs_list = cls._ref_inc.get_incfiles_list()
        incs = [
            {
                "time": inc.getinctime(),
                "type": cls._get_inc_type(inc),
                "base": inc.dirsplit()[1].decode(errors="replace"),
            }
            for inc in incs_list
        ]

        # append the mirror itself
        mirror_time = cls.get_mirror_time(must_exist=True)
        incs.append(
            {
                "time": mirror_time,
                "type": cls._get_file_type(cls._ref_path),
                "base": cls._ref_path.dirsplit()[1].decode(errors="replace"),
            }
        )

        return sorted(incs, key=lambda x: x["time"])

    # @API(RepoShadow.get_increments_sizes, 300)
    @classmethod
    def get_increments_sizes(cls):
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
            mirror_select = selection.Select(cls._ref_path)
            if not cls._ref_index:  # must exclude rdiff-backup-directory
                mirror_select.parse_rbdir_exclude()
            return mirror_select.get_select_iter()

        def get_inc_select():
            """Return iterator of increment rpaths"""
            for base_inc in cls._ref_inc.get_incfiles_list():
                yield base_inc
            if cls._ref_inc.isdir():
                inc_select = selection.Select(cls._ref_inc).get_select_iter()
                for inc in inc_select:
                    yield inc

        def get_summary_triples(mirror_total, time_dict):
            """Return list of triples (time, size, cumulative size)"""
            triples = []

            cur_mir_base = cls._data_dir.append(b"current_mirror")
            mirror_time = (cur_mir_base.get_incfiles_list())[0].getinctime()
            triples.append(
                {"time": mirror_time, "size": mirror_total, "total_size": mirror_total}
            )

            inc_times = list(time_dict.keys())
            inc_times.sort()
            inc_times.reverse()
            cumulative_size = mirror_total
            for inc_time in inc_times:
                size = time_dict[inc_time]
                cumulative_size += size
                triples.append(
                    {"time": inc_time, "size": size, "total_size": cumulative_size}
                )
            return triples

        mirror_total = get_total(get_mirror_select())
        time_dict = get_time_dict(get_inc_select())
        triples = get_summary_triples(mirror_total, time_dict)

        return sorted(triples, key=lambda x: x["time"])

    # ### COPIED FROM MANAGE ####

    # @API(RepoShadow.remove_increments, 300)
    @classmethod
    def remove_increments_older_than(cls, time_string=None, show_sizes=None):
        """
        Remove increments older than the given time
        """
        assert (
            cls._data_dir.conn is Globals.local_connection
        ), "Function should be called only locally " "and not over '{co}'.".format(
            co=cls._data_dir.conn
        )

        def yield_files(rp):
            if rp.isdir():
                for filename in rp.listdir():
                    for sub_rp in yield_files(rp.append(filename)):
                        yield sub_rp
            yield rp

        if time_string is None:
            time_string = cls._values.get("older_than")
        if show_sizes is None:
            show_sizes = cls._values.get("size")
        removal_time = cls._get_removal_time(time_string, show_sizes)

        if removal_time < 0:  # no increment is old enough
            log.Log(
                "No increment is older than '{ot}'".format(ot=time_string),
                log.WARNING,
            )
            return consts.RET_CODE_WARN

        for rp in yield_files(cls._data_dir):
            if (rp.isincfile() and rp.getinctime() < removal_time) or (
                rp.isdir() and not rp.listdir()
            ):
                log.Log("Deleting increment file {fi}".format(fi=rp), log.INFO)
                rp.delete()
        return consts.RET_CODE_OK

    @classmethod
    def _get_removal_time(cls, time_string, show_sizes):
        """
        Check remove older than time_string, return time in seconds

        Return None if the time string can't be interpreted as such, or
        if more than one increment would be removed, without the force option;
        or -1 if no increment would be removed.
        """
        action_time = cls.get_parsed_time(time_string)
        if action_time is None:
            return None

        if show_sizes:
            triples = cls.get_increments_sizes()[:-1]
            times_in_secs = [triple["time"] for triple in triples]
        else:
            times_in_secs = [
                inc.getinctime() for inc in cls._incs_dir.get_incfiles_list()
            ]
        times_in_secs = [t for t in times_in_secs if t < action_time]
        if not times_in_secs:
            log.Log(
                "No increments older than {at} found, exiting.".format(
                    at=Time.timetopretty(action_time)
                ),
                log.NOTE,
            )
            return -1

        times_in_secs.sort()
        if show_sizes:
            sizes = [
                triple["size"] for triple in triples if triple["time"] in times_in_secs
            ]
            stat_obj = statistics.StatsObj()  # used for byte summary string

            def format_time_and_size(time, size):
                return "{: <24} {: >17}".format(
                    Time.timetopretty(time), stat_obj.get_byte_summary_string(size)
                )

            pretty_times_map = map(format_time_and_size, times_in_secs, sizes)
            pretty_times = "\n".join(pretty_times_map)
        else:
            pretty_times = "\n".join(map(Time.timetopretty, times_in_secs))
        if len(times_in_secs) > 1:
            if not cls._values["force"]:
                log.Log(
                    "Found {ri} relevant increments, dates/times:\n{dt}\n"
                    "If you want to delete multiple increments in this way, "
                    "use the --force option.".format(
                        ri=len(times_in_secs), dt=pretty_times
                    ),
                    log.ERROR,
                )
                return None
            else:
                log.Log(
                    "Deleting increments at dates/times:\n{dt}".format(dt=pretty_times),
                    log.NOTE,
                )
        else:
            log.Log(
                "Deleting increment at date/time: {dt}".format(dt=pretty_times),
                log.NOTE,
            )
        # make sure we don't delete current increment
        return times_in_secs[-1] + 1

    # ### COPIED FROM COMPARE ####

    # @API(RepoShadow.init_and_get_loop, 201)
    @classmethod
    def init_and_get_loop(cls, compare_time, src_iter=None):
        """
        Return rorp iter at given compare time

        Attach necessary file details if src_iter is given

        cls.finish_loop must be called to finish the loop once initialized
        """
        cls.init_loop(compare_time)
        repo_iter = cls._subtract_indices(
            cls.mirror_base.index, cls._get_mirror_rorp_iter()
        )
        if src_iter is None:
            return repo_iter
        else:
            return cls._attach_files(compare_time, src_iter, repo_iter)

    @classmethod
    def _attach_files(cls, compare_time, src_iter, repo_iter):
        """
        Attach data to all the files that need checking

        Return an iterator of repo rorps that includes all the files
        that may have changed, and has the fileobj set on all rorps
        that need it.
        """
        base_index = cls.mirror_base.index
        for src_rorp, mir_rorp in rorpiter.Collate2Iters(src_iter, repo_iter):
            index = src_rorp and src_rorp.index or mir_rorp.index
            if src_rorp and mir_rorp:
                if not src_rorp.isreg() and src_rorp == mir_rorp:
                    cls._log_success(src_rorp, mir_rorp)
                    continue  # They must be equal, nothing else to check
                if (
                    src_rorp.isreg()
                    and mir_rorp.isreg()
                    and src_rorp.getsize() == mir_rorp.getsize()
                ):
                    fp = cls.rf_cache.get_fp(base_index + index, mir_rorp)
                    mir_rorp.setfile(fp)
                    mir_rorp.set_attached_filetype("snapshot")

            if mir_rorp:
                yield mir_rorp
            else:
                yield rpath.RORPath(index)  # indicate deleted mir_rorp

    # @API(RepoShadow.verify, 201)
    @classmethod
    def verify(cls, verify_time):
        """
        Compute SHA1 sums of repository files and check against metadata
        """
        assert (
            cls._ref_path.conn is Globals.local_connection
        ), "Only verify mirror locally, not remotely over '{conn}'.".format(
            conn=cls._ref_path.conn
        )
        repo_iter = cls.init_and_get_loop(verify_time)
        base_index = cls.mirror_base.index

        bad_files = 0
        no_hash = 0
        ret_code = consts.RET_CODE_OK
        for repo_rorp in repo_iter:
            if not repo_rorp.isreg():
                continue
            verify_sha1 = map_hardlinks.get_hash(repo_rorp)
            if not verify_sha1:
                log.Log(
                    "Cannot find SHA1 digest for file {fi}, perhaps "
                    "because this feature was added in v1.1.1".format(fi=repo_rorp),
                    log.WARNING,
                )
                no_hash += 1
                ret_code |= consts.RET_CODE_FILE_WARN
                continue
            fp = cls.rf_cache.get_fp(base_index + repo_rorp.index, repo_rorp)
            computed_hash = hash.compute_sha1_fp(fp)
            if computed_hash == verify_sha1:
                log.Log(
                    "Verified SHA1 digest of file {fi}".format(fi=repo_rorp), log.INFO
                )
            else:
                bad_files += 1
                log.Log(
                    "Computed SHA1 digest of file {fi} '{cd}' "
                    "doesn't match recorded digest of '{rd}'. "
                    "Your backup repository may be corrupted!".format(
                        fi=repo_rorp, cd=computed_hash, rd=verify_sha1
                    ),
                    log.ERROR,
                )
                ret_code |= consts.RET_CODE_FILE_ERR
        cls.finish_loop()
        if bad_files:
            log.Log(
                "Verification found {cf} potentially corrupted files".format(
                    cf=bad_files
                ),
                log.ERROR,
            )
            if no_hash:
                log.Log(
                    "Verification also found {fi} files without "
                    "hash".format(fi=no_hash),
                    log.NOTE,
                )
        elif no_hash:
            log.Log(
                "Verification found {fi} files without hash, all others "
                "could be verified successfully".format(fi=no_hash),
                log.NOTE,
            )
        else:
            log.Log("All files verified successfully", log.NOTE)
        return ret_code

    @classmethod
    def _open_logfile(cls):
        """
        Open logfile with base name in the repository
        """
        try:  # the target repository must be writable
            logfile = cls._data_dir.append(cls._values["action"] + ".log")
            log.Log.open_logfile(logfile)
        except (log.LoggerError, Security.Violation) as exc:
            log.Log(
                "Unable to open logfile '{lf}' due to '{ex}'".format(
                    lf=logfile, ex=exc
                ),
                log.ERROR,
            )
            return consts.RET_CODE_ERR
        else:
            cls._logging_to_file = True
            return consts.RET_CODE_OK

    @classmethod
    def _log_success(cls, src_rorp, mir_rorp=None):
        """
        Log that src_rorp and mir_rorp compare successfully
        """
        # FIXME eliminate duplicate function with _dir_shadow
        path = src_rorp and str(src_rorp) or str(mir_rorp)
        log.Log("Successfully compared path {pa}".format(pa=path), log.INFO)

    # ### COPIED FROM REGRESS ####

    # @API(RepoShadow.needs_regress, 201)
    @classmethod
    def needs_regress(cls):
        """
        Checks if the repository contains a previously failed backup and needs
        to be regressed

        Note that this function won't catch an initial failed backup, this
        needs to be done during the repository creation phase.

        Return None if the repository can't be found or is new,
        True if it needs regressing, False otherwise.
        """
        # detect an initial repository which doesn't need a regression
        if not (
            cls._base_dir.isdir()
            and cls._data_dir.isdir()
            and cls._incs_dir.isdir()
            and cls._incs_dir.listdir()
        ):
            return None
        curmirroot = cls._data_dir.append(b"current_mirror")
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

""".format(
                    dd=cls._data_dir
                )
            )
        elif len(curmir_incs) == 1:
            return False
        else:
            if not cls._values["force"]:
                try:
                    cls._check_pids(curmir_incs)
                except OSError as exc:
                    log.Log.FatalError(
                        "Could not check if rdiff-backup is currently"
                        "running due to exception '{ex}'".format(ex=exc)
                    )
            assert (
                len(curmir_incs) == 2
            ), "Found more than 2 current_mirror incs in '{ci}'.".format(
                ci=cls._data_dir
            )
            return True

    # @API(RepoShadow.regress, 201)
    @classmethod
    def regress(cls):
        """
        Bring mirror and inc directory back to regress_to_time

        Regress should only work one step at a time (i.e. don't "regress"
        through two separate backup sets.  This function should be run
        locally to the rdiff-backup-data directory.
        """
        assert (
            cls._base_dir.index == () and cls._incs_dir.index == ()
        ), "Mirror and increment paths must have an empty index"
        assert (
            cls._base_dir.isdir() and cls._incs_dir.isdir()
        ), "Mirror and increments paths must be directories"
        assert (
            cls._base_dir.conn is cls._incs_dir.conn is Globals.local_connection
        ), "Regress must happen locally."
        meta_manager, former_current_mirror_rp = cls._set_regress_time()
        cls._set_restore_times()
        _RegressFile.initialize(cls._restore_time, cls._mirror_time)
        cls._regress_rbdir(meta_manager)
        ITR = rorpiter.IterTreeReducer(_RepoRegressITRB, [])
        for rf in cls._iterate_meta_rfs(cls._base_dir, cls._incs_dir):
            ITR(rf.index, rf)
        ITR.finish_processing()
        if former_current_mirror_rp:
            if Globals.do_fsync:
                # Sync first, since we are marking dest dir as good now
                C.sync()
            former_current_mirror_rp.delete()
        return consts.RET_CODE_OK

    # @API(RepoShadow.force_regress, 300)
    @classmethod
    def force_regress(cls):
        """
        Try to fake a failed backup to force a regress

        Return True if the fake was succesful, else False, e.g. if the
        repository contains only the mirror and no increment.
        """
        inc_times = cls.get_increment_times()
        if len(inc_times) < 2:
            log.Log(
                "Repository with only a mirror can't be forced to regress, "
                "just remove it and start from scratch",
                log.WARNING,
            )
            return False
        mirror_time = cls.get_mirror_time()
        if inc_times[-1] != mirror_time:
            log.Log(
                "Repository's increment times are inconsistent, "
                "it's too dangerous to force a regress",
                log.WARNING,
            )
            return False
        cls.touch_current_mirror(inc_times[-2])
        return True

    @classmethod
    def _check_pids(cls, curmir_incs):
        """Check PIDs in curmir markers to make sure rdiff-backup not running"""
        pid_re = re.compile(r"^PID\s*([0-9]+)", re.I | re.M)

        def extract_pid(curmir_rp):
            """Return process ID from a current mirror marker, if any"""
            match = pid_re.search(curmir_rp.get_string())
            if not match:
                return None
            else:
                return int(match.group(1))

        def pid_running(pid):
            """Return True if we know if process with pid is currently running,
            False if it isn't running, and None if we don't know for sure."""
            if os.name == "nt":
                import win32api
                import win32con
                import pywintypes

                process = None
                try:
                    process = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, 0, pid)
                except pywintypes.error as error:
                    if error.winerror == 87:
                        # parameter incorrect, PID does not exist
                        return False
                    elif error.winerror == 5:
                        # access denied, means nevertheless PID still exists
                        return True
                    else:
                        log.Log(
                            "Unable to check if process ID {pi} "
                            "is still running".format(pi=pid),
                            log.WARNING,
                        )
                        return None  # we don't know if the process is running
                else:
                    if process:
                        win32api.CloseHandle(process)
                        return True
                    else:
                        return False
            else:
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:  # errno.ESRCH - pid doesn't exist
                    return False
                except OSError:  # any other OS error
                    log.Log(
                        "Unable to check if process ID {pi} "
                        "is still running".format(pi=pid),
                        log.WARNING,
                    )
                    return None  # we don't know if the process is still running
                else:  # the process still exists
                    return True

        for curmir_rp in curmir_incs:
            assert (
                curmir_rp.conn is Globals.local_connection
            ), "Function must be called locally not over '{conn}'.".format(
                conn=curmir_rp.conn
            )
            pid = extract_pid(curmir_rp)
            # FIXME differentiate between don't know and know and handle
            # err.errno == errno.EPERM: EPERM clearly means there's a process
            # to deny access to with OSError
            if pid is not None and pid_running(pid):
                log.Log.FatalError(
                    """It appears that a previous rdiff-backup session with process
    id {pi} is still running.  If two different rdiff-backup processes write
    the same repository simultaneously, data corruption will probably
    result.  To proceed with regress anyway, rerun rdiff-backup with the
    --force option""".format(
                        pi=pid
                    )
                )

    @classmethod
    def _set_regress_time(cls):
        """
        Set regress_time to previous successful backup

        If there are two current_mirror increments, then the last one
        corresponds to a backup session that failed.
        """
        meta_manager = meta_mgr.get_meta_manager(cls._data_dir, True)
        curmir_incs = meta_manager.sorted_prefix_inclist(b"current_mirror")
        assert (
            len(curmir_incs) == 2
        ), "Found {ilen} current_mirror flags, expected 2".format(ilen=len(curmir_incs))
        mirror_rp_to_delete = curmir_incs[0]
        cls._regress_time = curmir_incs[1].getinctime()
        cls._unsuccessful_backup_time = mirror_rp_to_delete.getinctime()
        log.Log(
            "Regressing to date/time {dt}".format(
                dt=Time.timetopretty(cls._regress_time)
            ),
            log.NOTE,
        )
        return meta_manager, mirror_rp_to_delete

    @classmethod
    def _set_restore_times(cls):
        """
        Set _restore_time and _mirror_time in the restore module

        _restore_time (restore time) corresponds to the last successful
        backup time.  _mirror_time is the unsuccessful backup time.
        """
        cls._mirror_time = cls._unsuccessful_backup_time
        cls._restore_time = cls._regress_time

    @classmethod
    def _regress_rbdir(cls, meta_manager):
        """Delete the increments in the rdiff-backup-data directory

        Returns the former current mirror rp so we can delete it later.
        All of the other rp's should be deleted before the actual regress,
        to clear up disk space the rest of the procedure may need.

        Also, in case the previous session failed while diffing the
        metadata file, either recreate the mirror_metadata snapshot, or
        delete the extra regress_time diff.

        """
        meta_diffs = []
        meta_snaps = []
        for old_rp in meta_manager.timerpmap[cls._regress_time]:
            if old_rp.getincbase_bname() == b"mirror_metadata":
                if old_rp.getinctype() == b"snapshot":
                    meta_snaps.append(old_rp)
                elif old_rp.getinctype() == b"diff":
                    meta_diffs.append(old_rp)
                else:
                    raise ValueError(
                        "Increment type for metadata mirror must be one of "
                        "'snapshot' or 'diff', not {mtype}.".format(
                            mtype=old_rp.getinctype()
                        )
                    )
        if meta_diffs and not meta_snaps:
            meta_manager.recreate_attr(cls._regress_time)

        for new_rp in meta_manager.timerpmap[cls._unsuccessful_backup_time]:
            if new_rp.getincbase_bname() != b"current_mirror":
                log.Log("Deleting old diff {od}".format(od=new_rp), log.INFO)
                new_rp.delete()

        for rp in meta_diffs:
            rp.delete()

    @classmethod
    def _iterate_meta_rfs(cls, mirror_rp, inc_rp):
        """
        Yield _RegressFile objects with extra metadata information added

        Each _RegressFile will have an extra object variable .metadata_rorp
        which will contain the metadata attributes of the mirror file at
        cls._regress_time.
        """
        raw_rfs = cls._iterate_raw_rfs(mirror_rp, inc_rp)
        collated = rorpiter.Collate2Iters(raw_rfs, cls._yield_metadata())
        for raw_rf, metadata_rorp in collated:
            raw_rf = map_longnames.update_rf(
                raw_rf, metadata_rorp, mirror_rp, _RegressFile
            )
            if not raw_rf:
                log.Log(
                    "Warning, metadata file has entry for path {pa}, "
                    "but there are no associated files.".format(pa=metadata_rorp),
                    log.WARNING,
                )
                continue
            raw_rf.set_metadata_rorp(metadata_rorp)
            # Return filename stored in metadata to handle long filename.
            if metadata_rorp:
                raw_rf.index = metadata_rorp.index
            yield raw_rf

    @classmethod
    def _iterate_raw_rfs(cls, mirror_rp, inc_rp):
        """Iterate all _RegressFile objects in mirror/inc directory

        Also changes permissions of unreadable files.  We don't have to
        change them back later because regress will do that for us.

        """
        root_rf = _RegressFile(mirror_rp, inc_rp, inc_rp.get_incfiles_list())

        def helper(rf):
            mirror_rp = rf.mirror_rp
            if Globals.process_uid != 0:
                if mirror_rp.isreg() and not mirror_rp.readable():
                    mirror_rp.chmod(0o400 | mirror_rp.getperms())
                elif mirror_rp.isdir() and not mirror_rp.hasfullperms():
                    mirror_rp.chmod(0o700 | mirror_rp.getperms())
            yield rf
            if rf.mirror_rp.isdir() or rf.inc_rp.isdir():
                for sub_rf in rf.yield_sub_rfs():
                    for sub_sub_rf in helper(sub_rf):
                        yield sub_sub_rf

        return helper(root_rf)

    @classmethod
    def _yield_metadata(cls):
        """
        Iterate rorps from metadata file, if any are available
        """
        meta_manager = meta_mgr.get_meta_manager(cls._data_dir, True)
        metadata_iter = meta_manager.get_metas_at_time(cls._regress_time)
        if metadata_iter:
            return metadata_iter
        log.Log.FatalError(
            "No metadata for time {pt} ({rt}) found, cannot regress".format(
                pt=Time.timetopretty(cls._regress_time), rt=cls._regress_time
            )
        )

    # ### COPIED FROM FS_ABILITIES ####

    # @API(RepoShadow.get_fs_abilities, 300)
    @classmethod
    def get_fs_abilities(cls):
        if cls._must_be_writable:
            # base dir can be _potentially_ writable but actually read-only
            # to map the actual rights of the root directory, whereas the
            # data dir is alway writable
            return fs_abilities.detect_fs_abilities(cls._data_dir, writable=True)
        else:
            return fs_abilities.detect_fs_abilities(cls._base_dir, writable=False)

    # @API(RepoShadow.get_config, 201)
    @classmethod
    def get_config(cls, key):
        """
        Returns the configuration value(s) for the given key,
        or None if the configuration doesn't exist.
        """
        # the key is used as filename for now, acceptable values are
        # chars_to_quote or special_escapes
        if key not in cls._configs:
            raise ValueError("Config key '{ck}' isn't valid")
        rp = cls._data_dir.append(key)
        if not rp.lstat():
            return None
        else:
            if cls._configs[key]["type"] is set:
                return set(rp.get_string().strip().split("\n"))
            elif cls._configs[key]["type"] is bytes:
                return rp.get_bytes()

    # @API(RepoShadow.set_config, 201)
    @classmethod
    def set_config(cls, key, value):
        """
        Sets the key configuration to the given value.

        The value can currently be bytes or a set of strings.

        Returns False if there was nothing to change, None if there was no
        old value, and True if the value changed
        """
        old_value = cls.get_config(key)
        if old_value == value:
            return False
        rp = cls._data_dir.append(key)
        if rp.lstat():
            rp.delete()
        if cls._configs[key]["type"] is set:
            rp.write_string("\n".join(value))
        elif cls._configs[key]["type"] is bytes:
            rp.write_bytes(value)
        if old_value is None:  # there was no old value
            return None
        else:
            return True

    # ### LOCKING ####

    @classmethod
    def _is_locked(cls, lockfile=None, exclusive=None):
        """
        Validate if the repository is locked or not by the file
        'rdiff-backup-data/lock.yml'

        The parameters lockfile and exclusive should only be used for tests.

        Returns True if the file exists and is locked, else returns False
        """
        # we set the defaults from class attributes if not explicitly set
        if lockfile is None:
            lockfile = cls._lockfile
        if exclusive is None:
            exclusive = cls._must_be_writable
        # we need to make sure we have the last state of the lock
        lockfile.setdata()
        if not lockfile.lstat():
            return False  # if the file doesn't exist, it can't be locked
        with open(lockfile, cls.LOCK_MODE[exclusive]["open"]) as lockfd:
            try:
                locking.lock(lockfd, cls.LOCK_MODE[exclusive]["lock"])
                return False
            except BlockingIOError:
                return True

    @classmethod
    def _lock(cls, lockfile=None, exclusive=None):
        """
        Write a specific file 'rdiff-backup-data/lock.yml' to grab the lock,
        and verify that no other process took the lock by comparing its
        content.

        The parameters lockfile and exclusive should only be used for tests.

        Return True if the lock could be taken, False else.
        Return None if the lock file doesn't exist in non-exclusive mode
        """
        # we set the defaults from class attributes if not explicitly set
        if lockfile is None:
            lockfile = cls._lockfile
        if exclusive is None:
            exclusive = cls._must_be_writable
        if cls._lockfd:  # we already opened the lockfile
            return False
        pid = os.getpid()
        identifier = {
            "timestamp": Globals.current_time_string,
            "pid": pid,
            "cmd": simpleps.get_pid_name(pid),
            "hostname": socket.gethostname(),
        }
        id_yaml = yaml.safe_dump(identifier)
        lockfile.setdata()
        if not lockfile.lstat():
            if exclusive:
                open_mode = cls.LOCK_MODE[exclusive]["truncate"]
            else:
                # we can't take the lock if the file doesn't exist
                return None
        else:
            open_mode = cls.LOCK_MODE[exclusive]["open"]
        try:
            lockfd = open(lockfile, open_mode)
            locking.lock(lockfd, cls.LOCK_MODE[exclusive]["lock"])
            if exclusive:  # let's keep a trace of who's writing
                lockfd.seek(0)
                lockfd.truncate()
                lockfd.write(id_yaml)
                lockfd.flush()
            cls._lockfd = lockfd
            return True
        except BlockingIOError:
            if lockfd:
                lockfd.close()
            return False

    @classmethod
    def _unlock(cls, lockfile=None, exclusive=None):
        """
        Remove any lock existing.

        The parameters lockfile and exclusive should only be used for tests.

        We don't check for any content because we have the lock and should be
        the only process running on this repository.
        """
        # we set the defaults from class attributes if not explicitly set
        if lockfile is None:
            lockfile = cls._lockfile
        if exclusive is None:
            exclusive = cls._must_be_writable
        if cls._lockfd:
            if exclusive:  # empty the file without removing it
                cls._lockfd.seek(0)
                cls._lockfd.truncate()
            # Unlocking isn't absolutely necessary as we close the file just
            # after, which automatically removes the lock
            locking.unlock(cls._lockfd)
            cls._lockfd.close()
            cls._lockfd = None

    @classmethod
    def _get_inc_type(cls, inc):
        """Return file type increment represents"""
        assert inc.isincfile(), "File '{inc!s}' must be an increment.".format(inc=inc)
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
            log.Log.FatalError(
                "Unknown type '{ut}' of increment '{ic}'".format(ut=inc_type, ic=inc)
            )

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


class _CacheCollatedPostProcess:
    """
    Cache a collated iter of (source_rorp, dest_rorp) pairs

    This is necessary for three reasons:

    1.  The patch function may need the original source_rorp or
        dest_rp information, which is not present in the diff it
        receives.

    2.  The metadata must match what is stored in the destination
        directory.  If there is an error, either we do not update the
        dest directory for that file and the old metadata is used, or
        the file is deleted on the other end..  Thus we cannot write
        any metadata until we know the file has been processed
        correctly.

    3.  We may lack permissions on certain destination directories.
        The permissions of these directories need to be relaxed before
        we enter them to computer signatures, and then reset after we
        are done patching everything inside them.

    4.  We need some place to put hashes (like SHA1) after computing
        them and before writing them to the metadata.

    The class caches older source_rorps and dest_rps so the patch
    function can retrieve them if necessary.  The patch function can
    also update the processed correctly flag.  When an item falls out
    of the cache, we assume it has been processed, and write the
    metadata for it.
    """

    def __init__(
        self, collated_iter, cache_size, dest_root_rp, data_rp, file_statistics
    ):
        """Initialize new CCWP."""
        self.iter = collated_iter  # generates (source_rorp, dest_rorp) pairs
        self.cache_size = cache_size
        self.dest_root_rp = dest_root_rp
        self.data_rp = data_rp
        self.file_statistics = file_statistics

        self.statfileobj = statistics.init_statfileobj()
        if self.file_statistics:
            statistics.FileStats.init(self.data_rp)
        self.metawriter = meta_mgr.get_meta_manager().get_writer()

        # the following should map indices to lists
        # [source_rorp, dest_rorp, changed_flag, success_flag, increment]

        # changed_flag should be true if the rorps are different, and

        # success_flag should be 1 if dest_rorp has been successfully
        # updated to source_rorp, and 2 if the destination file is
        # deleted entirely.  They both default to false (0).

        # increment holds the RPath of the increment file if one
        # exists.  It is used to record file statistics.

        self.cache_dict = {}
        self.cache_indices = []

        # Contains a list of pairs (destination_rps, permissions) to
        # be used to reset the permissions of certain directories
        # after we're finished with them
        self.dir_perms_list = []

        # Contains list of (index, (source_rorp, diff_rorp)) pairs for
        # the parent directories of the last item in the cache.
        self.parent_list = []

    def __iter__(self):
        return self

    def __next__(self):
        """Return next (source_rorp, dest_rorp) pair.  StopIteration passed"""
        source_rorp, dest_rorp = next(self.iter)
        self._pre_process(source_rorp, dest_rorp)
        index = source_rorp and source_rorp.index or dest_rorp.index
        self.cache_dict[index] = [source_rorp, dest_rorp, 0, 0, None]
        self.cache_indices.append(index)

        if len(self.cache_indices) > self.cache_size:
            self._shorten_cache()
        return source_rorp, dest_rorp

    def in_cache(self, index):
        """Return true if given index is cached"""
        return index in self.cache_dict

    def flag_success(self, index):
        """Signal that the file with given index was updated successfully"""
        self.cache_dict[index][3] = 1

    def flag_deleted(self, index):
        """Signal that the destination file was deleted"""
        self.cache_dict[index][3] = 2

    def flag_changed(self, index):
        """Signal that the file with given index has changed"""
        self.cache_dict[index][2] = 1

    def set_inc(self, index, inc):
        """Set the increment of the current file"""
        self.cache_dict[index][4] = inc

    def get_rorps(self, index):
        """Retrieve (source_rorp, dest_rorp) from cache"""
        try:
            return self.cache_dict[index][:2]
        except KeyError:
            return self._get_parent_rorps(index)

    def get_source_rorp(self, index):
        """Retrieve source_rorp with given index from cache"""
        assert index >= self.cache_indices[0], (
            "CCPP index out of order: {idx!r} shouldn't be less than "
            "{cached!r}.".format(idx=index, cached=self.cache_indices[0])
        )
        try:
            return self.cache_dict[index][0]
        except KeyError:
            return self._get_parent_rorps(index)[0]

    def get_mirror_rorp(self, index):
        """Retrieve mirror_rorp with given index from cache"""
        try:
            return self.cache_dict[index][1]
        except KeyError:
            return self._get_parent_rorps(index)[1]

    def update_hash(self, index, sha1sum):
        """
        Update the source rorp's SHA1 hash.

        Return True if modified, else False.
        """
        target_rorp = self.get_mirror_rorp(index)
        if target_rorp and target_rorp.has_sha1():
            old_sha1 = target_rorp.get_sha1()
        else:
            old_sha1 = None
        self.get_source_rorp(index).set_sha1(sha1sum)
        return old_sha1 != sha1sum

    def update_hardlink_hash(self, diff_rorp):
        """Tag associated source_rorp with same hash diff_rorp points to"""
        sha1sum = map_hardlinks.get_sha1(diff_rorp)
        if not sha1sum:
            return
        source_rorp = self.get_source_rorp(diff_rorp.index)
        source_rorp.set_sha1(sha1sum)

    def close(self):
        """Process the remaining elements in the cache"""
        while self.cache_indices:
            self._shorten_cache()
        while self.dir_perms_list:
            dir_rp, perms = self.dir_perms_list.pop()
            dir_rp.chmod(perms)
        self.metawriter.close()
        meta_mgr.get_meta_manager().convert_meta_main_to_diff()

    def _pre_process(self, source_rorp, dest_rorp):
        """
        Do initial processing on source_rorp and dest_rorp

        It will not be clear whether source_rorp and dest_rorp have
        errors at this point, so don't do anything which assumes they
        will be backed up correctly.
        """
        if Globals.preserve_hardlinks:
            if source_rorp:
                map_hardlinks.add_rorp(source_rorp, dest_rorp)
            else:
                map_hardlinks.add_old_rorp(dest_rorp)
        if (
            dest_rorp
            and dest_rorp.isdir()
            and Globals.process_uid != 0
            and dest_rorp.getperms() % 0o1000 < 0o700
        ):
            self._unreadable_dir_init(source_rorp, dest_rorp)

    def _unreadable_dir_init(self, source_rorp, dest_rorp):
        """
        Initialize an unreadable dir.

        Make it readable, and if necessary, store the old permissions
        in self.dir_perms_list so the old perms can be restored.
        """
        dest_rp = self.dest_root_rp.new_index(dest_rorp.index)
        dest_rp.chmod(0o700 | dest_rorp.getperms())
        if source_rorp and source_rorp.isdir():
            self.dir_perms_list.append((dest_rp, source_rorp.getperms()))

    def _shorten_cache(self):
        """Remove one element from cache, possibly adding it to metadata"""
        first_index = self.cache_indices[0]
        del self.cache_indices[0]
        try:
            (
                old_source_rorp,
                old_dest_rorp,
                changed_flag,
                success_flag,
                inc,
            ) = self.cache_dict[first_index]
        except KeyError:  # probably caused by error in file system (dup)
            log.Log(
                "Index {ix} missing from CCPP cache".format(ix=first_index), log.WARNING
            )
            return
        del self.cache_dict[first_index]
        self._post_process(
            old_source_rorp, old_dest_rorp, changed_flag, success_flag, inc
        )
        if self.dir_perms_list:
            self._reset_dir_perms(first_index)
        self._update_parent_list(first_index, old_source_rorp, old_dest_rorp)

    def _update_parent_list(self, index, src_rorp, dest_rorp):
        """
        Update the parent cache with the recently expired main cache entry

        This method keeps parent directories in the secondary parent
        cache until all their children have expired from the main
        cache.  This is necessary because we may realize we need a
        parent directory's information after we have processed many
        subfiles.
        """
        if not (src_rorp and src_rorp.isdir() or dest_rorp and dest_rorp.isdir()):
            return  # neither is directory
        assert (
            self.parent_list or index == ()
        ), "Index '{idx}' must be empty if no parent in list".format(idx=index)
        if self.parent_list:
            last_parent_index = self.parent_list[-1][0]
            lp_index, li = len(last_parent_index), len(index)
            assert li <= lp_index + 1, (
                "The length of the current index '{idx}' can't be more than "
                "one greater than the last parent's '{pidx}'.".format(
                    idx=index, pidx=last_parent_index
                )
            )
            # li == lp_index + 1, means we've descended into previous parent
            # if li <= lp_index, we're in a new directory but it must have
            # a common path up to (li - 1) with the last parent
            if li <= lp_index:
                assert last_parent_index[: li - 1] == index[:-1], (
                    "Current index '{idx}' and last parent index '{pidx}' "
                    "must have a common path up to {lvl} levels.".format(
                        idx=index, pidx=last_parent_index, lvl=(li - 1)
                    )
                )
                self.parent_list = self.parent_list[:li]
        self.parent_list.append((index, (src_rorp, dest_rorp)))

    def _post_process(self, source_rorp, dest_rorp, changed, success, inc):
        """
        Post process source_rorp and dest_rorp.

        The point of this is to write statistics and metadata.

        changed will be true if the files have changed.  success will
        be true if the files have been successfully updated (this is
        always false for un-changed files).
        """
        if Globals.preserve_hardlinks and source_rorp:
            map_hardlinks.del_rorp(source_rorp)

        if not changed or success:
            if source_rorp:
                self.statfileobj.add_source_file(source_rorp)
            if dest_rorp:
                self.statfileobj.add_dest_file(dest_rorp)
        if success == 0:
            metadata_rorp = dest_rorp
        elif success == 1:
            metadata_rorp = source_rorp
        else:
            metadata_rorp = None  # in case deleted because of ListError
        if success == 1 or success == 2:
            self.statfileobj.add_changed(source_rorp, dest_rorp)

        if metadata_rorp and metadata_rorp.lstat():
            self.metawriter.write_object(metadata_rorp)
        if self.file_statistics:
            statistics.FileStats.update(source_rorp, dest_rorp, changed, inc)

    def _reset_dir_perms(self, current_index):
        """Reset the permissions of directories when we have left them"""
        dir_rp, perms = self.dir_perms_list[-1]
        dir_index = dir_rp.index
        if current_index > dir_index and current_index[: len(dir_index)] != dir_index:
            dir_rp.chmod(perms)  # out of directory, reset perms now

    def _get_parent_rorps(self, index):
        """Retrieve (src_rorp, dest_rorp) pair from parent cache"""
        for parent_index, pair in self.parent_list:
            if parent_index == index:
                return pair
        raise KeyError(index)


class _RepoPatchITRB(rorpiter.ITRBranch):
    """
    Patch an rpath with the given diff iters (use with IterTreeReducer)

    The main complication here involves directories.  We have to
    finish processing the directory after what's in the directory, as
    the directory may have inappropriate permissions to alter the
    contents or the dir's mtime could change as we change the
    contents.
    """

    FAILED = 0  # something went wrong
    DONE = 1  # successfully done
    SPECIAL = 2  # special file
    UNCHANGED = 4  # unchanged content (hash the same)

    def __init__(self, basis_root_rp, CCPP):
        """Set basis_root_rp, the base of the tree to be incremented"""
        self.basis_root_rp = basis_root_rp
        assert basis_root_rp.conn is Globals.local_connection, (
            "Basis root path connection {conn} isn't "
            "local connection {lconn}.".format(
                conn=basis_root_rp.conn, lconn=Globals.local_connection
            )
        )
        self.statfileobj = (
            statistics.get_active_statfileobj() or statistics.StatFileObj()
        )
        self.dir_replacement, self.dir_update = None, None
        self.CCPP = CCPP
        self.error_handler = robust.get_error_handler("UpdateError")

    def can_fast_process(self, index, diff_rorp):
        """True if diff_rorp and mirror are not directories"""
        mirror_rorp = self.CCPP.get_mirror_rorp(index)
        return not (diff_rorp.isdir() or (mirror_rorp and mirror_rorp.isdir()))

    def fast_process_file(self, index, diff_rorp):
        """Patch base_rp with diff_rorp (case where neither is directory)"""
        mirror_rp, discard = map_longnames.get_mirror_inc_rps(
            self.CCPP.get_rorps(index), self.basis_root_rp
        )
        assert (
            not mirror_rp.isdir()
        ), "Mirror path '{rp}' points to a directory.".format(rp=mirror_rp)
        tf = mirror_rp.get_temp_rpath(sibling=True)
        result = self._patch_to_temp(mirror_rp, diff_rorp, tf)
        if result == self.UNCHANGED:
            rpath.copy_attribs(diff_rorp, mirror_rp)
            self.CCPP.flag_success(index)
        elif result:
            if tf.lstat():
                if (
                    robust.check_common_error(
                        self.error_handler, rpath.rename, (tf, mirror_rp)
                    )
                    is None
                ):
                    self.CCPP.flag_success(index)
            elif mirror_rp and mirror_rp.lstat():
                mirror_rp.delete()
                self.CCPP.flag_deleted(index)
        # final clean-up
        tf.setdata()
        if tf.lstat():
            tf.delete()

    def start_process_directory(self, index, diff_rorp):
        """Start processing directory - record information for later"""
        self.base_rp, discard = map_longnames.get_mirror_inc_rps(
            self.CCPP.get_rorps(index), self.basis_root_rp
        )
        if diff_rorp.isdir():
            self._prepare_dir(diff_rorp, self.base_rp)
        elif self._set_dir_replacement(diff_rorp, self.base_rp):
            if diff_rorp.lstat():
                self.CCPP.flag_success(index)
            else:
                self.CCPP.flag_deleted(index)

    def end_process_directory(self):
        """Finish processing directory"""
        if self.dir_update:
            assert (
                self.base_rp.isdir()
            ), "Base directory '{rp}' isn't a directory.".format(rp=self.base_rp)
            rpath.copy_attribs(self.dir_update, self.base_rp)

            if Globals.process_uid != 0 and self.dir_update.getperms() % 0o1000 < 0o700:
                # Directory was unreadable at start -- keep it readable
                # until the end of the backup process.
                self.base_rp.chmod(0o700 | self.dir_update.getperms())
        elif self.dir_replacement:
            self.base_rp.rmdir()
            if self.dir_replacement.lstat():
                rpath.rename(self.dir_replacement, self.base_rp)

    def _patch_to_temp(self, basis_rp, diff_rorp, new):
        """
        Patch basis_rp, writing output in new, which doesn't exist yet

        Returns True if able to write new as desired, False if
        UpdateError or similar gets in the way.
        """
        if diff_rorp.isflaglinked():
            result = self._patch_hardlink_to_temp(basis_rp, diff_rorp, new)
            if result == self.FAILED or result == self.UNCHANGED:
                return result
        elif diff_rorp.get_attached_filetype() == "snapshot":
            result = self._patch_snapshot_to_temp(diff_rorp, new)
            if result == self.FAILED or result == self.SPECIAL:
                return result
        else:
            result = self._patch_diff_to_temp(basis_rp, diff_rorp, new)
            if result == self.FAILED or result == self.UNCHANGED:
                return result
        if new.lstat():
            if diff_rorp.isflaglinked():
                if generics.eas_write:
                    # `isflaglinked() == True` implies that we are processing
                    # the 2nd (or later) file in a group of files linked to an
                    # inode.  As such, we don't need to perform the usual
                    # `copy_attribs(diff_rorp, new)` for the inode because
                    # that was already done when the 1st file in the group was
                    # processed.
                    # Nonetheless, we still must perform the following task
                    # (which would have normally been performed by
                    # `copy_attribs()`).  Otherwise, the subsequent call to
                    # `_matches_cached_rorp(diff_rorp, new)` will fail because
                    # the new rorp's metadata would be missing the extended
                    # attribute data.
                    new.data["ea"] = diff_rorp.get_ea()
            else:
                rpath.copy_attribs(diff_rorp, new)
        return self._matches_cached_rorp(diff_rorp, new)

    def _patch_hardlink_to_temp(self, basis_rp, diff_rorp, new):
        """Hardlink diff_rorp to temp, update hash if necessary"""
        map_hardlinks.link_rp(diff_rorp, new, self.basis_root_rp)
        self.CCPP.update_hardlink_hash(diff_rorp)
        # if the temp file and the original file have the same inode,
        # they're the same and nothing changed to the content
        if basis_rp.getnumlinks() > 1 and basis_rp.getinode() == new.getinode():
            return self.UNCHANGED
        else:
            return self.DONE

    def _patch_snapshot_to_temp(self, diff_rorp, new):
        """
        Write diff_rorp to new, return true if successful

        Returns 1 if normal success, 2 if special file is written,
        whether or not it is successful.  This is because special
        files either fail with a SpecialFileError, or don't need to be
        compared.
        """
        if diff_rorp.isspecial():
            self._write_special(diff_rorp, new)
            rpath.copy_attribs(diff_rorp, new)
            return self.SPECIAL

        report = robust.check_common_error(
            self.error_handler, rpath.copy, (diff_rorp, new)
        )
        if isinstance(report, hash.Report):
            self.CCPP.update_hash(diff_rorp.index, report.sha1_digest)
            return self.DONE  # FIXME hash always different, no need to check?
        elif report == 0:
            # if == 0, error_handler caught something
            return self.FAILED
        else:
            return self.DONE

    def _patch_diff_to_temp(self, basis_rp, diff_rorp, new):
        """Apply diff_rorp to basis_rp, write output in new"""
        assert (
            diff_rorp.get_attached_filetype() == "diff"
        ), "Type attached to '{rp}' isn't '{exp}' but '{att}'.".format(
            rp=diff_rorp, exp="diff", att=diff_rorp.get_attached_filetype()
        )
        report = robust.check_common_error(
            self.error_handler, Rdiff.patch_local, (basis_rp, diff_rorp, new)
        )
        if isinstance(report, hash.Report):
            if self.CCPP.update_hash(diff_rorp.index, report.sha1_digest):
                return self.DONE
            else:
                return self.UNCHANGED  # hash didn't change
        elif report == 0:
            # if == 0, error_handler caught something
            return self.FAILED
        else:
            return self.DONE

    def _matches_cached_rorp(self, diff_rorp, new_rp):
        """
        Return self.DONE if new_rp matches cached src rorp else self.FAILED

        This is a final check to make sure the temp file just written
        matches the stats which we got earlier.  If it doesn't it
        could confuse the regress operation.  This is only necessary
        for regular files.
        """
        if not new_rp.isreg():
            return self.DONE
        cached_rorp = self.CCPP.get_source_rorp(diff_rorp.index)
        if cached_rorp and cached_rorp.equal_loose(new_rp):
            return self.DONE
        log.ErrorLog.write_if_open(
            "UpdateError",
            diff_rorp,
            "Updated mirror "
            "temp file '{tf}' does not match source".format(tf=new_rp),
        )
        return self.FAILED

    def _write_special(self, diff_rorp, new):
        """Write diff_rorp (which holds special file) to new"""
        eh = robust.get_error_handler("SpecialFileError")
        if robust.check_common_error(eh, rpath.copy, (diff_rorp, new)) == 0:
            new.setdata()
            if new.lstat():
                new.delete()
            new.touch()

    def _set_dir_replacement(self, diff_rorp, base_rp):
        """
        Set self.dir_replacement, which holds data until done with dir

        This is used when base_rp is a dir, and diff_rorp is not.
        Returns True for success or False for failure
        """
        assert (
            diff_rorp.get_attached_filetype() == "snapshot"
        ), "Type attached to '{rp}' isn't '{exp}' but '{att}'.".format(
            rp=diff_rorp, exp="snapshot", att=diff_rorp.get_attached_filetype()
        )
        self.dir_replacement = base_rp.get_temp_rpath(sibling=True)
        if not self._patch_to_temp(None, diff_rorp, self.dir_replacement):
            if self.dir_replacement.lstat():
                self.dir_replacement.delete()
            # Was an error, so now restore original directory
            rpath.copy_with_attribs(
                self.CCPP.get_mirror_rorp(diff_rorp.index), self.dir_replacement
            )
            return False
        else:
            return True

    def _prepare_dir(self, diff_rorp, base_rp):
        """Prepare base_rp to be a directory"""
        self.dir_update = diff_rorp.getRORPath()  # make copy in case changes
        if not base_rp.isdir():
            if base_rp.lstat():
                self.base_rp.delete()
            base_rp.setdata()
            base_rp.mkdir()
            self.CCPP.flag_success(diff_rorp.index)
        else:  # maybe no change, so query CCPP before tagging success
            if self.CCPP.in_cache(diff_rorp.index):
                self.CCPP.flag_success(diff_rorp.index)


class _RepoIncrementITRB(_RepoPatchITRB):
    """
    Patch an rpath with the given diff iters and write increments

    Like _RepoPatchITRB, but this time also write increments.
    """

    def __init__(self, basis_root_rp, inc_root_rp, rorp_cache, previous_time):
        self.inc_root_rp = inc_root_rp
        self.previous_time = previous_time
        _RepoPatchITRB.__init__(self, basis_root_rp, rorp_cache)

    def fast_process_file(self, index, diff_rorp):
        """Patch base_rp with diff_rorp and write increment (neither is dir)"""
        mirror_rp, inc_prefix = map_longnames.get_mirror_inc_rps(
            self.CCPP.get_rorps(index), self.basis_root_rp, self.inc_root_rp
        )
        tf = mirror_rp.get_temp_rpath(sibling=True)
        result = self._patch_to_temp(mirror_rp, diff_rorp, tf)
        if result == self.UNCHANGED:
            log.Log("File content unchanged, only copying attributes", log.INFO)
            rpath.copy_attribs(diff_rorp, mirror_rp)
            self.CCPP.flag_success(index)
        elif result:
            inc = robust.check_common_error(
                self.error_handler,
                increment.make_increment,
                (tf, mirror_rp, inc_prefix, self.previous_time),
            )
            if inc is not None and not isinstance(inc, int):
                self.CCPP.set_inc(index, inc)
                if inc.isreg():
                    inc.fsync_with_dir()  # Write inc before rp changed
                if tf.lstat():
                    if (
                        robust.check_common_error(
                            self.error_handler, rpath.rename, (tf, mirror_rp)
                        )
                        is None
                    ):
                        self.CCPP.flag_success(index)
                elif mirror_rp.lstat():
                    mirror_rp.delete()
                    self.CCPP.flag_deleted(index)
        # final clean-up
        tf.setdata()
        if tf.lstat():
            tf.delete()

    def start_process_directory(self, index, diff_rorp):
        """Start processing directory"""
        self.base_rp, inc_prefix = map_longnames.get_mirror_inc_rps(
            self.CCPP.get_rorps(index), self.basis_root_rp, self.inc_root_rp
        )
        self.base_rp.setdata()
        assert (
            diff_rorp.isdir() or self.base_rp.isdir()
        ), "Either diff '{ipath!r}' or base '{bpath!r}' " "must be a directory".format(
            ipath=diff_rorp, bpath=self.base_rp
        )
        if diff_rorp.isdir():
            inc = increment.make_increment(
                diff_rorp, self.base_rp, inc_prefix, self.previous_time
            )
            if inc and inc.isreg():
                inc.fsync_with_dir()  # must write inc before rp changed
            self.base_rp.setdata()  # in case written by increment above
            self._prepare_dir(diff_rorp, self.base_rp)
        elif self._set_dir_replacement(diff_rorp, self.base_rp):
            inc = increment.make_increment(
                self.dir_replacement, self.base_rp, inc_prefix, self.previous_time
            )
            if inc:
                self.CCPP.set_inc(index, inc)
                self.CCPP.flag_success(index)


class _CachedRF:
    """Store _RestoreFile objects until they are needed

    The code above would like to pretend it has random access to RFs,
    making one for a particular index at will.  However, in general
    this involves listing and filtering a directory, which can get
    expensive.

    Thus, when a _CachedRF retrieves an _RestoreFile, it creates all the
    RFs of that directory at the same time, and doesn't have to
    recalculate.  It assumes the indices will be in order, so the
    cache is deleted if a later index is requested.

    """

    def __init__(self, root_rf):
        """Initialize _CachedRF, self.rf_list variable"""
        self.root_rf = root_rf
        self.rf_list = []  # list should filled in index order
        if Globals.process_uid != 0:
            self.perm_changer = _PermissionChanger(root_rf.mirror_rp)

    def get_fp(self, index, mir_rorp):
        """Return the file object (for reading) of given index"""
        rf = map_longnames.update_rf(
            self._get_rf(index, mir_rorp),
            mir_rorp,
            self.root_rf.mirror_rp,
            _RestoreFile,
        )
        if not rf:
            log.Log(
                "Unable to retrieve data for file {fi}! The cause is "
                "probably data loss from the backup repository".format(
                    fi=(index and "/".join(index) or ".")
                ),
                log.WARNING,
            )
            return io.BytesIO()
        return rf.get_restore_fp()

    def close(self):
        """Finish remaining rps in _PermissionChanger"""
        if Globals.process_uid != 0:
            self.perm_changer.finish()

    def _get_rf(self, index, mir_rorp=None):
        """Get a _RestoreFile for given index, or None"""
        while 1:
            if not self.rf_list:
                if not self._add_rfs(index, mir_rorp):
                    return None
            rf = self.rf_list[0]
            if rf.index == index:
                if Globals.process_uid != 0:
                    self.perm_changer(index, mir_rorp)
                return rf
            elif rf.index > index:
                # Try to add earlier indices.  But if first is
                # already from same directory, or we can't find any
                # from that directory, then we know it can't be added.
                if index[:-1] == rf.index[:-1] or not self._add_rfs(index, mir_rorp):
                    return None
            else:
                del self.rf_list[0]

    def _add_rfs(self, index, mir_rorp=None):
        """Given index, add the rfs in that same directory

        Returns false if no rfs are available, which usually indicates
        an error.

        """
        if not index:
            return self.root_rf
        if mir_rorp.has_alt_mirror_name():
            return  # longname alias separate
        parent_index = index[:-1]
        if Globals.process_uid != 0:
            self.perm_changer(parent_index)
        temp_rf = _RestoreFile(
            self.root_rf.mirror_rp.new_index(parent_index),
            self.root_rf.inc_rp.new_index(parent_index),
            [],
        )
        new_rfs = list(temp_rf.yield_sub_rfs())
        if not new_rfs:
            return 0
        self.rf_list[0:0] = new_rfs
        return 1

    def _debug_list_rfs_in_cache(self, index):
        """Used for debugging, return indices of cache rfs for printing"""
        s1 = "-------- Cached RF for %s -------" % (index,)
        s2 = " ".join([str(rf.index) for rf in self.rf_list])
        s3 = "--------------------------"
        return "\n".join((s1, s2, s3))


class _RestoreFile:
    """
    Hold data about a single mirror file and its related increments

    self.relevant_incs will be set to a list of increments that matter
    for restoring a regular file.  If the patches are to mirror_rp, it
    will be the first element in self.relevant.incs
    """

    def __init__(self, mirror_rp, inc_rp, inc_list):
        self.index = mirror_rp.index
        self.mirror_rp = mirror_rp
        self.inc_rp, self.inc_list = inc_rp, inc_list
        self.set_relevant_incs()

    def __str__(self):
        return "Index: %s, Mirror: %s, Increment: %s\nIncList: %s\nIncRel: %s" % (
            self.index,
            self.mirror_rp,
            self.inc_rp,
            list(map(str, self.inc_list)),
            list(map(str, self.relevant_incs)),
        )

    @classmethod
    def initialize(cls, restore_time, mirror_time):
        """
        Initialize the _RestoreFile class with restore and mirror time
        """
        cls._restore_time = restore_time
        cls._mirror_time = mirror_time

    def set_relevant_incs(self):
        """
        Set self.relevant_incs to increments that matter for restoring

        relevant_incs is sorted newest first.  If mirror_rp matters,
        it will be (first) in relevant_incs.
        """
        self.mirror_rp.inc_type = b"snapshot"
        self.mirror_rp.inc_compressed = 0
        if not self.inc_list or self._restore_time >= self._mirror_time:
            self.relevant_incs = [self.mirror_rp]
            return

        newer_incs = self.get_newer_incs()
        i = 0
        while i < len(newer_incs):
            # Only diff type increments require later versions
            if newer_incs[i].getinctype() != b"diff":
                break
            i = i + 1
        self.relevant_incs = newer_incs[: i + 1]
        if not self.relevant_incs or self.relevant_incs[-1].getinctype() == b"diff":
            self.relevant_incs.append(self.mirror_rp)
        self.relevant_incs.reverse()  # return in reversed order

    def get_newer_incs(self):
        """
        Return list of newer incs sorted by time (increasing)

        Also discard increments older than rest_time (rest_time we are
        assuming is the exact time rdiff-backup was run, so no need to
        consider the next oldest increment or any of that)
        """
        incpairs = []
        for inc in self.inc_list:
            inc_time = inc.getinctime()
            if inc_time >= self._restore_time:
                incpairs.append((inc_time, inc))
        incpairs.sort()
        return [pair[1] for pair in incpairs]

    def get_attribs(self):
        """Return RORP with restored attributes, but no data

        This should only be necessary if the metadata file is lost for
        some reason.  Otherwise the file provides all data.  The size
        will be wrong here, because the attribs may be taken from
        diff.

        """
        last_inc = self.relevant_incs[-1]
        if last_inc.getinctype() == b"missing":
            return rpath.RORPath(self.index)

        rorp = last_inc.getRORPath()
        rorp.index = self.index
        if last_inc.getinctype() == b"dir":
            rorp.data["type"] = "dir"
        return rorp

    def get_restore_fp(self):
        """Return file object of restored data"""

        def get_fp():
            current_fp = self._get_first_fp()
            for inc_diff in self.relevant_incs[1:]:
                log.Log("Applying patch file {pf}".format(pf=inc_diff), log.DEBUG)
                assert (
                    inc_diff.getinctype() == b"diff"
                ), "Path '{irp!r}' must be of type 'diff'.".format(irp=inc_diff)
                delta_fp = inc_diff.open("rb", inc_diff.isinccompressed())
                try:
                    new_fp = tempfile.TemporaryFile()
                    Rdiff.write_patched_fp(current_fp, delta_fp, new_fp)
                    new_fp.seek(0)
                except OSError:
                    tmpdir = tempfile.gettempdir()
                    log.Log(
                        "Error while writing to temporary directory "
                        "{td}".format(td=tmpdir),
                        log.ERROR,
                    )
                    raise
                current_fp = new_fp
            return current_fp

        def error_handler(exc):
            log.Log(
                "Failed reading file {fi}, substituting empty file.".format(
                    fi=self.mirror_rp
                ),
                log.WARNING,
            )
            return io.BytesIO(b"")

        if not self.relevant_incs[-1].isreg():
            log.Log(
                """Could not restore file {rf}!

A regular file was indicated by the metadata, but could not be
constructed from existing increments because last increment had type {it}.
Instead of the actual file's data, an empty length file will be created.
This error is probably caused by data loss in the
rdiff-backup destination directory, or a bug in rdiff-backup""".format(
                    rf=self.mirror_rp, it=self.relevant_incs[-1].lstat()
                ),
                log.WARNING,
            )
            return io.BytesIO()
        return robust.check_common_error(error_handler, get_fp)

    def yield_sub_rfs(self):
        """Return _RestoreFiles under current _RestoreFile (which is dir)"""
        if not self.mirror_rp.isdir() and not self.inc_rp.isdir():
            return
        if self.mirror_rp.isdir():
            mirror_iter = self._yield_mirrorrps(self.mirror_rp)
        else:
            mirror_iter = iter([])
        if self.inc_rp.isdir():
            inc_pair_iter = self.yield_inc_complexes(self.inc_rp)
        else:
            inc_pair_iter = iter([])
        collated = rorpiter.Collate2Iters(mirror_iter, inc_pair_iter)

        for mirror_rp, inc_pair in collated:
            if not inc_pair:
                inc_rp = self.inc_rp.new_index(mirror_rp.index)
                inc_list = []
            else:
                inc_rp, inc_list = inc_pair
            if not mirror_rp:
                mirror_rp = self.mirror_rp.new_index_empty(inc_rp.index)
            yield self.__class__(mirror_rp, inc_rp, inc_list)

    def yield_inc_complexes(self, inc_rpath):
        """Yield (sub_inc_rpath, inc_list) IndexedTuples from given inc_rpath

        Finds pairs under directory inc_rpath.  sub_inc_rpath will just be
        the prefix rp, while the rps in inc_list should actually exist.

        """
        if not inc_rpath.isdir():
            return

        def get_inc_pairs():
            """Return unsorted list of (basename, inc_filenames) pairs"""
            inc_dict = {}  # dictionary of basenames:inc_filenames
            dirlist = robust.listrp(inc_rpath)

            def add_to_dict(filename):
                """Add filename to the inc tuple dictionary"""
                rp = inc_rpath.append(filename)
                if rp.isincfile() and rp.getinctype() != b"data":
                    basename = rp.getincbase_bname()
                    inc_filename_list = inc_dict.setdefault(basename, [])
                    inc_filename_list.append(filename)
                elif rp.isdir():
                    inc_dict.setdefault(filename, [])

            for filename in dirlist:
                add_to_dict(filename)
            return list(inc_dict.items())

        def inc_filenames2incrps(filenames):
            """Map list of filenames into increment rps"""
            inc_list = []
            for filename in filenames:
                rp = inc_rpath.append(filename)
                assert rp.isincfile(), "Path '{mrp}' must be an increment file.".format(
                    mrp=rp
                )
                inc_list.append(rp)
            return inc_list

        items = get_inc_pairs()
        items.sort()  # Sorting on basis of basename now
        for basename, inc_filenames in items:
            sub_inc_rpath = inc_rpath.append(basename)
            yield rorpiter.IndexedTuple(
                sub_inc_rpath.index,
                (sub_inc_rpath, inc_filenames2incrps(inc_filenames)),
            )

    def _get_first_fp(self):
        """Return first file object from relevant inc list"""
        first_inc = self.relevant_incs[0]
        assert (
            first_inc.getinctype() == b"snapshot"
        ), "Path '{srp}' must be of type 'snapshot'.".format(srp=first_inc)
        if not first_inc.isinccompressed():
            return first_inc.open("rb")

        try:
            # current_fp must be a real (uncompressed) file
            current_fp = tempfile.TemporaryFile()
            fp = first_inc.open("rb", compress=1)
            rpath.copyfileobj(fp, current_fp)
            fp.close()
            current_fp.seek(0)
        except OSError:
            tmpdir = tempfile.gettempdir()
            log.Log(
                "Error while writing to temporary directory " "{td}".format(td=tmpdir),
                log.ERROR,
            )
            raise
        return current_fp

    def _yield_mirrorrps(self, mirrorrp):
        """Yield mirrorrps underneath given mirrorrp"""
        assert mirrorrp.isdir(), "Mirror path '{mrp}' must be a directory.".format(
            mrp=mirrorrp
        )
        for filename in robust.listrp(mirrorrp):
            rp = mirrorrp.append(filename)
            if rp.index != (b"rdiff-backup-data",):
                yield rp

    def _debug_relevant_incs_string(self):
        """Return printable string of relevant incs, used for debugging"""
        inc_header = ["---- Relevant incs for %s" % ("/".join(self.index),)]
        inc_header.extend(
            [
                "{itp} {ils} {irp}".format(
                    itp=inc.getinctype(), ils=inc.lstat(), irp=inc
                )
                for inc in self.relevant_incs
            ]
        )
        inc_header.append("--------------------------------")
        return "\n".join(inc_header)


class _PermissionChanger:
    """Change the permission of mirror files and directories

    The problem is that mirror files and directories may need their
    permissions changed in order to be read and listed, and then
    changed back when we are done.  This class hooks into the _CachedRF
    object to know when an rp is needed.

    """

    def __init__(self, root_rp):
        self.root_rp = root_rp
        self.current_index = ()
        # Below is a list of (index, rp, old_perm) triples in reverse
        # order that need clearing
        self.open_index_list = []

    def __call__(self, index, mir_rorp=None):
        """Given rpath, change permissions up to and including index"""
        if mir_rorp and mir_rorp.has_alt_mirror_name():
            return
        old_index = self.current_index
        self.current_index = index
        if not index or index <= old_index:
            return
        self._restore_old(index)
        self._add_chmod_new(old_index, index)

    def finish(self):
        """Restore any remaining rps"""
        for index, rp, perms in self.open_index_list:
            rp.chmod(perms)

    def _restore_old(self, index):
        """Restore permissions for indices we are done with"""
        while self.open_index_list:
            old_index, old_rp, old_perms = self.open_index_list[0]
            if index[: len(old_index)] > old_index:
                old_rp.chmod(old_perms)
            else:
                break
            del self.open_index_list[0]

    def _add_chmod_new(self, old_index, index):
        """Change permissions of directories between old_index and index"""
        for rp in self._get_new_rp_list(old_index, index):
            if (rp.isreg() and not rp.readable()) or (
                rp.isdir() and not (rp.executable() and rp.readable())
            ):
                old_perms = rp.getperms()
                self.open_index_list.insert(0, (rp.index, rp, old_perms))
                if rp.isreg():
                    rp.chmod(0o400 | old_perms)
                else:
                    rp.chmod(0o700 | old_perms)

    def _get_new_rp_list(self, old_index, index):
        """Return list of new rp's between old_index and index

        Do this lazily so that the permissions on the outer
        directories are fixed before we need the inner dirs.

        """
        for i in range(len(index) - 1, -1, -1):
            if old_index[:i] == index[:i]:
                common_prefix_len = i
                break  # latest with i==0 does the break happen

        for total_len in range(common_prefix_len + 1, len(index) + 1):
            yield self.root_rp.new_index(index[:total_len])


class _RegressFile(_RestoreFile):
    """
    Like _RestoreFile but with metadata

    Hold mirror_rp and related incs, but also put metadata info for
    the mirror file at regress time in self.metadata_rorp.
    self.metadata_rorp is not set in this class.
    """

    def __init__(self, mirror_rp, inc_rp, inc_list):
        super().__init__(mirror_rp, inc_rp, inc_list)

    def set_relevant_incs(self):
        super().set_relevant_incs()

        # Set self.regress_inc to increment to be removed (or None)
        newer_incs = self.get_newer_incs()
        assert len(newer_incs) <= 1, "Too many recent increments"
        if newer_incs:
            self.regress_inc = newer_incs[0]  # first is mirror_rp
        else:
            self.regress_inc = None

    def set_metadata_rorp(self, metadata_rorp):
        """Set self.metadata_rorp, creating empty if given None"""
        if metadata_rorp:
            self.metadata_rorp = metadata_rorp
        else:
            self.metadata_rorp = rpath.RORPath(self.index)

    def isdir(self):
        """Return true if regress needs before/after processing"""
        return (self.metadata_rorp and self.metadata_rorp.isdir()) or (
            self.mirror_rp and self.mirror_rp.isdir()
        )


class _RepoRegressITRB(rorpiter.ITRBranch):
    """
    Turn back state of dest directory (use with IterTreeReducer)

    The arguments to the ITR will be _RegressFiles.  There are two main
    assumptions this procedure makes (besides those mentioned above):

    1.  The mirror_rp and the metadata_rorp equal_loose correctly iff
        they contain the same data.  If this is the case, then the inc
        file is unnecessary and we can delete it.

    2.  If the don't match, then applying the inc file will
        successfully get us back to the previous state.

    Since the metadata file is required, the two above really only
    matter for regular files.
    """

    def __init__(self):
        """Just initialize some variables to None"""
        self.rf = None  # will hold _RegressFile applying to a directory

    def can_fast_process(self, index, rf):
        """True if none of the rps is a directory"""
        return not rf.mirror_rp.isdir() and not rf.metadata_rorp.isdir()

    def fast_process_file(self, index, rf):
        """Process when nothing is a directory"""
        if not rf.metadata_rorp.equal_loose(rf.mirror_rp):
            log.Log("Regressing file {fi}".format(fi=rf.metadata_rorp), log.INFO)
            if rf.metadata_rorp.isreg():
                self._restore_orig_regfile(rf)
            else:
                if rf.mirror_rp.lstat():
                    rf.mirror_rp.delete()
                if rf.metadata_rorp.isspecial():
                    robust.check_common_error(
                        None, rpath.copy_with_attribs, (rf.metadata_rorp, rf.mirror_rp)
                    )
                else:
                    rpath.copy_with_attribs(rf.metadata_rorp, rf.mirror_rp)
        if rf.regress_inc:
            log.Log("Deleting increment {ic}".format(ic=rf.regress_inc), log.INFO)
            rf.regress_inc.delete()

    def start_process_directory(self, index, rf):
        """Start processing directory"""
        if rf.metadata_rorp.isdir():
            # make sure mirror is a readable dir
            if not rf.mirror_rp.isdir():
                if rf.mirror_rp.lstat():
                    rf.mirror_rp.delete()
                rf.mirror_rp.mkdir()
            if not rf.mirror_rp.hasfullperms():
                rf.mirror_rp.chmod(0o700)
        self.rf = rf

    def end_process_directory(self):
        """Finish processing a directory"""
        rf = self.rf
        mir_rp = rf.mirror_rp
        meta_rorp = rf.metadata_rorp
        if meta_rorp.isdir():
            if mir_rp.isdir():
                mir_rp.setdata()
                if not meta_rorp.equal_loose(mir_rp):
                    log.Log(
                        "Regressing attributes of path {pa}".format(pa=mir_rp), log.INFO
                    )
                    rpath.copy_attribs(meta_rorp, mir_rp)
            else:
                mir_rp.delete()
                log.Log("Regressing file {fi}".format(fi=mir_rp), log.INFO)
                rpath.copy_with_attribs(meta_rorp, mir_rp)
        else:  # replacing a dir with some other kind of file
            assert mir_rp.isdir(), "Mirror '{mrp!r}' can only be a directory.".format(
                mrp=mir_rp
            )
            log.Log("Replacing directory {di}".format(di=mir_rp), log.INFO)
            if meta_rorp.isreg():
                self._restore_orig_regfile(rf)
            else:
                mir_rp.delete()
                rpath.copy_with_attribs(meta_rorp, mir_rp)
        if rf.regress_inc:
            log.Log("Deleting increment {ic}".format(ic=rf.regress_inc), log.INFO)
            rf.regress_inc.delete()

    def _restore_orig_regfile(self, rf):
        """
        Restore original regular file

        This is the trickiest case for avoiding information loss,
        because we don't want to delete the increment before the
        mirror is fully written.
        """
        assert (
            rf.metadata_rorp.isreg()
        ), "Metadata path '{mp}' can only be regular file.".format(mp=rf.metadata_rorp)
        if rf.mirror_rp.isreg():
            # Before restoring file from history, check if the versions are already identical.
            if (
                rf.mirror_rp.getsize() == rf.metadata_rorp.getsize()
                and rf.metadata_rorp.has_sha1()
                and rf.metadata_rorp.get_sha1() == hash.compute_sha1(rf.mirror_rp)
            ):
                rpath.copy_attribs(rf.metadata_rorp, rf.mirror_rp)
            else:
                tf = rf.mirror_rp.get_temp_rpath(sibling=True)
                tf.write_from_fileobj(rf.get_restore_fp())
                tf.fsync_with_dir()  # make sure tf fully written before move
                rpath.copy_attribs(rf.metadata_rorp, tf)
                rpath.rename(tf, rf.mirror_rp)  # move is atomic
        else:
            if rf.mirror_rp.lstat():
                rf.mirror_rp.delete()
            rf.mirror_rp.write_from_fileobj(rf.get_restore_fp())
            rpath.copy_attribs(rf.metadata_rorp, rf.mirror_rp)
        if Globals.fsync_directories:
            rf.mirror_rp.get_parent_rp().fsync()  # force move before inc delete
