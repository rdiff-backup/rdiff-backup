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
"""
A variety of variables which can have different values across connections.
They are specific to each instance of rdiff-backup involved.
"""

import os
import yaml
from importlib import metadata
from rdiff_backup import log

# The current version of rdiff-backup
# Get it from package info or fall back to DEV version.
try:
    version = metadata.version("rdiff-backup")
except metadata.PackageNotFoundError:
    version = "DEV.no.metadata"

# The default, supported (min/max) and actual API versions.
# An actual value of 0 means that the default version is to be used or whatever
# makes the connection work within the min-max range, depending on the
# API versions supported by the remote connection.
api_version = {"default": 201, "min": 201, "max": 201, "actual": 0}
# Allow overwrite from the environment variable RDIFF_BACKUP_API_VERSION
# we don't do a lot of error handling because it's more of a dev option
api_version.update(yaml.safe_load(os.environ.get("RDIFF_BACKUP_API_VERSION", "{}")))

# True if script is running as a server
server = False

# uid and gid of the owner of the rdiff-backup process.  This can
# vary depending on the connection.
try:
    process_uid = os.getuid()
    process_groups = set(os.getgroups())
except AttributeError:
    process_uid = 0
    process_groups = {0}

# The following three attributes represent whether extended attributes
# are supported.  If eas_active is true, then the current session
# supports them.  If eas_write is true, then the extended attributes
# should also be written to the destination side.  Finally, eas_conn
# is relative to the current connection, and should be true iff that
# particular connection supports extended attributes.
eas_conn = None
acls_conn = None
win_acls_conn = None
resource_forks_conn = None
carbonfile_conn = None

# This will be set as soon as the LocalConnection class loads
local_connection = None

# All connections should be added to the following list, so
# further global changes can be propagated to the remote systems.
# The first element should be specifics.local_connection.  For a
# server, the second is the connection to the client.
connections = []

# Dictionary pairing connection numbers with connections.  Set in
# SetConnections for all connections.
connection_dict = {}

# True if the script is the end that writes to the increment and
# mirror directories.  True for purely local sessions.
is_backup_writer = None  # compat201


# @API(get, 300)
def get(setting_name):
    """
    Return the value of a specific setting
    """
    return globals()[setting_name]


# @API(set, 300)
def set(setting_name, value):
    """
    Set the value of a specific setting
    """
    globals()[setting_name] = value


# @API(set_api_version, 300)
def set_api_version(val):
    """sets the actual API version after having verified that the new
    value is an integer between mix and max values."""
    try:
        intval = int(val)
    except ValueError:
        log.Log.FatalError(
            "API version must be set to an integer, "
            "received value {va} instead.".format(va=val)
        )
    if intval < api_version["min"] or intval > api_version["max"]:
        log.Log.FatalError(
            "API version {av} must be between {mi} and {ma}.".format(
                av=val, mi=api_version["min"], ma=api_version["max"]
            )
        )
    api_version["actual"] = intval


def get_api_version():
    """Return the actual API version, either set explicitly or the default
    one"""
    return api_version["actual"] or api_version["default"]
