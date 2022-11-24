# Copyright 2002 Ben Escoto
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
"""Functions to make sure remote requests are kosher"""

import os
import tempfile
from rdiff_backup import Globals, log, rpath


class Violation(Exception):
    """Exception that indicates an improper request has been received"""
    pass


# security_level has 4 values and controls which requests from remote
# systems will be honored.  "read-write" means anything goes. "read-only"
# means that the requests must not write to disk.  "update-only" means
# that requests shouldn't destructively update the disk (but normal
# incremental updates are OK).  "minimal" means only listen to a few
# basic requests.
_security_level = None

# If this is set, it indicates that the remote connection should only
# deal with paths inside of restrict_path.
_restrict_path = None
_restrict_path_list = []

# This will store the list of functions that will be honored from
# remote connections.
_allowed_requests = None

# This stores the list of global variables that the client can not
# set on the server.
_disallowed_server_globals = ["server"]

# Some common file commands we may want to check to make sure they are
# in the right directory.  Any commands accessing files that could be
# added to _allowed_requests must be here.
#
# The keys are files request, the value is the index of the argument
# taking a file.
_file_requests = {
    "os.chmod": 0,
    "os.chown": 0,
    "os.lchown": 0,
    "os.link": 1,
    "os.listdir": 0,
    "os.makedirs": 0,
    "os.mkdir": 0,
    "os.mkfifo": 0,
    "os.mknod": 0,
    "os.remove": 0,
    "os.rename": 0,
    "os.rmdir": 0,
    "os.symlink": 1,
    "os.unlink": 0,
    "os.utime": 0,
    "rpath.make_file_dict": 0,
    "rpath.delete_dir_no_files": 0
}

# functions to set global values
_globals_requests = {
    "Globals.set_local",
    # API < 201
    "Globals.set",
}


def initialize(security_class, cmdpairs,
               security_level="read-write", restrict_path=None):
    """
    Initialize allowable request list and kind of restricted "chroot".

    security_level and restrict_path are only of importance if in server class.
    """
    global _allowed_requests, _security_level

    security_level, restrict_path = _set_security_level(
        security_class, security_level, restrict_path, cmdpairs)
    _security_level = security_level
    if restrict_path:
        reset_restrict_path(rpath.RPath(Globals.local_connection,
                                        restrict_path))
    _allowed_requests = _set_allowed_requests(security_class, security_level)


def reset_restrict_path(rp):
    """
    Reset global variable _restrict_path to be within rpath

    Normalize the remote path and extract its path.
    Also set the global variable _restrict_path_list as list of path components.
    It is assumed that the new path is a proper path, else function will fail.
    """
    assert rp.conn is Globals.local_connection, (
        "Function works locally not over '{conn}'.".format(conn=rp.conn))
    global _restrict_path, _restrict_path_list
    _restrict_path = rp.normalize().path
    _restrict_path_list = _restrict_path.split(b"/")


def vet_request(request, arglist):
    """Examine request for security violations"""
    if _security_level == "override":
        return
    if _restrict_path:
        for arg in arglist:
            if isinstance(arg, rpath.RPath):
                _vet_rpath(arg, request, arglist)
        if request.function_string in _file_requests:
            _vet_filename(request, arglist)
    if request.function_string in _allowed_requests:
        return
    if request.function_string in _globals_requests:
        if arglist[0] not in _disallowed_server_globals:
            return
    _raise_violation("invalid request", request, arglist)


def _set_security_level(security_class, security_level, restrict_path,
                        cmdpairs):
    """
    If running client, set security level and restrict_path

    To find these settings, we must look at the action's security class
    to see what is supposed to happen, and then look at the cmdpairs to
    see what end the client is on, unless we're in server security class,
    in which case, we just return what's been chosen by the user.
    """

    def islocal(cmdpair):
        return not cmdpair[0]

    def bothlocal(cp1, cp2):
        return islocal(cp1) and islocal(cp2)

    def bothremote(cp1, cp2):
        return not islocal(cp1) and not islocal(cp2)

    def getpath(cmdpair):
        return cmdpair[1]

    # in security class model, we use the restrictions given by the user
    if security_class is None or security_class == "server":
        return (security_level, restrict_path)

    cp1 = cmdpairs[0]
    if len(cmdpairs) > 1:
        cp2 = cmdpairs[1]
    else:
        cp2 = cp1

    if security_class == "backup":
        if bothlocal(cp1, cp2) or bothremote(cp1, cp2):
            sec_level = "minimal"
            rdir = tempfile.gettempdirb()
        elif islocal(cp1):
            sec_level = "read-only"
            rdir = getpath(cp1)
        else:  # cp2 is local but not cp1
            sec_level = "update-only"
            rdir = getpath(cp2)
    elif security_class == "restore":
        if len(cmdpairs) == 1 or bothlocal(cp1, cp2) or bothremote(cp1, cp2):
            sec_level = "minimal"
            rdir = tempfile.gettempdirb()
        elif islocal(cp1):
            sec_level = "read-only"
            rp1 = rpath.RPath(Globals.local_connection, getpath(cp1))
            (base_dir, ref_index, ref_type) = rp1.get_repository_dirs()
            if ref_type is None:
                # the error will be catched later more cleanly, so that the
                # connections can be properly closed
                log.Log("Invalid restore directory '{rd}'".format(
                    rd=getpath(cp1)), log.ERROR)
            rdir = base_dir.path
        else:  # cp2 is local but not cp1
            sec_level = "read-write"
            rdir = getpath(cp2)
    elif security_class == "mirror":  # compat200 not sure what this was?!?
        if bothlocal(cp1, cp2) or bothremote(cp1, cp2):
            sec_level = "minimal"
            rdir = tempfile.gettempdirb()
        elif islocal(cp1):
            sec_level = "read-only"
            rdir = getpath(cp1)
        else:  # cp2 is local but not cp1
            sec_level = "read-write"
            rdir = getpath(cp2)
    elif security_class == "validate":
        sec_level = "minimal"
        rdir = tempfile.gettempdirb()
    else:
        raise RuntimeError("Unknown action security class '{sec}'.".format(
            sec=security_class))

    return (sec_level, rdir)


def _set_allowed_requests(sec_class, sec_level):
    """
    Set the allowed requests list using the security level
    """
    requests = {  # minimal set of requests
        "RedirectedRun",  # connection.RedirectedRun
        "VirtualFile.readfromid",  # connection.VirtualFile.readfromid
        "VirtualFile.closebyid",  # connection.VirtualFile.closebyid
        "Globals.get",
        "log.Log.open_logfile_allconn",
        "log.Log.close_logfile_allconn",
        "log.Log.log_to_file",
        "robust.install_signal_handlers",
        "SetConnections.add_redirected_conn",
        # System
        # "gzip.GzipFile",  # ??? perhaps covered by VirtualFile
        # "open",  # ??? perhaps covered by VirtualFile
        "sys.stdout.write",
        # API < 201
        "FilenameMapping.set_init_quote_vals_local",
        "Time.setcurtime_local",
        # API >= 201
        "_repo_shadow.RepoShadow.is_locked",
        "_repo_shadow.RepoShadow.setup_paths",
    }
    if (sec_level == "read-only" or sec_level == "update-only"
            or sec_level == "read-write"):
        requests.update([
            "rpath.gzip_open_local_read",
            "rpath.make_file_dict",
            "rpath.open_local_read",
            "rpath.setdata_local",
            # System
            "os.getuid",
            "os.listdir",
            # API < 201
            "os.name",  # doesn't work because not callable but attribute!
            "Hardlink.initialize_dictionaries",
            # API >= 201
            "platform.system",
        ])
    if sec_level == "read-only" or sec_level == "read-write":
        requests.update([
            # API < 201
            "backup.SourceStruct.get_source_select",
            "backup.SourceStruct.set_source_select",
            "backup.SourceStruct.get_diffs",
            "compare.DataSide.get_source_select",  # inherited from SourceStruct
            "compare.DataSide.compare_fast",
            "compare.DataSide.compare_hash",
            "compare.DataSide.compare_full",
            "compare.RepoSide.init_and_get_iter",
            "compare.RepoSide.close_rf_cache",  # inherited from MirrorStruct
            "compare.RepoSide.attach_files",
            "compare.Verify",
            "fs_abilities.get_readonly_fsa",
            "restore.MirrorStruct.get_increment_times",
            "restore.MirrorStruct.set_mirror_and_rest_times",
            "restore.MirrorStruct.set_mirror_select",
            "restore.MirrorStruct.initialize_rf_cache",
            "restore.MirrorStruct.close_rf_cache",
            "restore.MirrorStruct.get_diffs",
            "restore.ListChangedSince",
            "restore.ListAtTime",
            # API >= 201
            "_dir_shadow.ReadDirShadow.compare_full",
            "_dir_shadow.ReadDirShadow.compare_hash",
            "_dir_shadow.ReadDirShadow.compare_meta",
            "_dir_shadow.ReadDirShadow.get_diffs",
            "_dir_shadow.ReadDirShadow.get_fs_abilities",
            "_dir_shadow.ReadDirShadow.get_select",
            "_dir_shadow.ReadDirShadow.set_select",
            "_repo_shadow.RepoShadow.get_config",
            "_repo_shadow.RepoShadow.get_fs_abilities_readonly",
            "_repo_shadow.RepoShadow.init_loop",
            "_repo_shadow.RepoShadow.get_mirror_time",
            "_repo_shadow.RepoShadow.get_increment_times",
            "_repo_shadow.RepoShadow.set_select",
            "_repo_shadow.RepoShadow.finish_loop",
            "_repo_shadow.RepoShadow.get_diffs",
            "_repo_shadow.RepoShadow.list_files_changed_since",
            "_repo_shadow.RepoShadow.list_files_at_time",
            "_repo_shadow.RepoShadow.init_and_get_loop",
            "_repo_shadow.RepoShadow.verify",
        ])
    if sec_level == "update-only" or sec_level == "read-write":
        requests.update([
            "VirtualFile.writetoid",  # connection.VirtualFile.writetoid
            "log.ErrorLog.close",
            "log.ErrorLog.isopen",
            "log.ErrorLog.open",
            "log.ErrorLog.write_if_open",
            "log.Log.close_logfile_local",
            "log.Log.open_logfile_local",
            "statistics.record_error",
            # API < 201
            "backup.DestinationStruct.set_rorp_cache",
            "backup.DestinationStruct.get_sigs",
            "backup.DestinationStruct.patch_and_increment",
            "fs_abilities.backup_set_globals",
            "Main.backup_touch_curmirror_local",
            "Main.backup_remove_curmirror_local",
            "Main.backup_close_statistics",
            "regress.check_pids",
            # API >= 201
            "_repo_shadow.RepoShadow.close_statistics",
            "_repo_shadow.RepoShadow.get_fs_abilities_readwrite",
            "_repo_shadow.RepoShadow.get_sigs",
            "_repo_shadow.RepoShadow.lock",
            "_repo_shadow.RepoShadow.needs_regress",
            "_repo_shadow.RepoShadow.apply",
            "_repo_shadow.RepoShadow.remove_current_mirror",
            "_repo_shadow.RepoShadow.set_config",
            "_repo_shadow.RepoShadow.touch_current_mirror",
            "_repo_shadow.RepoShadow.unlock",
        ])
    if sec_level == "read-write":
        requests.update([
            "rpath.delete_dir_no_files",
            "rpath.copy_reg_file",  # FIXME really needed?
            "rpath.make_socket_local",  # FIXME really needed?
            "rpath.RPath.fsync_local",  # FIXME really needed?
            # System
            "os.chmod",
            "os.chown",
            "os.lchown",
            "os.link",
            "os.makedev",
            "os.makedirs",
            "os.mkdir",
            "os.mkfifo",
            "os.mknod",
            "os.remove",
            "os.rename",
            "os.rmdir",
            "os.symlink",
            "os.unlink",
            "os.utime",
            "shutil.rmtree",
            # API < 201
            "backup.DestinationStruct.patch",
            "manage.delete_earlier_than_local",
            "fs_abilities.restore_set_globals",
            "fs_abilities.single_set_globals",
            "regress.Regress",
            "restore.TargetStruct.get_initial_iter",
            "restore.TargetStruct.patch",
            "restore.TargetStruct.set_target_select",
            # API >= 201
            "_repo_shadow.RepoShadow.regress",
            "_repo_shadow.RepoShadow.remove_increments_older_than",
            "_dir_shadow.WriteDirShadow.get_fs_abilities",
            "_dir_shadow.WriteDirShadow.get_sigs_select",
            "_dir_shadow.WriteDirShadow.apply",
            "_dir_shadow.WriteDirShadow.set_select",
        ])
    if sec_class == "server":
        requests.update([
            "log.Log.setverbosity",
            "log.Log.setterm_verbosity",
            "SetConnections.init_connection_remote",
            # API < 201
            "Globals.postset_regexp_local",
            "Time.setprevtime_local",
            "user_group.init_user_mapping",
            "user_group.init_group_mapping",
            # API >= 201
            "_repo_shadow.RepoShadow.init_owners_mapping",
            "_dir_shadow.WriteDirShadow.init_owners_mapping",
            "Globals.set_api_version",
        ])
    return requests


def _vet_filename(request, arglist):
    """Check to see if file operation is within the restrict_path"""
    i = _file_requests[request.function_string]
    if len(arglist) <= i:
        _raise_violation("argument list shorter than %d" % i + 1, request,
                         arglist)
    filename = arglist[i]
    if not isinstance(filename, (bytes, str, os.PathLike)):
        _raise_violation("argument %d doesn't look like a filename" % i,
                         request, arglist)

    _vet_rpath(
        rpath.RPath(Globals.local_connection, filename), request, arglist)


def _vet_rpath(rp, request, arglist):
    """Internal function to validate that a specific path isn't restricted"""
    if _restrict_path and rp.conn is Globals.local_connection:
        norm_path = rp.normalize().path
        components = norm_path.split(b"/")
        # we can't properly assess paths with parent directory, so we reject
        if b".." in components:
            _raise_violation("normalized path '{np}' can't contain "
                             "parent directory '..'".format(np=norm_path),
                             request, arglist)
        # the restrict path being root is a special case, we could check it
        # earlier but we would miss the previous checks
        if _restrict_path == b"/":
            return
        # the normalized path must begin with the restricted path
        # using lists, we avoid /bla/foobar being deemed within /bla/foo
        if components[:len(_restrict_path_list)] != _restrict_path_list:
            _raise_violation("normalized path '{np}' not within restricted "
                             "path '{rp}'".format(np=norm_path,
                                                  rp=_restrict_path),
                             request, arglist)


def _raise_violation(reason, request, arglist):
    """Raise a security violation about given request"""
    raise Violation(
        "\nWARNING: Security Violation due to {sv} for function: {func}"
        "\nwith arguments: {args}"
        "\nCompared to {path} restricted {level}.\n".format(
            sv=reason, func=request.function_string,
            args=list(map(str, arglist)),
            path=_restrict_path, level=_security_level))
