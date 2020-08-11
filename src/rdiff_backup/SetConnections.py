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
from .log import Log
from . import Globals, connection, rpath

# This is the schema that determines how rdiff-backup will open a
# pipe to the remote system.  If the file is given as A::B, %s will
# be substituted with A in the schema.
__cmd_schema = b'ssh -C %s rdiff-backup --server'
__cmd_schema_no_compress = b'ssh %s rdiff-backup --server'

# This is a list of remote commands used to start the connections.
# The first is None because it is the local connection.
__conn_remote_cmds = [None]


class SetConnectionsException(Exception):
    pass


def get_cmd_pairs(arglist, remote_schema=None, remote_cmd=None):
    """Map the given file descriptions into command pairs

    Command pairs are tuples cmdpair with length 2.  cmdpair[0] is
    None iff it describes a local path, and cmdpair[1] is the path.

    """
    global __cmd_schema
    if remote_schema:
        __cmd_schema = remote_schema
    elif not Globals.ssh_compression:
        __cmd_schema = __cmd_schema_no_compress

    if Globals.remote_tempdir:
        __cmd_schema += (b" --tempdir=" + Globals.remote_tempdir)

    if not arglist:
        return []
    desc_pairs = list(map(_parse_file_desc, arglist))

    if [x for x in desc_pairs if x[0]]:  # True if any host_info found
        if remote_cmd:
            Log.FatalError("The --remote-cmd flag is not compatible "
                           "with remote file descriptions.")
    elif remote_schema:
        Log("Remote schema option ignored - no remote file "
            "descriptions.", 2)
    cmd_pairs = list(map(_desc2cmd_pairs, desc_pairs))
    if remote_cmd:  # last file description gets remote_cmd
        cmd_pairs[-1] = (remote_cmd, cmd_pairs[-1][1])
    return cmd_pairs


def cmdpair2rp(cmd_pair):
    """Return normalized RPath from cmd_pair (remote_cmd, filename)"""
    cmd, filename = cmd_pair
    if cmd:
        conn = _init_connection(cmd)
    else:
        conn = Globals.local_connection
    return rpath.RPath(conn, filename).normalize()


def _desc2cmd_pairs(desc_pair):
    """Return pair (remote_cmd, filename) from desc_pair"""
    host_info, filename = desc_pair
    if not host_info:
        return (None, filename)
    else:
        return (_fill_schema(host_info), filename)


def _parse_file_desc(file_desc):
    """Parse file description returning pair (host_info, filename)

    In other words, bescoto@folly.stanford.edu::/usr/bin/ls =>
    ("bescoto@folly.stanford.edu", "/usr/bin/ls").  The
    complication is to allow for quoting of : by a \\.  If the
    string is not separated by :, then the host_info is None.

    """

    # paths and similar objects must always be bytes
    file_desc = os.fsencode(file_desc)
    # match double colon not preceded by an odd number of backslashes
    file_match = re.fullmatch(rb"^(?P<host>.*[^\\](?:\\\\)*)::(?P<path>.*)$",
                              file_desc)
    if file_match:
        file_host = file_match.group("host")
        # According to description, the backslashes must be unquoted, i.e.
        # double backslashes replaced by single ones, and single ones removed.
        # Hence we split along double ones, remove single ones in each element,
        # and join back with a single backslash.
        file_host = b'\\'.join(
            [x.replace(b'\\', b'') for x in re.split(rb'\\\\', file_host) if x])
        file_path = file_match.group("path")
    else:
        if re.match(rb"^::", file_desc):
            raise SetConnectionsException("No file host in '%s'" % file_desc)
        file_host = None
        file_path = file_desc

    # make sure paths under Windows use / instead of \
    if os.path.altsep:  # only Windows has an alternative separator for paths
        file_path = file_path.replace(os.fsencode(os.path.sep), b'/')

    if not file_path:
        raise SetConnectionsException("No file path in '%s'" % file_desc)

    return (file_host, file_path)


def _fill_schema(host_info):
    """Fills host_info into the schema and returns remote command"""
    try:
        return __cmd_schema % host_info
    except TypeError:
        Log.FatalError("Invalid remote schema:\n\n%s\n" % _safe_str(__cmd_schema))


def _init_connection(remote_cmd):
    """Run remote_cmd, register connection, and then return it

    If remote_cmd is None, then the local connection will be
    returned.  This also updates some settings on the remote side,
    like global settings, its connection number, and verbosity.

    """
    if not remote_cmd:
        return Globals.local_connection

    Log("Executing %s" % _safe_str(remote_cmd), 4)
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
    except OSError:
        (stdin, stdout) = (None, None)
    conn_number = len(Globals.connections)
    conn = connection.PipeConnection(stdout, stdin, conn_number)

    _check_connection_version(conn, remote_cmd)
    Log("Registering connection %d" % conn_number, 7)
    _init_connection_routing(conn, conn_number, remote_cmd)
    _init_connection_settings(conn)
    return conn


def _check_connection_version(conn, remote_cmd):
    """Log warning if connection has different version"""
    try:
        remote_version = conn.Globals.get('version')
    except connection.ConnectionError as exception:
        Log.FatalError("""%s

Couldn't start up the remote connection by executing

    %s

Remember that, under the default settings, rdiff-backup must be
installed in the PATH on the remote system.  See the man page for more
information on this.  This message may also be displayed if the remote
version of rdiff-backup is quite different from the local version (%s).""" %
                       (exception, _safe_str(remote_cmd), Globals.version))
    except OverflowError:
        Log.FatalError(
            """Integer overflow while attempting to establish the
remote connection by executing

    %s

Please make sure that nothing is printed (e.g., by your login shell) when this
command executes. Try running this command:

    %s

which should only print out the text: rdiff-backup <version>""" %
            (_safe_str(remote_cmd),
             _safe_str(remote_cmd.replace(b"--server", b"--version"))))

    if remote_version != Globals.version:
        Log(
            "Warning: Local version %s does not match remote version %s." %
            (Globals.version, remote_version), 2)


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
    conn.log.Log.setverbosity(Log.verbosity)
    conn.log.Log.setterm_verbosity(Log.term_verbosity)
    for setting_name in Globals.changed_settings:
        conn.Globals.set(setting_name, Globals.get(setting_name))


def init_connection_remote(conn_number):
    """Run on server side to tell self that have given conn_number"""
    Globals.connection_number = conn_number
    Globals.local_connection.conn_number = conn_number
    Globals.connection_dict[0] = Globals.connections[1]
    Globals.connection_dict[conn_number] = Globals.local_connection


def add_redirected_conn(conn_number):
    """Run on server side - tell about redirected connection"""
    Globals.connection_dict[conn_number] = \
        connection.RedirectedConnection(conn_number)


def UpdateGlobal(setting_name, val):
    """Update value of global variable across all connections"""
    for conn in Globals.connections:
        conn.Globals.set(setting_name, val)


def BackupInitConnections(reading_conn, writing_conn):
    """Backup specific connection initialization"""
    reading_conn.Globals.set("isbackup_reader", 1)
    writing_conn.Globals.set("isbackup_writer", 1)
    UpdateGlobal("backup_reader", reading_conn)
    UpdateGlobal("backup_writer", writing_conn)


def CloseConnections():
    """Close all connections.  Run by client"""
    assert not Globals.server
    for conn in Globals.connections:
        conn.quit()
    del Globals.connections[1:]  # Only leave local connection
    Globals.connection_dict = {0: Globals.local_connection}
    Globals.backup_reader = Globals.isbackup_reader = \
        Globals.backup_writer = Globals.isbackup_writer = None


def TestConnections(rpaths):
    """Test connections, printing results"""
    if len(Globals.connections) == 1:
        print("No remote connections specified")
    else:
        assert len(Globals.connections) == len(rpaths) + 1, \
            "All %d parameters must be remote of the form 'server::path'." % \
            len(rpaths)
        for i in range(1, len(Globals.connections)):
            _test_connection(i, rpaths[i - 1])


def _test_connection(conn_number, rp):
    """Test connection.  conn_number 0 is the local connection"""
    print("Testing server started by: ", __conn_remote_cmds[conn_number])
    conn = Globals.connections[conn_number]
    try:
        assert conn.Globals.get('current_time') is None
        try:
            assert type(conn.os.getuid()) is int
        except AttributeError:  # Windows doesn't support os.getuid()
            assert type(conn.os.listdir(rp.path)) is list
        version = conn.Globals.get('version')
    except BaseException:
        sys.stderr.write("Server tests failed\n")
        raise
    if not version == Globals.version:
        print("""Server may work, but there is a version mismatch:
Local version: %s
Remote version: %s

In general, an attempt is made to guarantee compatibility only between
different minor versions of the same stable series.  For instance, you
should expect 0.12.4 and 0.12.7 to be compatible, but not 0.12.7
and 0.13.3, nor 0.13.2 and 0.13.4.
""" % (Globals.version, version))
    else:
        print("Server OK")


def _safe_str(cmd):
    """Transform bytes into string without risk of conversion error"""
    if isinstance(cmd, str):
        return cmd
    else:
        return str(cmd, errors='replace')
