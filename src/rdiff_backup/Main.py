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
from .log import Log, LoggerError, ErrorLog
from . import (
    Globals, Time, SetConnections, rpath,
    manage, connection, restore, FilenameMapping,
    Security, C, statistics, compare
)
from rdiffbackup import arguments, actions_mgr, actions

_action = None

# These are global because they are set while we are trying to figure
# whether to restore or to backup
restore_root, _restore_index, _restore_root_set = None, None, 0

# Those global variables are listed here to make the list complete
_restore_timestr = None
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


def _parse_cmdlineoptions_compat200(arglist):  # noqa: C901
    """
    Parse argument list and set global preferences, compatibility function
    between old and new way of parsing parameters.
    """
    global _args, _action, _restore_timestr
    global _remove_older_than_string

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
    if arglist.action in ('backup', 'regress', 'restore'):
        Globals.set("compression", arglist.compression)
        Globals.set("no_compression_regexp_string",
                    os.fsencode(arglist.not_compressed_regexp))
    else:
        Globals.set("no_compression_regexp_string",
                    os.fsencode(actions.DEFAULT_NOT_COMPRESSED_REGEXP))
    if arglist.action in ('backup'):
        Globals.set("file_statistics", arglist.file_statistics)
        Globals.set("print_statistics", arglist.print_statistics)
    Globals.set("null_separator", arglist.null_separator)
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

    if arglist.action in ('info', 'server'):
        _args = []
    else:
        _args = arglist.locations


def _take_action(rps):
    """Do whatever action says"""
    if _action == "remove-older-than":
        action_result = _action_remove_older_than(rps[0])
    else:
        raise ValueError("Unknown action " + _action)
    return action_result


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
