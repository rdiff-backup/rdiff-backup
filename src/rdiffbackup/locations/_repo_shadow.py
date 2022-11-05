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
    C, Globals, hash, increment, iterfile, log,
    Rdiff, robust, rorpiter, rpath, selection, statistics, Time,
)
from rdiffbackup import meta_mgr
from rdiffbackup.locations import fs_abilities
from rdiffbackup.locations.map import hardlinks as map_hardlinks
from rdiffbackup.locations.map import longnames as map_longnames
from rdiffbackup.locations.map import owners as map_owners
from rdiffbackup.utils import locking, simpleps

# ### COPIED FROM BACKUP ####


# @API(RepoShadow, 201)
class RepoShadow:
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
        True: {"open": "r+", "truncate": "w",
               "lock": locking.LOCK_EX | locking.LOCK_NB},
        False: {"open": "r", "lock": locking.LOCK_SH | locking.LOCK_NB},
    }

    # @API(RepoShadow.setup_paths, 201)
    @classmethod
    def setup_paths(cls, base_dir, data_dir, incs_dir):
        """
        Setup the base, data and increments directories for further use
        """
        cls._base_dir = base_dir
        cls._data_dir = data_dir
        cls._incs_dir = incs_dir

    # @API(RepoShadow.get_sigs, 201)
    @classmethod
    def get_sigs(cls, baserp, source_iter, previous_time, is_remote):
        """
        Setup cache and return a signatures iterator
        """
        cls._set_rorp_cache(baserp, source_iter, previous_time)
        return cls._sigs_iterator(baserp, is_remote)

    # @API(RepoShadow.apply, 201)
    @classmethod
    def apply(cls, dest_rpath, source_diffiter,
              inc_rpath=None, previous_time=None):
        """
        Patch dest_rpath with rorpiter of diffs and optionally write increments

        This function is used for first and follow-up backups
        within a repository.
        """
        if previous_time:
            ITR = rorpiter.IterTreeReducer(
                _RepoIncrementITRB,
                [dest_rpath, inc_rpath, cls.CCPP, previous_time])
            log_msg = "Processing changed file {cf}"
        else:
            ITR = rorpiter.IterTreeReducer(
                _RepoPatchITRB, [dest_rpath, cls.CCPP])
            log_msg = "Processing file {cf}"
        for diff in rorpiter.FillInIter(source_diffiter, dest_rpath):
            log.Log(log_msg.format(cf=diff), log.INFO)
            ITR(diff.index, diff)
        ITR.finish_processing()
        cls.CCPP.close()
        dest_rpath.setdata()

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

        meta_manager = meta_mgr.get_meta_manager(True)
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
            collated, Globals.pipeline_max_length * 4, baserp)
        # pipeline len adds some leeway over just*3 (to and from and back)

    @classmethod
    def _sigs_iterator(cls, baserp, is_remote):
        """
        Yield signatures of any changed destination files
        """
        flush_threshold = Globals.pipeline_max_length - 2
        num_rorps_seen = 0
        for src_rorp, dest_rorp in cls.CCPP:
            # If we are backing up across a pipe, we must flush the pipeline
            # every so often so it doesn't get congested on destination end.
            if is_remote:
                num_rorps_seen += 1
                if (num_rorps_seen > flush_threshold):
                    num_rorps_seen = 0
                    yield iterfile.MiscIterFlushRepeat
            if not (src_rorp and dest_rorp and src_rorp == dest_rorp
                    and (not Globals.preserve_hardlinks
                         or map_hardlinks.rorp_eq(src_rorp, dest_rorp))):

                index = src_rorp and src_rorp.index or dest_rorp.index
                sig = cls._get_one_sig(baserp, index, src_rorp, dest_rorp)
                if sig:
                    cls.CCPP.flag_changed(index)
                    yield sig

    @classmethod
    def _get_one_sig(cls, baserp, index, src_rorp, dest_rorp):
        """Return a signature given source and destination rorps"""
        if (Globals.preserve_hardlinks and src_rorp
                and map_hardlinks.is_linked(src_rorp)):
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
                "UpdateError", dest_rp,
                "File changed from regular file before signature")
            return None
        if (Globals.process_uid != 0 and not dest_rp.readable()
                and dest_rp.isowner()):
            # This branch can happen with root source and non-root
            # destination.  Permissions are changed permanently, which
            # should propagate to the diffs
            dest_rp.chmod(0o400 | dest_rp.getperms())
        try:
            return Rdiff.get_signature(dest_rp)
        except OSError as e:
            if (e.errno == errno.EPERM or e.errno == errno.EACCES):
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
                            ex=exc, fi=dest_rp))
            else:
                raise

    # @API(RepoShadow.touch_current_mirror, 201)
    @classmethod
    def touch_current_mirror(cls, data_dir, current_time_str):
        """
        Make a file like current_mirror.<datetime>.data to record time

        When doing an incremental backup, this should happen before any
        other writes, and the file should be removed after all writes.
        That way we can tell whether the previous session aborted if there
        are two current_mirror files.

        When doing the initial full backup, the file can be created after
        everything else is in place.
        """
        mirrorrp = data_dir.append(b'.'.join(
            (b"current_mirror", os.fsencode(current_time_str), b"data")))
        log.Log("Writing mirror marker {mm}".format(mm=mirrorrp), log.INFO)
        try:
            pid = os.getpid()
        except BaseException:
            pid = "NA"
        mirrorrp.write_string("PID {pp}\n".format(pp=pid))
        mirrorrp.fsync_with_dir()

    # @API(RepoShadow.remove_current_mirror, 201)
    @classmethod
    def remove_current_mirror(cls, data_dir):
        """
        Remove the older of the current_mirror files.

        Use at end of session
        """
        curmir_incs = data_dir.append(b"current_mirror").get_incfiles_list()
        assert len(curmir_incs) == 2, (
            "There must be two current mirrors not '{ilen}'.".format(
                ilen=len(curmir_incs)))
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
        if Globals.print_statistics:
            statistics.print_active_stats(end_time)
        if Globals.file_statistics:
            statistics.FileStats.close()
        statistics.write_active_statfileobj(end_time)

# ### COPIED FROM RESTORE ####

    # @API(RepoShadow.init_loop, 201)
    @classmethod
    def init_loop(cls, data_dir, mirror_base, inc_base, restore_to_time):
        """
        Initialize repository for looping through the increments
        """
        cls._initialize_restore(data_dir, restore_to_time)
        cls._initialize_rf_cache(mirror_base, inc_base)

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
                b"current_mirror").get_incfiles_list()
            if not cur_mirror_incs:
                if must_exist:
                    log.Log.FatalError("Could not get time of current mirror")
                else:
                    cls._mirror_time = 0
            elif len(cur_mirror_incs) > 1:
                log.Log("Two different times for current mirror were found, "
                        "it seems that the last backup failed, "
                        "you most probably want to regress the repository",
                        log.WARNING)
                if must_exist:
                    cls._mirror_time = cur_mirror_incs[0].getinctime()
                else:
                    cls._mirror_time = -1
            else:
                cls._mirror_time = cur_mirror_incs[0].getinctime()
        return cls._mirror_time

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
    def _initialize_restore(cls, data_dir, restore_to_time):
        """
        Set class variable _restore_time on mirror conn
        """
        cls._data_dir = data_dir
        cls._set_restore_time(restore_to_time)
        # it's a bit ugly to set the values to another class, but less than
        # the other way around as it used to be
        _RestoreFile.initialize(cls._restore_time,
                                cls.get_mirror_time(must_exist=True))

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

        meta_manager = meta_mgr.get_meta_manager(True)
        rorp_iter = meta_manager.get_metas_at_time(rest_time,
                                                   cls.mirror_base.index)
        if not rorp_iter:
            if require_metadata:
                log.Log.FatalError("Mirror metadata not found")
            log.Log("Mirror metadata not found, reading from directory",
                    log.WARNING)
            rorp_iter = cls._get_rorp_iter_from_rf(cls.root_rf)

        if cls._select:
            rorp_iter = selection.FilterIter(cls._select, rorp_iter)
        return rorp_iter

    # @API(RepoShadow.set_select, 201)
    @classmethod
    def set_select(cls, target_rp, select_opts, *filelists):
        """Initialize the mirror selection object"""
        if not select_opts:
            return  # nothing to do...
        cls._select = selection.Select(target_rp)
        cls._select.parse_selection_args(select_opts, filelists)

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
                assert rorp.index[:len(index)] == index, (
                    "Path '{ridx}' must be a sub-path of '{idx}'.".format(
                        ridx=rorp.index, idx=index))
                rorp.index = rorp.index[len(index):]
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
        mir_iter = cls._subtract_indices(cls.mirror_base.index,
                                         cls._get_mirror_rorp_iter())
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
            if (not target_rorp or not mir_rorp or not mir_rorp == target_rorp
                    or (Globals.preserve_hardlinks
                        and not map_hardlinks.rorp_eq(mir_rorp, target_rorp))):
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
        mir_rorp.set_attached_filetype('snapshot')
        return mir_rorp

# ### COPIED FROM RESTORE (LIST) ####

    # @API(RepoShadow.list_files_changed_since, 201)
    @classmethod
    def list_files_changed_since(cls, mirror_rp, inc_rp, data_dir,
                                 restore_to_time):
        """
        List the changed files under mirror_rp since rest time

        Notice the output is an iterator of RORPs.  We do this because we
        want to give the remote connection the data in buffered
        increments, and this is done automatically for rorp iterators.
        Encode the lines in the first element of the rorp's index.
        """
        assert mirror_rp.conn is Globals.local_connection, "Run locally only"
        cls.init_loop(data_dir, mirror_rp, inc_rp, restore_to_time)

        old_iter = cls._get_mirror_rorp_iter(cls._restore_time, True)
        cur_iter = cls._get_mirror_rorp_iter(cls.get_mirror_time(must_exist=True),
                                             True)
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
            path_desc = (old_rorp and str(old_rorp) or str(cur_rorp))
            yield rpath.RORPath(("%-7s %s" % (change, path_desc), ))
        cls.finish_loop()

    # @API(RepoShadow.list_files_at_time, 201)
    @classmethod
    def list_files_at_time(cls, mirror_rp, inc_rp, data_dir, reftime):
        """
        List the files in archive at the given time

        Output is a RORP Iterator with info in index.
        See list_files_changed_since for details.
        """
        assert mirror_rp.conn is Globals.local_connection, "Run locally only"
        cls.init_loop(data_dir, mirror_rp, inc_rp, reftime)
        old_iter = cls._get_mirror_rorp_iter()
        for rorp in old_iter:
            yield rorp
        cls.finish_loop()

# ### COPIED FROM MANAGE ####

    # @API(RepoShadow.remove_increments_older_than, 201)
    @classmethod
    def remove_increments_older_than(cls, baserp, reftime):
        """
        Remove increments older than the given time
        """
        assert baserp.conn is Globals.local_connection, (
            "Function should be called only locally "
            "and not over '{co}'.".format(co=baserp.conn))

        def yield_files(rp):
            if rp.isdir():
                for filename in rp.listdir():
                    for sub_rp in yield_files(rp.append(filename)):
                        yield sub_rp
            yield rp

        for rp in yield_files(baserp):
            if ((rp.isincfile() and rp.getinctime() < reftime)
                    or (rp.isdir() and not rp.listdir())):
                log.Log("Deleting increment file {fi}".format(fi=rp), log.INFO)
                rp.delete()

# ### COPIED FROM COMPARE ####

    # @API(RepoShadow.init_and_get_loop, 201)
    @classmethod
    def init_and_get_loop(cls, data_dir, mirror_rp, inc_rp, compare_time,
                          src_iter=None):
        """
        Return rorp iter at given compare time

        Attach necessary file details if src_iter is given

        cls.finish_loop must be called to finish the loop once initialized
        """
        cls.init_loop(data_dir, mirror_rp, inc_rp, compare_time)
        repo_iter = cls._subtract_indices(cls.mirror_base.index,
                                          cls._get_mirror_rorp_iter())
        if src_iter is None:
            return repo_iter
        else:
            return cls._attach_files(data_dir, mirror_rp, inc_rp, compare_time,
                                     src_iter, repo_iter)

    @classmethod
    def _attach_files(cls, data_dir, mirror_rp, inc_rp, compare_time,
                      src_iter, repo_iter):
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
                if (src_rorp.isreg() and mir_rorp.isreg()
                        and src_rorp.getsize() == mir_rorp.getsize()):
                    fp = cls.rf_cache.get_fp(base_index + index, mir_rorp)
                    mir_rorp.setfile(fp)
                    mir_rorp.set_attached_filetype('snapshot')

            if mir_rorp:
                yield mir_rorp
            else:
                yield rpath.RORPath(index)  # indicate deleted mir_rorp

    # @API(RepoShadow.verify, 201)
    @classmethod
    def verify(cls, data_dir, mirror_rp, inc_rp, verify_time):
        """
        Compute SHA1 sums of repository files and check against metadata
        """
        assert mirror_rp.conn is Globals.local_connection, (
            "Only verify mirror locally, not remotely over '{conn}'.".format(
                conn=mirror_rp.conn))
        repo_iter = cls.init_and_get_loop(data_dir, mirror_rp, inc_rp,
                                          verify_time)
        base_index = cls.mirror_base.index

        bad_files = 0
        no_hash = 0
        ret_code = Globals.RET_CODE_OK
        for repo_rorp in repo_iter:
            if not repo_rorp.isreg():
                continue
            verify_sha1 = map_hardlinks.get_hash(repo_rorp)
            if not verify_sha1:
                log.Log("Cannot find SHA1 digest for file {fi}, perhaps "
                        "because this feature was added in v1.1.1".format(
                            fi=repo_rorp), log.WARNING)
                no_hash += 1
                ret_code |= Globals.RET_CODE_FILE_WARN
                continue
            fp = cls.rf_cache.get_fp(base_index + repo_rorp.index, repo_rorp)
            computed_hash = hash.compute_sha1_fp(fp)
            if computed_hash == verify_sha1:
                log.Log("Verified SHA1 digest of file {fi}".format(
                    fi=repo_rorp), log.INFO)
            else:
                bad_files += 1
                log.Log("Computed SHA1 digest of file {fi} '{cd}' "
                        "doesn't match recorded digest of '{rd}'. "
                        "Your backup repository may be corrupted!".format(
                            fi=repo_rorp, cd=computed_hash, rd=verify_sha1),
                        log.ERROR)
                ret_code |= Globals.RET_CODE_FILE_ERR
        cls.finish_loop()
        if bad_files:
            log.Log(
                "Verification found {cf} potentially corrupted files".format(
                    cf=bad_files), log.ERROR)
            if no_hash:
                log.Log("Verification also found {fi} files without "
                        "hash".format(fi=no_hash), log.NOTE)
        elif no_hash:
            log.Log("Verification found {fi} files without hash, all others "
                    "could be verified successfully".format(fi=no_hash),
                    log.NOTE)
        else:
            log.Log("All files verified successfully", log.NOTE)
        return ret_code

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
    def needs_regress(cls, base_dir, data_dir, incs_dir, force):
        """
        Checks if the repository contains a previously failed backup and needs
        to be regressed

        Note that this function won't catch an initial failed backup, this
        needs to be done during the repository creation phase.

        Return None if the repository can't be found or is new,
        True if it needs regressing, False otherwise.
        """
        # detect an initial repository which doesn't need a regression
        if not (base_dir.isdir() and data_dir.isdir()
                and incs_dir.isdir() and incs_dir.listdir()):
            return None
        curmirroot = data_dir.append(b"current_mirror")
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

""".format(dd=data_dir))
        elif len(curmir_incs) == 1:
            return False
        else:
            if not force:
                try:
                    cls._check_pids(curmir_incs)
                except OSError as exc:
                    log.Log.FatalError(
                        "Could not check if rdiff-backup is currently"
                        "running due to exception '{ex}'".format(ex=exc))
            assert len(curmir_incs) == 2, (
                "Found more than 2 current_mirror incs in '{ci}'.".format(
                    ci=data_dir))
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
            if os.name == 'nt':
                import win32api
                import win32con
                import pywintypes
                process = None
                try:
                    process = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS,
                                                   0, pid)
                except pywintypes.error as error:
                    if error.winerror == 87:
                        # parameter incorrect, PID does not exist
                        return False
                    elif error.winerror == 5:
                        # access denied, means nevertheless PID still exists
                        return True
                    else:
                        log.Log("Unable to check if process ID {pi} "
                                "is still running".format(pi=pid), log.WARNING)
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
                    log.Log("Unable to check if process ID {pi} "
                            "is still running".format(pi=pid), log.WARNING)
                    return None  # we don't know if the process is still running
                else:  # the process still exists
                    return True

        for curmir_rp in curmir_incs:
            assert curmir_rp.conn is Globals.local_connection, (
                "Function must be called locally not over '{conn}'.".format(
                    conn=curmir_rp.conn))
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
    --force option""".format(pi=pid))

    # @API(RepoShadow.regress, 201)
    @classmethod
    def regress(cls, base_rp, incs_rp):
        """
        Bring mirror and inc directory back to regress_to_time

        Regress should only work one step at a time (i.e. don't "regress"
        through two separate backup sets.  This function should be run
        locally to the rdiff-backup-data directory.
        """
        assert base_rp.index == () and incs_rp.index == (), (
            "Mirror and increment paths must have an empty index")
        assert base_rp.isdir() and incs_rp.isdir(), (
            "Mirror and increments paths must be directories")
        assert base_rp.conn is incs_rp.conn is Globals.local_connection, (
            "Regress must happen locally.")
        meta_manager, former_current_mirror_rp = cls._set_regress_time()
        cls._set_restore_times()
        _RegressFile.initialize(cls._restore_time, cls._mirror_time)
        cls._regress_rbdir(meta_manager)
        ITR = rorpiter.IterTreeReducer(_RepoRegressITRB, [])
        for rf in cls._iterate_meta_rfs(base_rp, incs_rp):
            ITR(rf.index, rf)
        ITR.finish_processing()
        if former_current_mirror_rp:
            if Globals.do_fsync:
                # Sync first, since we are marking dest dir as good now
                C.sync()
            former_current_mirror_rp.delete()

    @classmethod
    def _set_regress_time(cls):
        """
        Set regress_time to previous successful backup

        If there are two current_mirror increments, then the last one
        corresponds to a backup session that failed.
        """
        meta_manager = meta_mgr.get_meta_manager(True)
        curmir_incs = meta_manager.sorted_prefix_inclist(b'current_mirror')
        assert len(curmir_incs) == 2, (
            "Found {ilen} current_mirror flags, expected 2".format(
                ilen=len(curmir_incs)))
        mirror_rp_to_delete = curmir_incs[0]
        cls._regress_time = curmir_incs[1].getinctime()
        cls._unsuccessful_backup_time = mirror_rp_to_delete.getinctime()
        log.Log("Regressing to date/time {dt}".format(
            dt=Time.timetopretty(cls._regress_time)), log.NOTE)
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
            if old_rp.getincbase_bname() == b'mirror_metadata':
                if old_rp.getinctype() == b'snapshot':
                    meta_snaps.append(old_rp)
                elif old_rp.getinctype() == b'diff':
                    meta_diffs.append(old_rp)
                else:
                    raise ValueError(
                        "Increment type for metadata mirror must be one of "
                        "'snapshot' or 'diff', not {mtype}.".format(
                            mtype=old_rp.getinctype()))
        if meta_diffs and not meta_snaps:
            meta_manager.recreate_attr(cls._regress_time)

        for new_rp in meta_manager.timerpmap[cls._unsuccessful_backup_time]:
            if new_rp.getincbase_bname() != b'current_mirror':
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
            raw_rf = map_longnames.update_rf(raw_rf, metadata_rorp, mirror_rp,
                                             _RegressFile)
            if not raw_rf:
                log.Log("Warning, metadata file has entry for path {pa}, "
                        "but there are no associated files.".format(
                            pa=metadata_rorp), log.WARNING)
                continue
            raw_rf.set_metadata_rorp(metadata_rorp)
            yield raw_rf

    @classmethod
    def _iterate_raw_rfs(cls, mirror_rp, inc_rp):
        """Iterate all _RegressFile objects in mirror/inc directory

        Also changes permissions of unreadable files.  We don't have to
        change them back later because regress will do that for us.

        """
        root_rf = _RegressFile(mirror_rp, inc_rp,
                               inc_rp.get_incfiles_list())

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
        meta_manager = meta_mgr.get_meta_manager(True)
        metadata_iter = meta_manager.get_metas_at_time(cls._regress_time)
        if metadata_iter:
            return metadata_iter
        log.Log.FatalError(
            "No metadata for time {pt} ({rt}) found, cannot regress".format(
                pt=Time.timetopretty(cls._regress_time), rt=cls._regress_time))

# ### COPIED FROM FS_ABILITIES ####

    # @API(RepoShadow.get_fs_abilities_readonly, 201)
    @classmethod
    def get_fs_abilities_readonly(cls, base_dir):
        return fs_abilities.FSAbilities(base_dir, writable=False)

    # @API(RepoShadow.get_fs_abilities_readwrite, 201)
    @classmethod
    def get_fs_abilities_readwrite(cls, base_dir):
        return fs_abilities.FSAbilities(base_dir, writable=True)

    # @API(RepoShadow.get_config, 201)
    @classmethod
    def get_config(cls, data_dir, key):
        """
        Returns the configuration value(s) for the given key,
        or None if the configuration doesn't exist.
        """
        # the key is used as filename for now, acceptable values are
        # chars_to_quote or special_escapes
        if key not in cls._configs:
            raise ValueError("Config key '{ck}' isn't valid")
        rp = data_dir.append(key)
        if not rp.lstat():
            return None
        else:
            if cls._configs[key]["type"] is set:
                return set(rp.get_string().strip().split("\n"))
            elif cls._configs[key]["type"] is bytes:
                return rp.get_bytes()

    # @API(RepoShadow.set_config, 201)
    @classmethod
    def set_config(cls, data_dir, key, value):
        """
        Sets the key configuration to the given value.

        The value can currently be bytes or a set of strings.

        Returns False if there was nothing to change, None if there was no
        old value, and True if the value changed
        """
        old_value = cls.get_config(data_dir, key)
        if old_value == value:
            return False
        rp = data_dir.append(key)
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

    # @API(RepoShadow.init_owners_mapping, 201)
    @classmethod
    def init_owners_mapping(cls, users_map, groups_map, preserve_num_ids):
        map_owners.init_users_mapping(users_map, preserve_num_ids)
        map_owners.init_groups_mapping(groups_map, preserve_num_ids)

# ### LOCKING ####

    # @API(RepoShadow.is_locked, 201)
    @classmethod
    def is_locked(cls, lockfile, exclusive):
        """
        Validate if the repository is locked or not by the file
        'rdiff-backup-data/lock.yml'

        Returns True if the file exists and is locked, else returns False
        """
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

    # @API(RepoShadow.lock, 201)
    @classmethod
    def lock(cls, lockfile, exclusive, force=False):
        """
        Write a specific file 'rdiff-backup-data/lock.yml' to grab the lock,
        and verify that no other process took the lock by comparing its
        content.

        Return True if the lock could be taken, False else.
        Return None if the lock file doesn't exist in non-exclusive mode
        """
        if cls._lockfd:  # we already opened the lockfile
            return False
        pid = os.getpid()
        identifier = {
            'timestamp': Globals.current_time_string,
            'pid': pid,
            'cmd': simpleps.get_pid_name(pid),
            'hostname': socket.gethostname(),
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

    # @API(RepoShadow.unlock, 201)
    @classmethod
    def unlock(cls, lockfile, exclusive):
        """
        Remove any lock existing.

        We don't check for any content because we have the lock and should be
        the only process running on this repository.
        """
        if cls._lockfd:
            if exclusive:  # empty the file without removing it
                cls._lockfd.seek(0)
                cls._lockfd.truncate()
            # Unlocking isn't absolutely necessary as we close the file just
            # after, which automatically removes the lock
            locking.unlock(cls._lockfd)
            cls._lockfd.close()
            cls._lockfd = None


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

    def __init__(self, collated_iter, cache_size, dest_root_rp):
        """Initialize new CCWP."""
        self.iter = collated_iter  # generates (source_rorp, dest_rorp) pairs
        self.cache_size = cache_size
        self.dest_root_rp = dest_root_rp

        self.statfileobj = statistics.init_statfileobj()
        if Globals.file_statistics:
            statistics.FileStats.init()
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
            "{cached!r}.".format(idx=index, cached=self.cache_indices[0]))
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
        if (dest_rorp and dest_rorp.isdir() and Globals.process_uid != 0
                and dest_rorp.getperms() % 0o1000 < 0o700):
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
            (old_source_rorp, old_dest_rorp, changed_flag, success_flag,
             inc) = self.cache_dict[first_index]
        except KeyError:  # probably caused by error in file system (dup)
            log.Log("Index {ix} missing from CCPP cache".format(
                ix=first_index), log.WARNING)
            return
        del self.cache_dict[first_index]
        self._post_process(old_source_rorp, old_dest_rorp, changed_flag,
                           success_flag, inc)
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
        if not (src_rorp and src_rorp.isdir()
                or dest_rorp and dest_rorp.isdir()):
            return  # neither is directory
        assert self.parent_list or index == (), (
            "Index '{idx}' must be empty if no parent in list".format(
                idx=index))
        if self.parent_list:
            last_parent_index = self.parent_list[-1][0]
            lp_index, li = len(last_parent_index), len(index)
            assert li <= lp_index + 1, (
                "The length of the current index '{idx}' can't be more than "
                "one greater than the last parent's '{pidx}'.".format(
                    idx=index, pidx=last_parent_index))
            # li == lp_index + 1, means we've descended into previous parent
            # if li <= lp_index, we're in a new directory but it must have
            # a common path up to (li - 1) with the last parent
            if li <= lp_index:
                assert last_parent_index[:li - 1] == index[:-1], (
                    "Current index '{idx}' and last parent index '{pidx}' "
                    "must have a common path up to {lvl} levels.".format(
                        idx=index, pidx=last_parent_index, lvl=(li - 1)))
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
        if Globals.file_statistics:
            statistics.FileStats.update(source_rorp, dest_rorp, changed, inc)

    def _reset_dir_perms(self, current_index):
        """Reset the permissions of directories when we have left them"""
        dir_rp, perms = self.dir_perms_list[-1]
        dir_index = dir_rp.index
        if (current_index > dir_index
                and current_index[:len(dir_index)] != dir_index):
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
                conn=basis_root_rp.conn, lconn=Globals.local_connection))
        self.statfileobj = (statistics.get_active_statfileobj()
                            or statistics.StatFileObj())
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
            self.CCPP.get_rorps(index), self.basis_root_rp)
        assert not mirror_rp.isdir(), (
            "Mirror path '{rp}' points to a directory.".format(rp=mirror_rp))
        tf = mirror_rp.get_temp_rpath(sibling=True)
        result = self._patch_to_temp(mirror_rp, diff_rorp, tf)
        if result == self.UNCHANGED:
            rpath.copy_attribs(diff_rorp, mirror_rp)
            self.CCPP.flag_success(index)
        elif result:
            if tf.lstat():
                if robust.check_common_error(self.error_handler, rpath.rename,
                                             (tf, mirror_rp)) is None:
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
            self.CCPP.get_rorps(index), self.basis_root_rp)
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
            assert self.base_rp.isdir(), (
                "Base directory '{rp}' isn't a directory.".format(
                    rp=self.base_rp))
            rpath.copy_attribs(self.dir_update, self.base_rp)

            if (Globals.process_uid != 0
                    and self.dir_update.getperms() % 0o1000 < 0o700):
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
            self._patch_hardlink_to_temp(diff_rorp, new)
        elif diff_rorp.get_attached_filetype() == 'snapshot':
            result = self._patch_snapshot_to_temp(diff_rorp, new)
            if result == self.FAILED or result == self.SPECIAL:
                return result
        else:
            result = self._patch_diff_to_temp(basis_rp, diff_rorp, new)
            if result == self.FAILED or result == self.UNCHANGED:
                return result
        if new.lstat():
            if diff_rorp.isflaglinked():
                if Globals.eas_write:
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
                    new.data['ea'] = diff_rorp.get_ea()
            else:
                rpath.copy_attribs(diff_rorp, new)
        return self._matches_cached_rorp(diff_rorp, new)

    def _patch_hardlink_to_temp(self, diff_rorp, new):
        """Hardlink diff_rorp to temp, update hash if necessary"""
        map_hardlinks.link_rp(diff_rorp, new, self.basis_root_rp)
        self.CCPP.update_hardlink_hash(diff_rorp)

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

        report = robust.check_common_error(self.error_handler, rpath.copy,
                                           (diff_rorp, new))
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
        assert diff_rorp.get_attached_filetype() == 'diff', (
            "Type attached to '{rp}' isn't '{exp}' but '{att}'.".format(
                rp=diff_rorp, exp="diff",
                att=diff_rorp.get_attached_filetype()))
        report = robust.check_common_error(
            self.error_handler, Rdiff.patch_local, (basis_rp, diff_rorp, new))
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
            "UpdateError", diff_rorp, "Updated mirror "
            "temp file '{tf}' does not match source".format(tf=new_rp))
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
        assert diff_rorp.get_attached_filetype() == 'snapshot', (
            "Type attached to '{rp}' isn't '{exp}' but '{att}'.".format(
                rp=diff_rorp, exp="snapshot",
                att=diff_rorp.get_attached_filetype()))
        self.dir_replacement = base_rp.get_temp_rpath(sibling=True)
        if not self._patch_to_temp(None, diff_rorp, self.dir_replacement):
            if self.dir_replacement.lstat():
                self.dir_replacement.delete()
            # Was an error, so now restore original directory
            rpath.copy_with_attribs(
                self.CCPP.get_mirror_rorp(diff_rorp.index),
                self.dir_replacement)
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
            self.CCPP.get_rorps(index), self.basis_root_rp, self.inc_root_rp)
        tf = mirror_rp.get_temp_rpath(sibling=True)
        result = self._patch_to_temp(mirror_rp, diff_rorp, tf)
        if result == self.UNCHANGED:
            rpath.copy_attribs(diff_rorp, mirror_rp)
            self.CCPP.flag_success(index)
        elif result:
            inc = robust.check_common_error(
                self.error_handler, increment.Increment,
                (tf, mirror_rp, inc_prefix, self.previous_time))
            if inc is not None and not isinstance(inc, int):
                self.CCPP.set_inc(index, inc)
                if inc.isreg():
                    inc.fsync_with_dir()  # Write inc before rp changed
                if tf.lstat():
                    if robust.check_common_error(self.error_handler,
                                                 rpath.rename,
                                                 (tf, mirror_rp)) is None:
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
            self.CCPP.get_rorps(index), self.basis_root_rp, self.inc_root_rp)
        self.base_rp.setdata()
        assert diff_rorp.isdir() or self.base_rp.isdir(), (
            "Either diff '{ipath!r}' or base '{bpath!r}' "
            "must be a directory".format(ipath=diff_rorp, bpath=self.base_rp))
        if diff_rorp.isdir():
            inc = increment.Increment(diff_rorp, self.base_rp,
                                      inc_prefix, self.previous_time)
            if inc and inc.isreg():
                inc.fsync_with_dir()  # must write inc before rp changed
            self.base_rp.setdata()  # in case written by increment above
            self._prepare_dir(diff_rorp, self.base_rp)
        elif self._set_dir_replacement(diff_rorp, self.base_rp):
            inc = increment.Increment(self.dir_replacement, self.base_rp,
                                      inc_prefix, self.previous_time)
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
        rf = map_longnames.update_rf(self._get_rf(index, mir_rorp), mir_rorp,
                                     self.root_rf.mirror_rp, _RestoreFile)
        if not rf:
            log.Log(
                "Unable to retrieve data for file {fi}! The cause is "
                "probably data loss from the backup repository".format(
                    fi=(index and "/".join(index) or '.')), log.WARNING)
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
                if (index[:-1] == rf.index[:-1]
                        or not self._add_rfs(index, mir_rorp)):
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
            self.root_rf.inc_rp.new_index(parent_index), [])
        new_rfs = list(temp_rf.yield_sub_rfs())
        if not new_rfs:
            return 0
        self.rf_list[0:0] = new_rfs
        return 1

    def _debug_list_rfs_in_cache(self, index):
        """Used for debugging, return indices of cache rfs for printing"""
        s1 = "-------- Cached RF for %s -------" % (index, )
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
            self.index, self.mirror_rp, self.inc_rp,
            list(map(str, self.inc_list)), list(map(str, self.relevant_incs)))

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
        self.mirror_rp.inc_type = b'snapshot'
        self.mirror_rp.inc_compressed = 0
        if (not self.inc_list or self._restore_time >= self._mirror_time):
            self.relevant_incs = [self.mirror_rp]
            return

        newer_incs = self.get_newer_incs()
        i = 0
        while (i < len(newer_incs)):
            # Only diff type increments require later versions
            if newer_incs[i].getinctype() != b"diff":
                break
            i = i + 1
        self.relevant_incs = newer_incs[:i + 1]
        if (not self.relevant_incs
                or self.relevant_incs[-1].getinctype() == b"diff"):
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
        if last_inc.getinctype() == b'missing':
            return rpath.RORPath(self.index)

        rorp = last_inc.getRORPath()
        rorp.index = self.index
        if last_inc.getinctype() == b'dir':
            rorp.data['type'] = 'dir'
        return rorp

    def get_restore_fp(self):
        """Return file object of restored data"""

        def get_fp():
            current_fp = self._get_first_fp()
            for inc_diff in self.relevant_incs[1:]:
                log.Log("Applying patch file {pf}".format(pf=inc_diff),
                        log.DEBUG)
                assert inc_diff.getinctype() == b'diff', (
                    "Path '{irp!r}' must be of type 'diff'.".format(
                        irp=inc_diff))
                delta_fp = inc_diff.open("rb", inc_diff.isinccompressed())
                try:
                    new_fp = tempfile.TemporaryFile()
                    Rdiff.write_patched_fp(current_fp, delta_fp, new_fp)
                    new_fp.seek(0)
                except OSError:
                    tmpdir = tempfile.gettempdir()
                    log.Log("Error while writing to temporary directory "
                            "{td}".format(td=tmpdir), log.ERROR)
                    raise
                current_fp = new_fp
            return current_fp

        def error_handler(exc):
            log.Log("Failed reading file {fi}, substituting empty file.".format(
                fi=self.mirror_rp), log.WARNING)
            return io.BytesIO(b'')

        if not self.relevant_incs[-1].isreg():
            log.Log("""Could not restore file {rf}!

A regular file was indicated by the metadata, but could not be
constructed from existing increments because last increment had type {it}.
Instead of the actual file's data, an empty length file will be created.
This error is probably caused by data loss in the
rdiff-backup destination directory, or a bug in rdiff-backup""".format(
                rf=self.mirror_rp,
                it=self.relevant_incs[-1].lstat()), log.WARNING)
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
                if rp.isincfile() and rp.getinctype() != b'data':
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
                assert rp.isincfile(), (
                    "Path '{mrp}' must be an increment file.".format(mrp=rp))
                inc_list.append(rp)
            return inc_list

        items = get_inc_pairs()
        items.sort()  # Sorting on basis of basename now
        for (basename, inc_filenames) in items:
            sub_inc_rpath = inc_rpath.append(basename)
            yield rorpiter.IndexedTuple(
                sub_inc_rpath.index,
                (sub_inc_rpath, inc_filenames2incrps(inc_filenames)))

    def _get_first_fp(self):
        """Return first file object from relevant inc list"""
        first_inc = self.relevant_incs[0]
        assert first_inc.getinctype() == b'snapshot', (
            "Path '{srp}' must be of type 'snapshot'.".format(
                srp=first_inc))
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
            log.Log("Error while writing to temporary directory "
                    "{td}".format(td=tmpdir), log.ERROR)
            raise
        return current_fp

    def _yield_mirrorrps(self, mirrorrp):
        """Yield mirrorrps underneath given mirrorrp"""
        assert mirrorrp.isdir(), (
            "Mirror path '{mrp}' must be a directory.".format(mrp=mirrorrp))
        for filename in robust.listrp(mirrorrp):
            rp = mirrorrp.append(filename)
            if rp.index != (b'rdiff-backup-data', ):
                yield rp

    def _debug_relevant_incs_string(self):
        """Return printable string of relevant incs, used for debugging"""
        inc_header = ["---- Relevant incs for %s" % ("/".join(self.index), )]
        inc_header.extend([
            "{itp} {ils} {irp}".format(
                itp=inc.getinctype(), ils=inc.lstat(), irp=inc)
            for inc in self.relevant_incs
        ])
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
            if index[:len(old_index)] > old_index:
                old_rp.chmod(old_perms)
            else:
                break
            del self.open_index_list[0]

    def _add_chmod_new(self, old_index, index):
        """Change permissions of directories between old_index and index"""
        for rp in self._get_new_rp_list(old_index, index):
            if ((rp.isreg() and not rp.readable())
                    or (rp.isdir() and not (rp.executable() and rp.readable()))):
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
        return ((self.metadata_rorp and self.metadata_rorp.isdir())
                or (self.mirror_rp and self.mirror_rp.isdir()))


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
            log.Log("Regressing file {fi}".format(fi=rf.metadata_rorp),
                    log.INFO)
            if rf.metadata_rorp.isreg():
                self._restore_orig_regfile(rf)
            else:
                if rf.mirror_rp.lstat():
                    rf.mirror_rp.delete()
                if rf.metadata_rorp.isspecial():
                    robust.check_common_error(None, rpath.copy_with_attribs,
                                              (rf.metadata_rorp, rf.mirror_rp))
                else:
                    rpath.copy_with_attribs(rf.metadata_rorp, rf.mirror_rp)
        if rf.regress_inc:
            log.Log("Deleting increment {ic}".format(ic=rf.regress_inc),
                    log.INFO)
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
        if rf.metadata_rorp.isdir():
            if rf.mirror_rp.isdir():
                rf.mirror_rp.setdata()
                if not rf.metadata_rorp.equal_loose(rf.mirror_rp):
                    log.Log("Regressing attributes of path {pa}".format(pa=rf),
                            log.INFO)
                    rpath.copy_attribs(rf.metadata_rorp, rf.mirror_rp)
            else:
                rf.mirror_rp.delete()
                log.Log("Regressing file {fi}".format(fi=rf.mirror_rp),
                        log.INFO)
                rpath.copy_with_attribs(rf.metadata_rorp, rf.mirror_rp)
        else:  # replacing a dir with some other kind of file
            assert rf.mirror_rp.isdir(), (
                "Mirror '{mrp!r}' can only be a directory.".format(
                    mrp=rf.mirror_rp))
            log.Log("Replacing directory {di}".format(di=rf), log.INFO)
            if rf.metadata_rorp.isreg():
                self._restore_orig_regfile(rf)
            else:
                rf.mirror_rp.delete()
                rpath.copy_with_attribs(rf.metadata_rorp, rf.mirror_rp)
        if rf.regress_inc:
            log.Log("Deleting increment {ic}".format(ic=rf), log.INFO)
            rf.regress_inc.delete()

    def _restore_orig_regfile(self, rf):
        """
        Restore original regular file

        This is the trickiest case for avoiding information loss,
        because we don't want to delete the increment before the
        mirror is fully written.
        """
        assert rf.metadata_rorp.isreg(), (
            "Metadata path '{mp}' can only be regular file.".format(
                mp=rf.metadata_rorp))
        if rf.mirror_rp.isreg():
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
            rf.mirror_rp.get_parent_rp().fsync(
            )  # force move before inc delete
