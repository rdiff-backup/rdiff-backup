# Copyright 2002, 2003, 2004, 2005 Ben Escoto
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
"""Start (and end) here - read arguments, set global settings, etc."""

import getopt
import sys
import os
import io
import tempfile
import time
import errno
import platform
from .log import Log, LoggerError, ErrorLog
from . import (
    Globals, Time, SetConnections, robust, rpath,
    manage, backup, connection, restore, FilenameMapping,
    Security, C, statistics, compare
)

_action = None
_create_full_path = None
_remote_cmd, _remote_schema = None, None
_force = None
_select_opts = []
_select_files = []
_user_mapping_filename, _group_mapping_filename, _preserve_numerical_ids = None, None, None

# These are global because they are set while we are trying to figure
# whether to restore or to backup
restore_root, _restore_index, _restore_root_set = None, None, 0

# Those global variables are listed here to make the list complete
_restore_timestr, _incdir, _prevtime = None, None, None
_remove_older_than_string = None


def _parse_cmdlineoptions(arglist):  # noqa: C901
    """Parse argument list and set global preferences"""
    global _args, _action, _create_full_path, _force, _restore_timestr
    global _remote_cmd, _remote_schema, _remove_older_than_string
    global _user_mapping_filename, _group_mapping_filename, \
        _preserve_numerical_ids

    def sel_fl(filename):
        """Helper function for including/excluding filelists below"""
        try:
            return open(filename, "rb")  # files match paths hence bytes/bin
        except IOError:
            Log.FatalError("Error opening file %s" % filename)

    def normalize_path(path):
        """Used below to normalize the security paths before setting"""
        return rpath.RPath(Globals.local_connection, path).normalize().path

    try:
        optlist, _args = getopt.getopt(arglist, "blr:sv:V", [
            "allow-duplicate-timestamps",
            "backup-mode", "calculate-average", "carbonfile",
            "check-destination-dir", "compare", "compare-at-time=",
            "compare-hash", "compare-hash-at-time=", "compare-full",
            "compare-full-at-time=", "create-full-path", "current-time=",
            "exclude=", "exclude-device-files", "exclude-fifos",
            "exclude-filelist=", "exclude-symbolic-links", "exclude-sockets",
            "exclude-filelist-stdin", "exclude-globbing-filelist=",
            "exclude-globbing-filelist-stdin", "exclude-mirror=",
            "exclude-other-filesystems", "exclude-regexp=",
            "exclude-if-present=", "exclude-special-files", "force",
            "group-mapping-file=", "include=", "include-filelist=",
            "include-filelist-stdin", "include-globbing-filelist=",
            "include-globbing-filelist-stdin", "include-regexp=",
            "include-special-files", "include-symbolic-links", "list-at-time=",
            "list-changed-since=", "list-increments", "list-increment-sizes",
            "never-drop-acls", "max-file-size=", "min-file-size=", "no-acls",
            "no-carbonfile", "no-compare-inode", "no-compression",
            "no-compression-regexp=", "no-eas", "no-file-statistics",
            "no-hard-links", "null-separator", "override-chars-to-quote=",
            "parsable-output", "preserve-numerical-ids", "print-statistics",
            "remote-cmd=", "remote-schema=", "remote-tempdir=",
            "remove-older-than=", "restore-as-of=", "restrict=",
            "restrict-read-only=", "restrict-update-only=", "server",
            "ssh-no-compression", "tempdir=", "terminal-verbosity=",
            "test-server", "use-compatible-timestamps", "user-mapping-file=",
            "verbosity=", "verify", "verify-at-time=", "version", "no-fsync"
        ])
    except getopt.error as e:
        _commandline_error("Bad commandline options: " + str(e))

    for opt, arg in optlist:
        if opt == "-b" or opt == "--backup-mode":
            _action = "backup"
        elif opt == "--calculate-average":
            _action = "calculate-average"
        elif opt == "--carbonfile":
            Globals.set("carbonfile_active", 1)
        elif opt == "--check-destination-dir":
            _action = "check-destination-dir"
        elif opt in ("--compare", "--compare-at-time", "--compare-hash",
                     "--compare-hash-at-time", "--compare-full",
                     "--compare-full-at-time"):
            if opt[-8:] == "-at-time":
                _restore_timestr, opt = arg, opt[:-8]
            else:
                _restore_timestr = "now"
            _action = opt[2:]
        elif opt == "--create-full-path":
            _create_full_path = 1
        elif opt == "--current-time":
            Globals.set_integer('current_time', arg)
        elif (opt == "--exclude" or opt == "--exclude-device-files"
              or opt == "--exclude-fifos"
              or opt == "--exclude-other-filesystems"
              or opt == "--exclude-regexp" or opt == "--exclude-if-present"
              or opt == "--exclude-special-files" or opt == "--exclude-sockets"
              or opt == "--exclude-symbolic-links"):
            _select_opts.append((opt, arg))
        elif opt == "--exclude-filelist":
            _select_opts.append((opt, arg))
            _select_files.append(sel_fl(arg))
        elif opt == "--exclude-filelist-stdin":
            _select_opts.append(("--exclude-filelist", "standard input"))
            _select_files.append(sys.stdin.buffer)
        elif opt == "--exclude-globbing-filelist":
            _select_opts.append((opt, arg))
            _select_files.append(sel_fl(arg))
        elif opt == "--exclude-globbing-filelist-stdin":
            _select_opts.append(("--exclude-globbing-filelist",
                                "standard input"))
            _select_files.append(sys.stdin.buffer)
        elif opt == "--force":
            _force = 1
        elif opt == "--group-mapping-file":
            _group_mapping_filename = os.fsencode(arg)
        elif (opt == "--include" or opt == "--include-special-files"
              or opt == "--include-symbolic-links"):
            _select_opts.append((opt, arg))
        elif opt == "--include-filelist":
            _select_opts.append((opt, arg))
            _select_files.append(sel_fl(arg))
        elif opt == "--include-filelist-stdin":
            _select_opts.append(("--include-filelist", "standard input"))
            _select_files.append(sys.stdin.buffer)
        elif opt == "--include-globbing-filelist":
            _select_opts.append((opt, arg))
            _select_files.append(sel_fl(arg))
        elif opt == "--include-globbing-filelist-stdin":
            _select_opts.append(("--include-globbing-filelist",
                                "standard input"))
            _select_files.append(sys.stdin.buffer)
        elif opt == "--include-regexp":
            _select_opts.append((opt, arg))
        elif opt == "--list-at-time":
            _restore_timestr, _action = arg, "list-at-time"
        elif opt == "--list-changed-since":
            _restore_timestr, _action = arg, "list-changed-since"
        elif opt == "-l" or opt == "--list-increments":
            _action = "list-increments"
        elif opt == '--list-increment-sizes':
            _action = 'list-increment-sizes'
        elif opt == "--max-file-size":
            _select_opts.append((opt, arg))
        elif opt == "--min-file-size":
            _select_opts.append((opt, arg))
        elif opt == "--never-drop-acls":
            Globals.set("never_drop_acls", 1)
        elif opt == "--no-acls":
            Globals.set("acls_active", 0)
            Globals.set("win_acls_active", 0)
        elif opt == "--no-carbonfile":
            Globals.set("carbonfile_active", 0)
        elif opt == "--no-compare-inode":
            Globals.set("compare_inode", 0)
        elif opt == "--no-compression":
            Globals.set("compression", None)
        elif opt == "--no-compression-regexp":
            Globals.set("no_compression_regexp_string", os.fsencode(arg))
        elif opt == "--no-eas":
            Globals.set("eas_active", 0)
        elif opt == "--no-file-statistics":
            Globals.set('file_statistics', 0)
        elif opt == "--no-hard-links":
            Globals.set('preserve_hardlinks', 0)
        elif opt == "--null-separator":
            Globals.set("null_separator", 1)
        elif opt == "--override-chars-to-quote":
            Globals.set('chars_to_quote', os.fsencode(arg))
        elif opt == "--parsable-output":
            Globals.set('parsable_output', 1)
        elif opt == "--preserve-numerical-ids":
            _preserve_numerical_ids = 1
        elif opt == "--print-statistics":
            Globals.set('print_statistics', 1)
        elif opt == "-r" or opt == "--restore-as-of":
            _restore_timestr, _action = arg, "restore-as-of"
        elif opt == "--remote-cmd":
            _remote_cmd = os.fsencode(arg)
        elif opt == "--remote-schema":
            _remote_schema = os.fsencode(arg)
        elif opt == "--remote-tempdir":
            Globals.remote_tempdir = os.fsencode(arg)
        elif opt == "--remove-older-than":
            _remove_older_than_string = arg
            _action = "remove-older-than"
        elif opt == "--no-resource-forks":
            Globals.set('resource_forks_active', 0)
        elif opt == "--restrict":
            Globals.restrict_path = normalize_path(arg)
        elif opt == "--restrict-read-only":
            Globals.security_level = "read-only"
            Globals.restrict_path = normalize_path(arg)
        elif opt == "--restrict-update-only":
            Globals.security_level = "update-only"
            Globals.restrict_path = normalize_path(arg)
        elif opt == "-s" or opt == "--server":
            _action = "server"
            Globals.server = 1
        elif opt == "--ssh-no-compression":
            Globals.set('ssh_compression', None)
        elif opt == "--tempdir":
            if (not os.path.isdir(arg)):
                Log.FatalError("Temporary directory '%s' doesn't exist." % arg)
            tempfile.tempdir = os.fsencode(arg)
        elif opt == "--terminal-verbosity":
            Log.setterm_verbosity(arg)
        elif opt == "--test-server":
            _action = "test-server"
        elif opt == "--use-compatible-timestamps":
            Globals.set("use_compatible_timestamps", 1)
        elif opt == "--allow-duplicate-timestamps":
            Globals.set("allow_duplicate_timestamps", True)
        elif opt == "--user-mapping-file":
            _user_mapping_filename = os.fsencode(arg)
        elif opt == "-v" or opt == "--verbosity":
            Log.setverbosity(arg)
        elif opt == "--verify":
            _action, _restore_timestr = "verify", "now"
        elif opt == "--verify-at-time":
            _action, _restore_timestr = "verify", arg
        elif opt == "-V" or opt == "--version":
            print("rdiff-backup " + Globals.version)
            sys.exit(0)
        elif opt == "--no-fsync":
            Globals.do_fsync = False
        else:
            Log.FatalError("Unknown option %s" % opt)
    Log("Using rdiff-backup version %s" % (Globals.version), 4)
    Log("\twith %s %s version %s" % (
        sys.implementation.name,
        sys.executable,
        platform.python_version()), 4)
    Log("\ton %s, fs encoding %s" % (platform.platform(), sys.getfilesystemencoding()), 4)


def _check_action():
    """Check to make sure _action is compatible with _args"""
    global _action
    arg_action_dict = {
        0: ['server'],
        1: [
            'list-increments', 'list-increment-sizes', 'remove-older-than',
            'list-at-time', 'list-changed-since', 'check-destination-dir',
            'verify'
        ],
        2: [
            'backup', 'restore', 'restore-as-of', 'compare', 'compare-hash',
            'compare-full'
        ]
    }
    args_len = len(_args)
    if args_len == 0 and _action not in arg_action_dict[args_len]:
        _commandline_error("No arguments given")
    elif not _action:
        if args_len == 2:
            pass  # Will determine restore or backup later
        else:
            _commandline_error("Switches missing or wrong number of arguments")
    elif _action == 'test-server' or _action == 'calculate-average':
        pass  # these two take any number of args
    elif args_len > 2 or _action not in arg_action_dict[args_len]:
        _commandline_error("Wrong number of arguments given.")


def _final_set_action(rps):
    """If no action set, decide between backup and restore at this point"""
    global _action
    if _action:
        return
    assert len(rps) == 2, rps
    if restore_set_root(rps[0]):
        _action = "restore"
    else:
        _action = "backup"


def _commandline_error(message):
    Log.FatalError(
        "%s\nSee the rdiff-backup manual page for more information." % message)


def _misc_setup(rps):
    """Set default change ownership flag, umask, relay regexps"""
    os.umask(0o77)
    Time.setcurtime(Globals.current_time)
    SetConnections.UpdateGlobal("client_conn", Globals.local_connection)
    Globals.postset_regexp('no_compression_regexp',
                           Globals.no_compression_regexp_string)
    for conn in Globals.connections:
        conn.robust.install_signal_handlers()
        conn.Hardlink.initialize_dictionaries()


def _init_user_group_mapping(destination_conn):
    """Initialize user and group mapping on destination connection"""
    global _user_mapping_filename, _group_mapping_filename, \
        _preserve_numerical_ids

    def get_string_from_file(filename):
        if not filename:
            return None
        rp = rpath.RPath(Globals.local_connection, filename)
        try:
            return rp.get_string()
        except OSError as e:
            Log.FatalError(
                "Error '%s' reading mapping file '%s'" % (str(e), filename))

    user_mapping_string = get_string_from_file(_user_mapping_filename)
    destination_conn.user_group.init_user_mapping(user_mapping_string,
                                                  _preserve_numerical_ids)
    group_mapping_string = get_string_from_file(_group_mapping_filename)
    destination_conn.user_group.init_group_mapping(group_mapping_string,
                                                   _preserve_numerical_ids)


def _take_action(rps):
    """Do whatever action says"""
    if _action == "server":
        connection.PipeConnection(sys.stdin.buffer, sys.stdout.buffer).Server()
        sys.exit(0)
    elif _action == "test-server":
        action_result = SetConnections.TestConnections(rps)
    elif _action == "backup":
        action_result = _action_backup(rps[0], rps[1])
    elif _action == "calculate-average":
        action_result = _action_calculate_average(rps)
    elif _action == "check-destination-dir":
        action_result = _action_check_dest(rps[0])
    elif _action.startswith("compare"):
        action_result = _action_compare(_action, rps[0], rps[1])
    elif _action == "list-at-time":
        action_result = _action_list_at_time(rps[0])
    elif _action == "list-changed-since":
        action_result = _action_list_changed_since(rps[0])
    elif _action == "list-increments":
        action_result = _action_list_increments(rps[0])
    elif _action == 'list-increment-sizes':
        action_result = _action_list_increment_sizes(rps[0])
    elif _action == "remove-older-than":
        action_result = _action_remove_older_than(rps[0])
    elif _action == "restore":
        action_result = _action_restore(*rps)
    elif _action == "restore-as-of":
        action_result = _action_restore(rps[0], rps[1], 1)
    elif _action == "verify":
        action_result = _action_verify(rps[0])
    else:
        raise AssertionError("Unknown action " + _action)
    return action_result


def _cleanup():
    """Do any last minute cleaning before exiting"""
    Log("Cleaning up", 6)
    if ErrorLog.isopen():
        ErrorLog.close()
    Log.close_logfile()
    if not Globals.server:
        SetConnections.CloseConnections()


def error_check_Main(arglist):
    """Run Main on arglist, suppressing stack trace for routine errors"""
    try:
        _Main(arglist)
    except SystemExit:
        raise
    except (Exception, KeyboardInterrupt) as exc:
        errmsg = robust.is_routine_fatal(exc)
        if errmsg:
            Log.exception(2, 6)
            Log.FatalError(errmsg)
        else:
            Log.exception(2, 2)
            raise


def _Main(arglist):
    """Start everything up!"""
    _parse_cmdlineoptions(arglist)
    _check_action()
    cmdpairs = SetConnections.get_cmd_pairs(_args, _remote_schema, _remote_cmd)
    Security.initialize(_action or "mirror", cmdpairs)
    rps = list(map(SetConnections.cmdpair2rp, cmdpairs))
    _final_set_action(rps)
    _misc_setup(rps)
    return_val = _take_action(rps)
    _cleanup()
    if isinstance(return_val, int):
        sys.exit(return_val)
    else:
        sys.exit(0)


def _action_backup(rpin, rpout):
    """Backup, possibly incrementally, src_path to dest_path."""
    global _incdir
    SetConnections.BackupInitConnections(rpin.conn, rpout.conn)
    _backup_check_dirs(rpin, rpout)
    _backup_set_rbdir(rpin, rpout)
    rpout.conn.fs_abilities.backup_set_globals(rpin, _force)
    if Globals.chars_to_quote:
        rpout = _backup_quoted_rpaths(rpout)
    _init_user_group_mapping(rpout.conn)
    _backup_final_init(rpout)
    _backup_set_select(rpin)
    _backup_warn_if_infinite_regress(rpin, rpout)
    if _prevtime:
        Time.setprevtime(_prevtime)
        rpout.conn.Main.backup_touch_curmirror_local(rpin, rpout)
        backup.Mirror_and_increment(rpin, rpout, _incdir)
        rpout.conn.Main.backup_remove_curmirror_local()
    else:
        backup.Mirror(rpin, rpout)
        rpout.conn.Main.backup_touch_curmirror_local(rpin, rpout)
    rpout.conn.Main.backup_close_statistics(time.time())


def _backup_quoted_rpaths(rpout):
    """Get QuotedRPath versions of important RPaths.  Return rpout"""
    global _incdir
    SetConnections.UpdateGlobal('rbdir',
                                FilenameMapping.get_quotedrpath(Globals.rbdir))
    _incdir = FilenameMapping.get_quotedrpath(_incdir)
    return FilenameMapping.get_quotedrpath(rpout)


def _backup_set_select(rpin):
    """Create Select objects on source connection"""
    if rpin.conn.os.name == 'nt':
        Log("Symbolic links excluded by default on Windows", 4)
        _select_opts.append(("--exclude-symbolic-links", None))
    rpin.conn.backup.SourceStruct.set_source_select(rpin, _select_opts,
                                                    *_select_files)


def _backup_check_dirs(rpin, rpout):
    """Make sure in and out dirs exist and are directories"""
    if rpout.lstat() and not rpout.isdir():
        if not _force:
            Log.FatalError("Destination %s exists and is not a "
                           "directory" % rpout.get_safepath())
        else:
            Log("Deleting %s" % rpout.get_safepath(), 3)
            rpout.delete()
    if not rpout.lstat():
        try:
            if _create_full_path:
                rpout.makedirs()
            else:
                rpout.mkdir()
        except os.error:
            Log.FatalError(
                "Unable to create directory %s" % rpout.get_safepath())

    if not rpin.lstat():
        Log.FatalError(
            "Source directory %s does not exist" % rpin.get_safepath())
    elif not rpin.isdir():
        Log.FatalError("Source %s is not a directory" % rpin.get_safepath())
    Globals.rbdir = rpout.append_path(b"rdiff-backup-data")


def _check_failed_initial_backup():
    """Returns true if it looks like initial backup failed."""
    if Globals.rbdir.lstat():
        rbdir_files = Globals.rbdir.listdir()
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


def _fix_failed_initial_backup():
    """Clear Globals.rbdir after a failed initial backup"""
    Log("Found interrupted initial backup. Removing...", 2)
    rbdir_files = Globals.rbdir.listdir()
    # Try to delete the increments dir first
    if b'increments' in rbdir_files:
        rbdir_files.remove(b'increments')
        rp = Globals.rbdir.append(b'increments')
        try:
            rp.conn.rpath.delete_dir_no_files(rp)
        except rpath.RPathException:
            Log("Increments dir contains files.", 4)
            return
        except Security.Violation:
            Log("Server doesn't support resuming.", 2)
            return

    for file_name in rbdir_files:
        rp = Globals.rbdir.append_path(file_name)
        if not rp.isdir():  # Only remove files, not folders
            rp.delete()


def _backup_set_rbdir(rpin, rpout):
    """Initialize data dir and logging"""
    global _incdir
    try:
        _incdir = Globals.rbdir.append_path(b"increments")
    except IOError as exc:
        if exc.errno == errno.EACCES:
            print("\n")
            Log.FatalError("Could not begin backup due to\n%s" % exc)
        else:
            raise

    assert rpout.lstat(), (rpout.get_safepath(), rpout.lstat())
    if rpout.isdir() and not rpout.listdir():  # rpout is empty dir
        try:
            rpout.chmod(0o700)  # just make sure permissions aren't too lax
        except OSError:
            Log("Cannot change permissions on target directory.", 2)
    elif not Globals.rbdir.lstat() and not _force:
        Log.FatalError("""Destination directory

%s

exists, but does not look like a rdiff-backup directory.  Running
rdiff-backup like this could mess up what is currently in it.  If you
want to update or overwrite it, run rdiff-backup with the --force
option.""" % rpout.get_safepath())
    elif _check_failed_initial_backup():
        _fix_failed_initial_backup()

    if not Globals.rbdir.lstat():
        try:
            Globals.rbdir.mkdir()
        except (OSError, IOError) as exc:
            Log.FatalError("""Could not create rdiff-backup directory

%s

due to

%s

Please check that the rdiff-backup user can create files and directories in the
destination directory: %s""" % (Globals.rbdir.get_safepath(), exc,
                                rpout.get_safepath()))
    SetConnections.UpdateGlobal('rbdir', Globals.rbdir)


def _backup_warn_if_infinite_regress(rpin, rpout):
    """Warn user if destination area contained in source area"""
    # Just a few heuristics, we don't have to get every case
    if rpout.conn is not rpin.conn:
        return
    if len(rpout.path) <= len(rpin.path) + 1:
        return
    if rpout.path[:len(rpin.path) + 1] != rpin.path + b'/':
        return

    relative_rpout_comps = tuple(rpout.path[len(rpin.path) + 1:].split(b'/'))
    relative_rpout = rpin.new_index(relative_rpout_comps)  # noqa: F841
    # FIXME: this fails currently because the selection object isn't stored
    #        but an iterable, the object not being pickable.
    #        Related to issue #296
    #if not Globals.select_mirror.Select(relative_rpout):  # noqa: E265
    #    return

    Log(
        """Warning: The destination directory '%s' may be contained in the
source directory '%s'.  This could cause an infinite regress.  You
may need to use the --exclude option (which you might already have done)."""
        % (rpout.get_safepath(), rpin.get_safepath()), 2)


def _backup_get_mirrortime():
    """Return time in seconds of previous mirror, or None if cannot"""
    incbase = Globals.rbdir.append_path(b"current_mirror")
    mirror_rps = restore.get_inclist(incbase)
    assert len(mirror_rps) <= 1, \
        "Found %s current_mirror rps, expected <=1" % (len(mirror_rps),)
    if mirror_rps:
        return mirror_rps[0].getinctime()
    else:
        return 0  # is always in the past


def _backup_final_init(rpout):
    """Open the backup log and the error log, create increments dir"""
    global _prevtime, _incdir
    if Log.verbosity > 0:
        Log.open_logfile(Globals.rbdir.append("backup.log"))
    _checkdest_if_necessary(rpout)
    _prevtime = _backup_get_mirrortime()
    if _prevtime >= Time.curtime:
        Log.FatalError(
            """Time of Last backup is not in the past.  This is probably caused
by running two backups in less than a second.  Wait a second and try again.""")
    ErrorLog.open(Time.curtimestr, compress=Globals.compression)
    if not _incdir.lstat():
        _incdir.mkdir()


def backup_touch_curmirror_local(rpin, rpout):
    """Make a file like current_mirror.time.data to record time

    When doing an incremental backup, this should happen before any
    other writes, and the file should be removed after all writes.
    That way we can tell whether the previous session aborted if there
    are two current_mirror files.

    When doing the initial full backup, the file can be created after
    everything else is in place.

    """
    mirrorrp = Globals.rbdir.append(b'.'.join(
        map(os.fsencode, (b"current_mirror", Time.curtimestr, "data"))))
    Log("Writing mirror marker %s" % mirrorrp.get_safepath(), 6)
    try:
        pid = os.getpid()
    except BaseException:
        pid = "NA"
    mirrorrp.write_string("PID %s\n" % (pid, ))
    mirrorrp.fsync_with_dir()


def backup_remove_curmirror_local():
    """Remove the older of the current_mirror files.  Use at end of session"""
    assert Globals.rbdir.conn is Globals.local_connection
    curmir_incs = restore.get_inclist(Globals.rbdir.append(b"current_mirror"))
    assert len(curmir_incs) == 2
    if curmir_incs[0].getinctime() < curmir_incs[1].getinctime():
        older_inc = curmir_incs[0]
    else:
        older_inc = curmir_incs[1]
    if Globals.do_fsync:
        C.sync()  # Make sure everything is written before curmirror is removed
    older_inc.delete()


def backup_close_statistics(end_time):
    """Close out the tracking of the backup statistics.

    Moved to run at this point so that only the clock of the system on which
    rdiff-backup is run is used (set by passing in time.time() from that
    system). Use at end of session.

    """
    assert Globals.rbdir.conn is Globals.local_connection
    if Globals.print_statistics:
        statistics.print_active_stats(end_time)
    if Globals.file_statistics:
        statistics.FileStats.close()
    statistics.write_active_statfileobj(end_time)


def _action_restore(src_rp, dest_rp, restore_as_of=None):
    """Main restoring function

    Here src_rp should be the source file (either an increment or
    mirror file), dest_rp should be the target rp to be written.

    """
    if not _restore_root_set and not restore_set_root(src_rp):
        Log.FatalError("Could not find rdiff-backup repository at %s" %
                       src_rp.get_safepath())
    _restore_check_paths(src_rp, dest_rp, restore_as_of)
    try:
        dest_rp.conn.fs_abilities.restore_set_globals(dest_rp)
    except IOError as exc:
        if exc.errno == errno.EACCES:
            print("\n")
            Log.FatalError("Could not begin restore due to\n%s" % exc)
        else:
            raise
    _init_user_group_mapping(dest_rp.conn)
    src_rp = _restore_init_quoting(src_rp)
    _restore_check_backup_dir(restore_root, src_rp, restore_as_of)
    inc_rpath = Globals.rbdir.append_path(b'increments', _restore_index)
    if restore_as_of:
        try:
            time = Time.genstrtotime(_restore_timestr, rp=inc_rpath)
        except Time.TimeException as exc:
            Log.FatalError(str(exc))
    else:
        time = src_rp.getinctime()
    _restore_set_select(restore_root, dest_rp)
    _restore_start_log(src_rp, dest_rp, time)
    try:
        restore.Restore(
            restore_root.new_index(_restore_index), inc_rpath, dest_rp, time)
    except IOError as exc:
        if exc.errno == errno.EACCES:
            print("\n")
            Log.FatalError("Could not complete restore due to\n%s" % exc)
        else:
            raise
    else:
        Log("Restore finished", 4)


def _restore_init_quoting(src_rp):
    """Change rpaths into quoted versions of themselves if necessary"""
    global restore_root
    if not Globals.chars_to_quote:
        return src_rp
    for conn in Globals.connections:
        conn.FilenameMapping.set_init_quote_vals()
    restore_root = FilenameMapping.get_quotedrpath(restore_root)
    SetConnections.UpdateGlobal('rbdir',
                                FilenameMapping.get_quotedrpath(Globals.rbdir))
    return FilenameMapping.get_quotedrpath(src_rp)


def _restore_set_select(mirror_rp, target):
    """Set the selection iterator on both side from command line args

    We must set both sides because restore filtering is different from
    select filtering.  For instance, if a file is excluded it should
    not be deleted from the target directory.

    The BytesIO stuff is because filelists need to be read and then
    duplicated, because we need two copies of them now.

    """

    def fp2string(fp):
        buf = fp.read()
        assert not fp.close()
        return buf

    select_data = list(map(fp2string, _select_files))
    if _select_opts:
        mirror_rp.conn.restore.MirrorStruct.set_mirror_select(
            target, _select_opts, *list(map(io.BytesIO, select_data)))
        target.conn.restore.TargetStruct.set_target_select(
            target, _select_opts, *list(map(io.BytesIO, select_data)))


def _restore_start_log(rpin, target, time):
    """Open restore log file, log initial message"""
    try:
        Log.open_logfile(Globals.rbdir.append("restore.log"))
    except (LoggerError, Security.Violation) as e:
        Log("Warning - Unable to open logfile: %s" % str(e), 2)

    # Log following message at file verbosity 3, but term verbosity 4
    log_message = ("Starting restore of %s to %s as it was as of %s." % (
        rpin.get_safepath(), target.get_safepath(), Time.timetopretty(time)))
    if Log.term_verbosity >= 4:
        Log.log_to_term(log_message, 4)
    if Log.verbosity >= 3:
        Log.log_to_file(log_message)


def _restore_check_paths(rpin, rpout, restoreasof=None):
    """Make sure source and destination exist, and have appropriate type"""
    if not restoreasof:
        if not rpin.lstat():
            Log.FatalError(
                "Source file %s does not exist" % rpin.get_safepath())
    if not _force and rpout.lstat() and (not rpout.isdir() or rpout.listdir()):
        Log.FatalError("Restore target %s already exists, "
                       "specify --force to overwrite." % rpout.get_safepath())
    if _force and rpout.lstat() and not rpout.isdir():
        rpout.delete()


def _restore_check_backup_dir(mirror_root, src_rp=None, restore_as_of=1):
    """Make sure backup dir root rpin is in consistent state"""
    if not restore_as_of and not src_rp.isincfile():
        Log.FatalError("""File %s does not look like an increment file.

Try restoring from an increment file (the filenames look like
"foobar.2001-09-01T04:49:04-07:00.diff").""" % src_rp.get_safepath())

    result = _checkdest_need_check(mirror_root)
    if result is None:
        Log.FatalError("%s does not appear to be an rdiff-backup directory." %
                       Globals.rbdir.get_safepath())
    elif result == 1:
        Log.FatalError(
            "Previous backup to %s seems to have failed.\nRerun rdiff-backup "
            "with --check-destination-dir option to revert directory "
            "to state before unsuccessful session." %
            mirror_root.get_safepath())


def restore_set_root(rpin):
    """Set data dir, restore_root and index, or return None if fail

    The idea here is to keep backing up on the path until we find
    a directory that contains "rdiff-backup-data".  That is the
    mirror root.  If the path from there starts
    "rdiff-backup-data/increments*", then the index is the
    remainder minus that.  Otherwise the index is just the path
    minus the root.

    All this could fail if the increment file is pointed to in a
    funny way, using symlinks or somesuch.

    """
    global restore_root, _restore_index, _restore_root_set
    if rpin.isincfile():
        relpath = rpin.getincbase().path
    else:
        relpath = rpin.path
    if rpin.conn is not Globals.local_connection:
        # For security checking consistency, don't get absolute path
        pathcomps = relpath.split(b'/')
    else:
        pathcomps = rpath.RORPath.path_join(rpath.RORPath.getcwdb(),
                                            relpath).split(b'/')
    if not pathcomps[0]:
        min_len_pathcomps = 2  # treat abs paths differently
    else:
        min_len_pathcomps = 1

    i = len(pathcomps)
    while i >= min_len_pathcomps:
        parent_dir = rpath.RPath(rpin.conn, b'/'.join(pathcomps[:i]))
        if (parent_dir.isdir() and parent_dir.readable()
                and b"rdiff-backup-data" in parent_dir.listdir()):
            break
        if parent_dir.path == rpin.conn.Globals.get('restrict_path'):
            return None
        i = i - 1
    else:
        return None

    restore_root = parent_dir
    Log("Using mirror root directory %s" % restore_root.get_safepath(), 6)
    if restore_root.conn is Globals.local_connection:
        Security.reset_restrict_path(restore_root)
    SetConnections.UpdateGlobal('rbdir',
                                restore_root.append_path(b"rdiff-backup-data"))
    if not Globals.rbdir.isdir():
        Log.FatalError("Unable to read rdiff-backup-data directory %s" %
                       Globals.rbdir.get_safepath())

    from_datadir = tuple(pathcomps[i:])
    if not from_datadir or from_datadir[0] != b"rdiff-backup-data":
        _restore_index = from_datadir  # in mirror, not increments
    else:
        assert (from_datadir[1] == b"increments"
                or (len(from_datadir) == 2
                    and from_datadir[1].startswith(b'increments'))), from_datadir
        _restore_index = from_datadir[2:]
    _restore_root_set = 1
    return 1


def _action_list_increments(rp):
    """Print out a summary of the increments and their times"""
    rp = _require_root_set(rp, 1)
    _restore_check_backup_dir(restore_root)
    mirror_rp = restore_root.new_index(_restore_index)
    inc_rpath = Globals.rbdir.append_path(b'increments', _restore_index)
    incs = restore.get_inclist(inc_rpath)
    mirror_time = restore.MirrorStruct.get_mirror_time()
    if Globals.parsable_output:
        print(manage.describe_incs_parsable(incs, mirror_time, mirror_rp))
    else:
        print(manage.describe_incs_human(incs, mirror_time, mirror_rp))


def _require_root_set(rp, read_only):
    """Make sure rp is or is in a valid rdiff-backup dest directory.

    Also initializes fs_abilities (read or read/write) and quoting and
    return quoted rp if necessary.

    """
    if not restore_set_root(rp):
        Log.FatalError(
            "Bad directory %s.\n"
            "It doesn't appear to be an rdiff-backup destination dir." %
            rp.get_safepath())
    try:
        Globals.rbdir.conn.fs_abilities.single_set_globals(
            Globals.rbdir, read_only)
    except (OSError, IOError) as exc:
        print("\n")
        Log.FatalError("Could not open rdiff-backup directory\n\n%s\n\n"
                       "due to\n\n%s" % (Globals.rbdir.get_safepath(), exc))
    if Globals.chars_to_quote:
        return _restore_init_quoting(rp)
    else:
        return rp


def _action_list_increment_sizes(rp):
    """Print out a summary of the increments """
    rp = _require_root_set(rp, 1)
    print(manage.list_increment_sizes(restore_root, _restore_index))


def _action_calculate_average(rps):
    """Print out the average of the given statistics files"""
    statobjs = [statistics.StatsObj().read_stats_from_rp(rp) for rp in rps]
    average_stats = statistics.StatsObj().set_to_average(statobjs)
    print(average_stats.get_stats_logstring(
        "Average of %d stat files" % len(rps)))


def _action_remove_older_than(rootrp):
    """Remove all increment files older than a certain time"""
    rootrp = _require_root_set(rootrp, 0)
    _rot_require_rbdir_base(rootrp)

    time = _rot_check_time(_remove_older_than_string)
    if time is None:
        return
    Log("Actual remove older than time: %s" % (time, ), 6)
    manage.delete_earlier_than(Globals.rbdir, time)


def _rot_check_time(time_string):
    """Check remove older than time_string, return time in seconds"""
    try:
        time = Time.genstrtotime(time_string)
    except Time.TimeException as exc:
        Log.FatalError(str(exc))

    times_in_secs = [
        inc.getinctime() for inc in restore.get_inclist(
            Globals.rbdir.append_path(b"increments"))
    ]
    times_in_secs = [t for t in times_in_secs if t < time]
    if not times_in_secs:
        Log(
            "No increments older than %s found, exiting." %
            (Time.timetopretty(time), ), 3)
        return None

    times_in_secs.sort()
    inc_pretty_time = "\n".join(map(Time.timetopretty, times_in_secs))
    if len(times_in_secs) > 1 and not _force:
        Log.FatalError(
            "Found %d relevant increments, dated:\n%s"
            "\nIf you want to delete multiple increments in this way, "
            "use the --force." % (len(times_in_secs), inc_pretty_time))
    if len(times_in_secs) == 1:
        Log("Deleting increment at time:\n%s" % inc_pretty_time, 3)
    else:
        Log("Deleting increments at times:\n%s" % inc_pretty_time, 3)
    return times_in_secs[-1] + 1  # make sure we don't delete current increment


def _rot_require_rbdir_base(rootrp):
    """Make sure pointing to base of rdiff-backup dir"""
    if _restore_index != ():
        Log.FatalError("Increments for directory %s cannot be removed "
                       "separately.\nInstead run on entire directory %s." %
                       (rootrp.get_safepath(), restore_root.get_safepath()))


def _action_list_changed_since(rp):
    """List all the files under rp that have changed since restoretime"""
    rp = _require_root_set(rp, 1)
    try:
        rest_time = Time.genstrtotime(_restore_timestr)
    except Time.TimeException as exc:
        Log.FatalError(str(exc))
    mirror_rp = restore_root.new_index(_restore_index)
    inc_rp = mirror_rp.append_path(b"increments", _restore_index)
    for rorp in rp.conn.restore.ListChangedSince(mirror_rp, inc_rp, rest_time):
        # This is a hack, see restore.ListChangedSince for rationale
        print(rorp.get_safeindexpath())


def _action_list_at_time(rp):
    """List files in archive under rp that are present at restoretime"""
    rp = _require_root_set(rp, 1)
    try:
        rest_time = Time.genstrtotime(_restore_timestr)
    except Time.TimeException as exc:
        Log.FatalError(str(exc))
    mirror_rp = restore_root.new_index(_restore_index)
    inc_rp = mirror_rp.append_path(b"increments", _restore_index)
    for rorp in rp.conn.restore.ListAtTime(mirror_rp, inc_rp, rest_time):
        print(rorp.get_safeindexpath())


def _action_compare(compare_type, src_rp, dest_rp, compare_time=None):
    """Compare metadata in src_rp with metadata of backup session

    Prints to stdout whenever a file in the src_rp directory has
    different metadata than what is recorded in the metadata for the
    appropriate session.

    Session time is read from _restore_timestr if compare_time is None.

    """
    dest_rp = _require_root_set(dest_rp, 1)
    if not compare_time:
        try:
            compare_time = Time.genstrtotime(_restore_timestr)
        except Time.TimeException as exc:
            Log.FatalError(str(exc))

    mirror_rp = restore_root.new_index(_restore_index)
    inc_rp = Globals.rbdir.append_path(b"increments", _restore_index)
    _backup_set_select(src_rp)  # Sets source rorp iterator
    if compare_type == "compare":
        compare_func = compare.Compare
    elif compare_type == "compare-hash":
        compare_func = compare.Compare_hash
    else:
        assert compare_type == "compare-full", compare_type
        compare_func = compare.Compare_full
    return compare_func(src_rp, mirror_rp, inc_rp, compare_time)


def _action_verify(dest_rp, verify_time=None):
    """Check the hashes of the regular files against mirror_metadata"""
    dest_rp = _require_root_set(dest_rp, 1)
    if not verify_time:
        try:
            verify_time = Time.genstrtotime(_restore_timestr)
        except Time.TimeException as exc:
            Log.FatalError(str(exc))

    mirror_rp = restore_root.new_index(_restore_index)
    inc_rp = Globals.rbdir.append_path(b"increments", _restore_index)
    return dest_rp.conn.compare.Verify(mirror_rp, inc_rp, verify_time)


def _action_check_dest(dest_rp):
    """Check the destination directory, """
    dest_rp = _require_root_set(dest_rp, 0)
    need_check = _checkdest_need_check(dest_rp)
    if need_check is None:
        Log.FatalError(
            "No destination dir found at %s" % dest_rp.get_safepath())
    elif need_check == 0:
        Log.FatalError(
            "Destination dir %s does not need checking" %
            dest_rp.get_safepath(),
            no_fatal_message=1,
            errlevel=0)
    _init_user_group_mapping(dest_rp.conn)
    dest_rp.conn.regress.Regress(dest_rp)


def _checkdest_need_check(dest_rp):
    """Return None if no dest dir found, 1 if dest dir needs check, 0 o/w"""
    if not dest_rp.isdir() or not Globals.rbdir.isdir():
        return None
    for filename in Globals.rbdir.listdir():
        if filename not in [
                b'chars_to_quote', b'special_escapes', b'backup.log'
        ]:
            break
    else:  # This may happen the first backup just after we test for quoting
        return None
    curmirroot = Globals.rbdir.append(b"current_mirror")
    curmir_incs = restore.get_inclist(curmirroot)
    if not curmir_incs:
        Log.FatalError("""Bad rdiff-backup-data dir on destination side

The rdiff-backup data directory
%s
exists, but we cannot find a valid current_mirror marker.  You can
avoid this message by removing the rdiff-backup-data directory;
however any data in it will be lost.

Probably this error was caused because the first rdiff-backup session
into a new directory failed.  If this is the case it is safe to delete
the rdiff-backup-data directory because there is no important
information in it.

""" % (Globals.rbdir.get_safepath(), ))
    elif len(curmir_incs) == 1:
        return 0
    else:
        if not _force:
            try:
                curmir_incs[0].conn.regress.check_pids(curmir_incs)
            except (OSError, IOError) as exc:
                Log.FatalError("Could not check if rdiff-backup is currently"
                               "running due to\n%s" % exc)
        assert len(curmir_incs) == 2, \
            "Found too many current_mirror incs in %s!" % Globals.rbdir.get_safepath()
        return 1


def _checkdest_if_necessary(dest_rp):
    """Check the destination dir if necessary.

    This can/should be run before an incremental backup.

    """
    need_check = _checkdest_need_check(dest_rp)
    if need_check == 1:
        Log(
            "Previous backup seems to have failed, regressing "
            "destination now.", 2)
        try:
            dest_rp.conn.regress.Regress(dest_rp)
        except Security.Violation:
            Log.FatalError("Security violation while attempting to regress "
                           "destination, perhaps due to --restrict-read-only "
                           "or --restrict-update-only.")
