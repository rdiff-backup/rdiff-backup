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

import errno
import io
import os
import sys
import tempfile
import time
import yaml
from .log import Log, LoggerError, ErrorLog
from . import (
    Globals, Time, SetConnections, robust, rpath,
    manage, backup, connection, restore, FilenameMapping,
    Security, C, statistics, compare
)
from rdiffbackup import arguments, actions_mgr, actions

_action = None
_create_full_path = None
_remote_schema = None
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


def main_run_and_exit(arglist):
    """
    Main function to be called with arguments list without the name of the
    program, aka $0 resp. sys.argv[0].
    
    The function simply calls the internal function '_main_run' and exits
    with the code returned.
    """
    sys.exit(_main_run(arglist))


def _main_run(arglist, security_override=False):
    """
    Internal main function to be called with arguments list without the
    name of the program, aka $0 resp. sys.argv[0].

    The security override is only meant for test purposes

    The function returns with an error code.
    """

    # get a dictionary of discovered action plugins
    discovered_actions = actions_mgr.get_discovered_actions()

    # parse accordingly the arguments
    parsed_args = arguments.parse(
        arglist, "rdiff-backup {ver}".format(ver=Globals.version),
        actions_mgr.get_generic_parsers(),
        actions_mgr.get_parent_parsers_compat200(),
        discovered_actions)

    # instantiate the action object from the dictionary, handing over the
    # parsed arguments
    action = discovered_actions[parsed_args.action](parsed_args, Log, ErrorLog)

    # compatibility plug, we need verbosity set properly asap
    _parse_cmdlineoptions_compat200(parsed_args)

    # validate that everything looks good before really starting
    ret_val = action.pre_check()
    if ret_val != 0:
        Log("Action {act} failed on {func}.".format(
            act=parsed_args.action, func="pre_check"), Log.ERROR)
        return ret_val

    # now start for real, conn_act and action are the same object
    with action.connect() as conn_act:

        # For test purposes
        if security_override:
            Globals.security_level = "override"

        ret_val = conn_act.check()
        if ret_val != 0:
            Log("Action {act} failed on {func}.".format(
                act=parsed_args.action, func="check"), Log.ERROR)
            return ret_val

        ret_val = conn_act.setup()
        if ret_val != 0:
            Log("Action {act} failed on {func}.".format(
                act=parsed_args.action, func="setup"), Log.ERROR)
            return ret_val

        ret_val = conn_act.run()
        if ret_val != 0:
            Log("Action {act} failed on {func}.".format(
                act=parsed_args.action, func="run"), Log.ERROR)
            return ret_val

    return ret_val


# @API(backup_touch_curmirror_local, 200)
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


# @API(backup_remove_curmirror_local, 200)
def backup_remove_curmirror_local():
    """Remove the older of the current_mirror files.  Use at end of session"""
    assert Globals.rbdir.conn is Globals.local_connection, (
        "Function can only be called locally and not over '{conn}'.".format(
            conn=Globals.rbdir.conn))
    curmir_incs = restore.get_inclist(Globals.rbdir.append(b"current_mirror"))
    assert len(curmir_incs) == 2, (
        "There must be two current mirrors not '{ilen}'.".format(
            ilen=len(curmir_incs)))
    if curmir_incs[0].getinctime() < curmir_incs[1].getinctime():
        older_inc = curmir_incs[0]
    else:
        older_inc = curmir_incs[1]
    if Globals.do_fsync:
        C.sync()  # Make sure everything is written before curmirror is removed
    older_inc.delete()


# @API(backup_close_statistics, 200)
def backup_close_statistics(end_time):
    """Close out the tracking of the backup statistics.

    Moved to run at this point so that only the clock of the system on which
    rdiff-backup is run is used (set by passing in time.time() from that
    system). Use at end of session.

    """
    assert Globals.rbdir.conn is Globals.local_connection, (
        "Function can only be called locally and not over '{conn}'.".format(
            conn=Globals.rbdir.conn))
    if Globals.print_statistics:
        statistics.print_active_stats(end_time)
    if Globals.file_statistics:
        statistics.FileStats.close()
    statistics.write_active_statfileobj(end_time)


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
    elif (from_datadir[1] == b"increments"
            or (len(from_datadir) == 2
                and from_datadir[1].startswith(b'increments'))):
        _restore_index = from_datadir[2:]
    else:
        raise RuntimeError("Data directory '{ddir}' looks neither like mirror "
                           "nor like increment.".format(ddir=from_datadir))
    _restore_root_set = 1
    return 1


def _parse_cmdlineoptions_compat200(arglist):  # noqa: C901
    """
    Parse argument list and set global preferences, compatibility function
    between old and new way of parsing parameters.
    """
    global _args, _action, _create_full_path, _force, _restore_timestr
    global _remote_schema, _remove_older_than_string
    global _user_mapping_filename, _group_mapping_filename, \
        _preserve_numerical_ids

    def sel_fl(filename):
        """Helper function for including/excluding filelists below"""
        if filename is True:  # we really mean the boolean True
            return sys.stdin.buffer
        try:
            return open(filename, "rb")  # files match paths hence bytes/bin
        except IOError:
            Log.FatalError("Error opening file %s" % filename)

    def normalize_path(path):
        """Used below to normalize the security paths before setting"""
        return rpath.RPath(Globals.local_connection, path).normalize().path

    if arglist.action == "calculate":
        _action = arglist.action + "-" + arglist.method
    elif arglist.action == "compare":
        _action = arglist.action
        if arglist.method != "meta":
            _action += "-" + arglist.method
        _restore_timestr = arglist.at
    elif arglist.action == "regress":
        _action = "check-destination-dir"
        Globals.set("allow_duplicate_timestamps",
                    arglist.allow_duplicate_timestamps)
    elif arglist.action == "list":
        if arglist.entity == "files":
            if arglist.changed_since:
                _restore_timestr = arglist.changed_since
                _action = "list-changed-since"
            else:
                _restore_timestr = arglist.at
                _action = "list-at-time"
        elif arglist.entity == "increments":
            if arglist.size:
                _action = 'list-increment-sizes'
            else:
                _action = "list-increments"
    elif arglist.action == "restore":
        if not arglist.increment:
            _restore_timestr = arglist.at
        _action = "restore"
    elif arglist.action == "remove":
        if arglist.entity == "increments":
            _remove_older_than_string = arglist.older_than
            _action = "remove-older-than"
    elif arglist.action == "server":
        _action = "server"
        Globals.server = True
    elif arglist.action == "test":
        _action = "test-server"
    elif arglist.action == "verify":
        _restore_timestr = arglist.at
        _action = "verify"
    else:
        _action = arglist.action

    if arglist.action in ('backup', 'restore'):
        Globals.set("acls_active", arglist.acls)
        Globals.set("win_acls_active", arglist.acls)
        Globals.set("carbonfile_active", arglist.carbonfile)
        Globals.set("compare_inode", arglist.compare_inode)
        Globals.set("eas_active", arglist.eas)
        Globals.set("preserve_hardlinks", arglist.hard_links)
        Globals.set("resource_forks_active", arglist.resource_forks)
        Globals.set("never_drop_acls", arglist.never_drop_acls)
        _create_full_path = arglist.create_full_path
    if arglist.action in ('backup', 'regress', 'restore'):
        Globals.set("compression", arglist.compression)
        Globals.set("no_compression_regexp_string",
                    os.fsencode(arglist.not_compressed_regexp))
        _preserve_numerical_ids = arglist.preserve_numerical_ids
        if arglist.group_mapping_file is not None:
            _group_mapping_filename = os.fsencode(arglist.group_mapping_file)
        if arglist.user_mapping_file is not None:
            _user_mapping_filename = os.fsencode(arglist.user_mapping_file)
    else:
        Globals.set("no_compression_regexp_string",
                    os.fsencode(actions.DEFAULT_NOT_COMPRESSED_REGEXP))
    if arglist.action in ('backup'):
        Globals.set("file_statistics", arglist.file_statistics)
        Globals.set("print_statistics", arglist.print_statistics)
    Globals.set("null_separator", arglist.null_separator)
    Globals.set("parsable_output", arglist.parsable_output)
    Globals.set("use_compatible_timestamps", arglist.use_compatible_timestamps)
    Globals.set("do_fsync", arglist.fsync)
    if arglist.current_time is not None:
        Globals.set_integer('current_time', arglist.current_time)
    if arglist.chars_to_quote is not None:
        Globals.set('chars_to_quote', os.fsencode(arglist.chars_to_quote))
    if arglist.remote_tempdir is not None:
        Globals.remote_tempdir = os.fsencode(arglist.remote_tempdir)
    if arglist.restrict_path is not None:
        Globals.restrict_path = normalize_path(arglist.restrict_path)
        if arglist.restrict_mode == "read-write":
            Globals.security_level = "all"
        else:
            Globals.security_level = arglist.restrict_mode
    if arglist.api_version is not None:  # FIXME
        Globals.set_api_version(arglist.api_version)
    _force = arglist.force
    if arglist.remote_schema is not None:
        _remote_schema = os.fsencode(arglist.remote_schema)
    if arglist.terminal_verbosity is not None:
        Log.setterm_verbosity(arglist.terminal_verbosity)
    Log.setverbosity(arglist.verbosity)
    if arglist.tempdir is not None:
        if not os.path.isdir(arglist.tempdir):
            Log.FatalError(
                "Temporary directory '{dir}' doesn't exist.".format(
                    dir=arglist.tempdir))
        # At least until Python 3.10, the module tempfile doesn't work properly,
        # especially under Windows, if tempdir is stored as bytes.
        # See https://github.com/python/cpython/pull/20442
        tempfile.tempdir = arglist.tempdir

    # handle selection options
    if (arglist.action in ('backup', 'compare', 'restore')
            and arglist.selections):
        for selection in arglist.selections:
            if 'filelist' in selection[0]:
                if selection[0].endswith("-stdin"):
                    _select_opts.append((
                        "--" + selection[0][:-6],  # remove '-stdin'
                        "standard input"))
                else:
                    _select_opts.append(("--" + selection[0], selection[1]))
                _select_files.append(sel_fl(selection[1]))
            else:
                _select_opts.append(("--" + selection[0], selection[1]))

    if arglist.action in ('info', 'server'):
        _args = []
    else:
        _args = arglist.locations


def _commandline_error(message):
    Log.FatalError(
        "%s\nSee the rdiff-backup manual page for more information." % message)


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
        action_result = _action_restore(rps[0], rps[1])
    elif _action == "verify":
        action_result = _action_verify(rps[0])
    else:
        raise ValueError("Unknown action " + _action)
    return action_result


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
    _backup_warn_if_infinite_recursion(rpin, rpout)
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

    assert rpout.lstat(), (
        "Target backup directory '{rp!s}' must exist.".format(rp=rpout))
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


def _backup_warn_if_infinite_recursion(rpin, rpout):
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
source directory '%s'.  This could cause an infinite recursion.  You
may need to use the --exclude option (which you might already have done)."""
        % (rpout.get_safepath(), rpin.get_safepath()), 2)


def _backup_get_mirrortime():
    """Return time in seconds of previous mirror, or None if cannot"""
    incbase = Globals.rbdir.append_path(b"current_mirror")
    mirror_rps = restore.get_inclist(incbase)
    assert len(mirror_rps) <= 1, (
        "Found {mlen} current_mirror paths, expected <=1".format(
            mlen=len(mirror_rps)))
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


def _action_restore(src_rp, dest_rp):
    """Main restoring function

    Here src_rp should be the source file (either an increment or
    mirror file), dest_rp should be the target rp to be written.

    """
    if src_rp.isincfile():
        if _restore_timestr and _restore_timestr != "now":
            Log.FatalError("You can't give an increment and a time to restore at the same time.")
        else:
            restore_as_of = False
    else:
        restore_as_of = True

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
        fp.close()
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


def _restore_check_paths(rpin, rpout, restore_as_of=None):
    """Make sure source and destination exist, and have appropriate type"""
    if not restore_as_of:
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
    elif compare_type == "compare-full":
        compare_func = compare.Compare_full
    else:
        raise ValueError(
            "Comparaison type '{comp}' must be one of compare, "
            "compare-hash or compare-full.".format(comp=compare_type))
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
        Log("No destination dir found at {ddir}.".format(
            ddir=dest_rp.get_safepath()), 1)
        return 1
    elif need_check == 0:
        Log("Destination dir {ddir} does not need checking.".format(
            ddir=dest_rp.get_safepath()), 2)
        return 0
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
        assert len(curmir_incs) == 2, (
            "Found more than 2 current_mirror incs in '{rp!s}'.".format(
                rp=Globals.rbdir))
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
