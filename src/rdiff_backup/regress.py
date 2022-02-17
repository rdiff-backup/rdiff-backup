# Copyright 2002, 2005 Ben Escoto
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
"""Code for reverting the rdiff-backup directory to prev state

This module is used after an aborted session, and the rdiff-backup
destination directory may be in-between states.  In this situation we
need to bring back the directory as it was after the last successful
backup.  The basic strategy is to restore all the attributes from the
metadata file (which we assume is intact) and delete the extra
increments.  For regular files we examine the mirror file and use the
increment file to get the old data if the mirror file is out of date.

Currently this does not recover hard links.  This may make the
regressed directory take up more disk space, but hard links can still
be recovered.

"""

import re
import os
from rdiff_backup import Globals, restore, log, rorpiter, rpath, C, \
    Time, robust, longname
from rdiffbackup import meta_mgr

# regress_time should be set to the time we want to regress back to
# (usually the time of the last successful backup)
regress_time = None

# This should be set to the latest unsuccessful backup time
unsuccessful_backup_time = None


class RegressFile(restore.RestoreFile):
    """Like RestoreFile but with metadata

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


class RegressITRB(rorpiter.ITRBranch):
    """Turn back state of dest directory (use with IterTreeReducer)

    The arguments to the ITR will be RegressFiles.  There are two main
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
        self.rf = None  # will hold RegressFile applying to a directory

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
        """Restore original regular file

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


# @API(check_pids, 200, 200)
def check_pids(curmir_incs):
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
                process = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, 0,
                                               pid)
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
        # FIXME differentiate between don't know and know and handle err.errno == errno.EPERM:
        # EPERM clearly means there's a process to deny access to with OSError
        if pid is not None and pid_running(pid):
            log.Log.FatalError(
                """It appears that a previous rdiff-backup session with process
id {pi} is still running.  If two different rdiff-backup processes write
the same repository simultaneously, data corruption will probably
result.  To proceed with regress anyway, rerun rdiff-backup with the
--force option""".format(pi=pid))


# @API(Regress, 200, 200)
def Regress(mirror_rp):
    """Bring mirror and inc directory back to regress_to_time

    Also affects the rdiff-backup-data directory, so Globals.rbdir
    should be set.  Regress should only work one step at a time
    (i.e. don't "regress" through two separate backup sets.  This
    function should be run locally to the rdiff-backup-data directory.

    """
    inc_rpath = Globals.rbdir.append_path(b"increments")
    assert mirror_rp.index == () and inc_rpath.index == (), (
        "Mirror and increment paths must have an empty index")
    assert mirror_rp.isdir() and inc_rpath.isdir(), (
        "Mirror and increments paths must be directories")
    assert mirror_rp.conn is inc_rpath.conn is Globals.local_connection, (
        "Regress must happen locally.")
    meta_manager, former_current_mirror_rp = _set_regress_time()
    _set_restore_times()
    _regress_rbdir(meta_manager)
    ITR = rorpiter.IterTreeReducer(RegressITRB, [])
    for rf in _iterate_meta_rfs(mirror_rp, inc_rpath):
        ITR(rf.index, rf)
    ITR.finish_processing()
    if former_current_mirror_rp:
        if Globals.do_fsync:
            C.sync()  # Sync first, since we are marking dest dir as good now
        former_current_mirror_rp.delete()


def _set_regress_time():
    """Set global regress_time to previous successful backup

    If there are two current_mirror increments, then the last one
    corresponds to a backup session that failed.

    """
    global regress_time, unsuccessful_backup_time
    meta_manager = meta_mgr.get_meta_manager(True)
    curmir_incs = meta_manager.sorted_prefix_inclist(b'current_mirror')
    assert len(curmir_incs) == 2, (
        "Found {ilen} current_mirror flags, expected 2".format(
            ilen=len(curmir_incs)))
    mirror_rp_to_delete = curmir_incs[0]
    regress_time = curmir_incs[1].getinctime()
    unsuccessful_backup_time = mirror_rp_to_delete.getinctime()
    log.Log("Regressing to date/time {dt}".format(
        dt=Time.timetopretty(regress_time)), log.NOTE)
    return meta_manager, mirror_rp_to_delete


def _set_restore_times():
    """Set _rest_time and _mirror_time in the restore module

    _rest_time (restore time) corresponds to the last successful
    backup time.  _mirror_time is the unsuccessful backup time.

    """
    restore.MirrorStruct._mirror_time = unsuccessful_backup_time
    restore.MirrorStruct._rest_time = regress_time


def _regress_rbdir(meta_manager):
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
    for old_rp in meta_manager.timerpmap[regress_time]:
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
        meta_manager.recreate_attr(regress_time)

    for new_rp in meta_manager.timerpmap[unsuccessful_backup_time]:
        if new_rp.getincbase_bname() != b'current_mirror':
            log.Log("Deleting old diff {od}".format(od=new_rp), log.INFO)
            new_rp.delete()

    for rp in meta_diffs:
        rp.delete()


def _iterate_raw_rfs(mirror_rp, inc_rp):
    """Iterate all RegressFile objects in mirror/inc directory

    Also changes permissions of unreadable files.  We don't have to
    change them back later because regress will do that for us.

    """
    root_rf = RegressFile(mirror_rp, inc_rp,
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


def _iterate_meta_rfs(mirror_rp, inc_rp):
    """Yield RegressFile objects with extra metadata information added

    Each RegressFile will have an extra object variable .metadata_rorp
    which will contain the metadata attributes of the mirror file at
    regress_time.

    """
    raw_rfs = _iterate_raw_rfs(mirror_rp, inc_rp)
    collated = rorpiter.Collate2Iters(raw_rfs, _yield_metadata())
    for raw_rf, metadata_rorp in collated:
        raw_rf = longname.update_rf(raw_rf, metadata_rorp, mirror_rp,
                                    RegressFile)
        if not raw_rf:
            log.Log("Warning, metadata file has entry for path {pa}, "
                    "but there are no associated files.".format(
                        pa=metadata_rorp), log.WARNING)
            continue
        raw_rf.set_metadata_rorp(metadata_rorp)
        yield raw_rf


def _yield_metadata():
    """Iterate rorps from metadata file, if any are available"""
    meta_manager = meta_mgr.get_meta_manager(True)
    metadata_iter = meta_manager.get_metas_at_time(regress_time)
    if metadata_iter:
        return metadata_iter
    log.Log.FatalError("No metadata for time {pt} ({rt}) found, "
                       "cannot regress".format(
                           pt=Time.timetopretty(regress_time), rt=regress_time))
