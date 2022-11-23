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
"""Parse args and setup connections

The functions in this module are used once by Main to parse file
descriptions like bescoto@folly.stanford.edu:/usr/bin/ls and to set up
the related connections.

"""

import os
import re
import sys
import subprocess
from rdiff_backup import connection, Globals, log, rpath
from rdiffbackup.utils import safestr

# This is a list of remote commands used to start the connections.
# The first is None because it is the local connection.
__conn_remote_cmds = [None]

# keep a list of sub-processes running; we don't use it, it's only to avoid
# "ResourceWarning: subprocess N is still running" from subprocess library
_processes = []


class SetConnectionsException(Exception):
    pass


def get_cmd_pairs(locations, remote_schema=None, ssh_compression=True,
                  remote_tempdir=None, term_verbosity=None):
    """Map the given file descriptions into command pairs

    Command pairs are tuples cmdpair with length 2.  cmdpair[0] is
    None iff it describes a local path, and cmdpair[1] is the path.

    """

    # This is the schema that determines how rdiff-backup will open a
    # pipe to the remote system.  If the file is given as A::B, {h}/%s will
    # be substituted with A in the schema.
    if remote_schema:
        cmd_schema = remote_schema
    else:
        if ssh_compression:
            cmd_schema = b"ssh -C {h} rdiff-backup"
        else:
            cmd_schema = b"ssh {h} rdiff-backup"
        if remote_tempdir:
            cmd_schema += (b" --tempdir=" + remote_tempdir)
        # we could wait until the verbosity is "transferred" to the remote side
        # but we might miss important messages at the beginning of the process
        if term_verbosity is not None:
            cmd_schema += b" --terminal-verbosity %d" % term_verbosity
        if Globals.get_api_version() > 200:  # compat200
            cmd_schema += b" server"
        else:
            cmd_schema += b" --server"

    if not locations:
        return []
    desc_triples = list(map(parse_location, locations))

    # was any error string be returned as third in the list?
    for err in [triple[2] for triple in desc_triples if triple[2]]:
        raise SetConnectionsException(err)

    if remote_schema and not [x for x in desc_triples if x[0]]:
        # remote schema defined but no remote location found
        log.Log("Remote schema option ignored - no remote file descriptions",
                log.WARNING)

    # strip the error field from the triples to get pairs
    desc_pairs = [triple[:2] for triple in desc_triples]

    def desc2cmd_pairs(desc_pair):
        """Return pair (remote_cmd, filename) from desc_pair"""
        host_info, filename = desc_pair
        if not host_info:
            return (None, filename)
        else:
            return (_fill_schema(host_info, cmd_schema), filename)

    cmd_pairs = list(map(desc2cmd_pairs, desc_pairs))

    return cmd_pairs


def get_connected_rpath(cmd_pair):
    """
    Return normalized RPath from command pair (remote_cmd, filename)
    """
    cmd, filename = cmd_pair
    if cmd:
        conn = _init_connection(cmd)
    else:
        conn = Globals.local_connection
    if conn:
        return rpath.RPath(conn, filename).normalize()
    else:
        return None


# @API(init_connection_remote, 200)
def init_connection_remote(conn_number):
    """Run on server side to tell self that have given conn_number"""
    Globals.connection_number = conn_number
    Globals.local_connection.conn_number = conn_number
    Globals.connection_dict[0] = Globals.connections[1]
    Globals.connection_dict[conn_number] = Globals.local_connection


# @API(add_redirected_conn, 200)
def add_redirected_conn(conn_number):
    """Run on server side - tell about redirected connection"""
    Globals.connection_dict[conn_number] = \
        connection.RedirectedConnection(conn_number)


def BackupInitConnections(reading_conn, writing_conn):  # compat200
    """Backup specific connection initialization"""
    reading_conn.Globals.set_local("isbackup_reader", True)
    writing_conn.Globals.set_local("isbackup_writer", True)
    Globals.set_all("backup_reader", reading_conn)
    Globals.set_all("backup_writer", writing_conn)


def CloseConnections():
    """Close all connections.  Run by client"""
    assert not Globals.server, "Connections can't be closed by server"
    for conn in Globals.connections:
        if conn:  # could be None, if the connection failed
            conn.quit()
    del Globals.connections[1:]  # Only leave local connection
    Globals.connection_dict = {0: Globals.local_connection}
    Globals.backup_reader = Globals.backup_writer = None
    Globals.isbackup_reader = Globals.isbackup_writer = False


def test_connections(rpaths):
    """
    Test connections, printing results.
    Returns OK if all connections work, Error if one or more failed,
    File Error if the length of the list of connections isn't correct,
    most probably because the user called rdiff-backup incorrectly
    """
    # the function doesn't use the log functions because it might not have
    # an error or log file to use.
    conn_len = len(Globals.connections)
    if conn_len == 1:
        log.Log("No remote connections specified, only local one available",
                log.ERROR)
        return Globals.RET_CODE_FILE_ERR
    elif conn_len != len(rpaths) + 1:
        print("All {pa} parameters must be remote of the form "
              "'server::path'".format(pa=len(rpaths)), log.ERROR)
        return Globals.RET_CODE_FILE_ERR

    # we create a list of all test results, skipping the connection 0, which
    # is the local one.
    results = map(lambda i: _test_connection(i, rpaths[i - 1]),
                  range(1, conn_len))
    if all(results):
        return Globals.RET_CODE_OK
    else:
        return Globals.RET_CODE_ERR


def parse_location(file_desc):
    """
    Parse file description returning triple (host_info, filename, error)

    In other words, bescoto@folly.stanford.edu::/usr/bin/ls =>
    ("bescoto@folly.stanford.edu", "/usr/bin/ls", None).  The
    complication is to allow for quoting of : by a \\.  If the
    string is not separated by ::, then the host_info is None.
    If the error isn't None, it is an error message explaining the issue.
    """

    # paths and similar objects must always be bytes
    file_desc = os.fsencode(file_desc)
    # match double colon not preceded by an odd number of backslashes
    file_parts = [x for x in re.split(rb"(?<!\\)(\\{2})*::", file_desc)
                  if x is not None]
    # because even numbers of backslashes are grouped as part of the split,
    # we need to stitch them back together,e.g.
    # "host\\\\::path" becomes ["host","\\\\","path"]
    # which then becomes ["host\\\\", "path"]
    concat_parts = []
    keep = None
    for part in reversed(file_parts):
        if re.match(rb"^(\\{2})+$", part):
            keep = part
        else:
            if keep:
                part += keep
                keep = None
            concat_parts.append(part)
    concat_parts.reverse()

    if len(concat_parts) > 2:
        return (None, None,
                "Too many parts separated by double colon in '{desc}'".format(
                    desc=file_desc))
    elif len(concat_parts) == 0:  # it's probably not possible but...
        return (None, None,
                "No location could be identified in '{desc}'".format(
                    desc=file_desc))
    elif len(concat_parts) == 1:  # a local path without remote host
        file_host = None
        file_path = concat_parts[0]
    else:  # length of 2 is given
        if not concat_parts[0]:
            return (None, None,
                    "No file host in location '{lo}' starting with '::'".format(
                        lo=file_desc))
        elif not concat_parts[1]:
            return (None, None,
                    "No file path in location '{lo}' ending with '::'".format(
                        lo=file_desc))
        file_host = concat_parts[0]
        file_path = concat_parts[1]

    # According to description, the backslashes must be unquoted, i.e.
    # double backslashes replaced by single ones, and single ones removed
    # before colons.
    sbs = b'\\'  # single backslash
    dbs = rb'\\'  # double backslash (r for raw)
    # Hence we split along double ones, remove single ones in each element,
    # and join back with a single backslash.
    if file_host:
        file_host = sbs.join(
            [x.replace(sbs + b':', b':') for x in file_host.split(dbs)])
    # handle the special case of an UNC path '\\hostname\some\path'
    if (file_path.startswith(dbs)
            and len(file_path) > 2 and file_path[2:3] != sbs):
        is_unc_path = True
    else:
        # it could still be an UNC path using forward slashes
        # but we don't need to care
        is_unc_path = False
    file_path = sbs.join(
        [x.replace(sbs + b':', b':') for x in file_path.split(dbs)])
    # And then we make sure that paths under Windows use / instead of \
    # (we don't do it for the host part because it could be a shell command)
    file_path = file_path.replace(b"\\", b"/")
    if is_unc_path:
        file_path = b'/' + file_path

    return (file_host, file_path, None)


def _fill_schema(host_info, cmd_schema):
    """
    Fills host_info and optionally the version into the schema

    Returns the filled remote command
    """
    assert isinstance(host_info, bytes), (
        "host_info parameter must be bytes not {thi}".format(
            thi=type(host_info)))
    try:
        # for security reasons, we accept only specific format placeholders
        # h for host_info, Vx,Vy,Vz for version x.y.z
        # and the host placeholder is mandatory
        if ((re.findall(b"{[^}]*}", cmd_schema)
             != re.findall(b"{h}|{V[xyz]}", cmd_schema))
                or (b"{h}" not in cmd_schema
                    and b"%s" not in cmd_schema)):  # compat200
            raise KeyError
        if b"{h}" in cmd_schema:
            ver_split = Globals.version.split(".")
            # bytes doesn't have a format method, hence the conversions
            return os.fsencode(os.fsdecode(cmd_schema).format(
                h=os.fsdecode(host_info),
                Vx=ver_split[0], Vy=ver_split[1], Vz=ver_split[2]))
        else:  # compat200: accepts "%s" as host place-holder
            return cmd_schema % host_info
    except (TypeError, KeyError):
        log.Log.FatalError("Invalid remote schema: {rs}".format(
            rs=safestr.to_str(cmd_schema)))


def _init_connection(remote_cmd):
    """Run remote_cmd, register connection, and then return it

    If remote_cmd is None, then the local connection will be
    returned.  This also updates some settings on the remote side,
    like global settings, its connection number, and verbosity.

    """
    global _processes
    if not remote_cmd:
        return Globals.local_connection

    log.Log("Executing remote command {rc}".format(
        rc=safestr.to_str(remote_cmd)), log.INFO)
    try:
        # we need buffered read on SSH communications, hence using
        # default value for bufsize parameter
        if os.name == 'nt':
            # FIXME workaround because python 3.7 doesn't yet accept bytes
            process = subprocess.Popen(
                os.fsdecode(remote_cmd),
                shell=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE)
        else:
            process = subprocess.Popen(
                remote_cmd,
                shell=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE)
        (stdin, stdout) = (process.stdin, process.stdout)
        # only to avoid resource warnings about subprocess still running
        _processes.append(process)
    except OSError:
        (stdin, stdout) = (None, None)
    conn_number = len(Globals.connections)
    conn = connection.PipeConnection(stdout, stdin, conn_number)

    if not _validate_connection_version(conn, remote_cmd):
        return None
    log.Log("Registering connection {co}".format(co=conn_number), log.DEBUG)
    _init_connection_routing(conn, conn_number, remote_cmd)
    _init_connection_settings(conn)
    return conn


def _validate_connection_version(conn, remote_cmd):
    """Validate that local and remote versions are compatible.
    Either the old method using the application version with only a warning
    if they're not the same, or the new method using the API version and
    trying to find a common compatible version.
    Returns False if something goes wrong or no compatible version could
    be found, else returns True (also in warning case)."""

    try:
        remote_version = conn.Globals.get('version')
    except connection.ConnectionError as exception:
        log.Log(
            """Couldn't start up the remote connection by executing '{rc}'
due to exception '{ex}'.

Remember that, under the default settings, rdiff-backup must be
installed in the PATH on the remote system.  See the man page for more
information on this.  This message may also be displayed if the remote
version of rdiff-backup is quite different from the local version ({lv})
""".format(ex=exception, rc=safestr.to_str(remote_cmd), lv=Globals.version),
            log.ERROR)
        return False
    except OverflowError:
        log.Log(
            """Integer overflow while attempting to establish the
remote connection by executing {rc}

Please make sure that nothing is printed (e.g., by your login shell) when this
command executes. Try running this command: {co}

which should only print out the text: rdiff-backup <version>""".format(
                rc=safestr.to_str(remote_cmd),
                co=safestr.to_str(
                    remote_cmd.replace(b"--server", b"--version"))),
            log.ERROR)
        return False

    try:
        remote_api_version = conn.Globals.get('api_version')
    except KeyError:  # the remote side doesn't know yet about api_version
        # Only version 2.0 could _not_ understand api_version but still be
        # compatible with version 200 of the API
        if (remote_version.startswith("2.0.")
                and (Globals.api_version["actual"]
                     or Globals.api_version["min"]) == 200):
            Globals.api_version["actual"] == 200
            log.Log("Remote version {rv} doesn't know about API "
                    "versions but should be compatible with 200".format(
                        rv=remote_version), log.NOTE)
            return True
        else:
            log.Log(
                "Remote version {rv} isn't compatible with local "
                "API version {av}".format(
                    rv=remote_version,
                    av=(Globals.api_version["actual"]
                        or Globals.api_version["min"])), log.ERROR)
            return False

    # servers don't validate the API version, client does
    if Globals.server:
        return True

    # Now compare the remote and local API versions and agree actual version

    # if client and server have no common API version
    if (min(remote_api_version["max"], Globals.api_version["max"])
            < max(remote_api_version["min"], Globals.api_version["min"])):
        log.Log(
            """Local and remote rdiff-backup have no common API version:
Remote API version for {rv} must be between min {ri} and max {ra}.
Local API version for {lv} must be between min {li} and max {la}.
Please make sure you have compatible versions of rdiff-backup""".format(
                rv=remote_version,
                ri=remote_api_version["min"],
                ra=remote_api_version["max"],
                lv=Globals.version,
                li=Globals.api_version["min"],
                la=Globals.api_version["max"]), log.ERROR)
        return False
    # is there an actual API version and does it fit the other side?
    if Globals.api_version["actual"]:
        if (Globals.api_version["actual"] >= remote_api_version["min"]
                and Globals.api_version["actual"] <= remote_api_version["max"]):
            conn.Globals.set_api_version(Globals.api_version["actual"])
            log.Log("API version agreed to be actual {av} "
                    "with command {co}".format(
                        av=Globals.api_version["actual"], co=remote_cmd),
                    log.INFO)
            return True
        else:  # the actual version doesn't fit the other side
            log.Log(
                "Remote rdiff-backup doesn't accept the API version "
                "explicitly set locally to {av}. "
                "It should be between min {ri} and max {ra}. "
                "Use '--api-version' to set another API version".format(
                    av=Globals.api_version["actual"],
                    ri=remote_api_version["min"],
                    ra=remote_api_version["max"]), log.ERROR)
            return False
    else:
        # use the default local value but make make sure it's between min
        # and max on the remote side, while using the highest acceptable value:
        actual_api_version = max(remote_api_version["min"],
                                 min(remote_api_version["max"],
                                     Globals.api_version["default"]))
        Globals.api_version["actual"] = actual_api_version
        conn.Globals.set_api_version(actual_api_version)
        log.Log("API version agreed to be {av} with command {co}".format(
            av=actual_api_version, co=remote_cmd), log.INFO)
        return True


def _init_connection_routing(conn, conn_number, remote_cmd):
    """Called by _init_connection, establish routing, conn dict"""
    Globals.connection_dict[conn_number] = conn

    conn.SetConnections.init_connection_remote(conn_number)
    for other_remote_conn in Globals.connections[1:]:
        conn.SetConnections.add_redirected_conn(other_remote_conn.conn_number)
        other_remote_conn.SetConnections.add_redirected_conn(conn_number)

    Globals.connections.append(conn)
    __conn_remote_cmds.append(remote_cmd)


def _init_connection_settings(conn):
    """Tell new conn about log settings and updated globals"""
    conn.log.Log.setverbosity(log.Log.verbosity)
    conn.log.Log.setterm_verbosity(log.Log.term_verbosity)
    for setting_name in Globals.changed_settings:
        conn.Globals.set_local(setting_name, Globals.get(setting_name))


def _test_connection(conn_number, rp):
    """Test connection if it is not None, else skip. Returns True/False
    depending on test results."""
    # the function doesn't use the log functions because it might not have
    # an error or log file to use.
    print("Testing server started by: ", __conn_remote_cmds[conn_number])
    conn = Globals.connections[conn_number]
    if conn is None:
        sys.stderr.write("- Connection failed, server tests skipped\n")
        return False
    # FIXME the tests don't sound right, the path given needs to pre-exist
    # on Windows but not on Linux? What are we exactly testing here?
    try:
        assert conn.Globals.get('current_time') is None
        assert type(conn.os.listdir(rp.path)) is list
    except BaseException as exc:
        sys.stderr.write("- Server tests failed due to {exc}\n".format(exc=exc))
        return False
    else:
        print("- Server OK")
        return True
