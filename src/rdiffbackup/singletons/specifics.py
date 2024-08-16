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
server = None

# uid and gid of the owner of the rdiff-backup process.  This can
# vary depending on the connection.
try:
    process_uid = os.getuid()
    process_gid = os.getgid()
    process_groups = [process_gid] + os.getgroups()
except AttributeError:
    process_uid = 0
    process_gid = 0
    process_groups = [0]

# If true, change the permissions of unwriteable mirror files
# (such as directories) so that they can be written, and then
# change them back.  This defaults to 1 just in case the process
# is not running as root (root doesn't need to change
# permissions).
change_mirror_perms = process_uid != 0

# If true, try to reset the atimes of the source partition.
preserve_atime = None

# The following three attributes represent whether extended attributes
# are supported.  If eas_active is true, then the current session
# supports them.  If eas_write is true, then the extended attributes
# should also be written to the destination side.  Finally, eas_conn
# is relative to the current connection, and should be true iff that
# particular connection supports extended attributes.
eas_active = None
eas_write = None
eas_conn = None

# The following settings are like the extended attribute settings, but
# apply to access control lists instead.
acls_active = None
acls_write = None
acls_conn = None

# Like the above, but applies to support of Windows
# access control lists.
win_acls_active = None
win_acls_write = None
win_acls_conn = None

# Like above two setting groups, but applies to support of Mac OS X
# style resource forks.
resource_forks_active = None
resource_forks_write = None
resource_forks_conn = None

# Like the above, but applies to MacOS Carbon Finder creator/type info.
# As of 1.0.2 this has defaulted to off because of bugs
carbonfile_active = None
carbonfile_write = None
carbonfile_conn = None

# This will be set as soon as the LocalConnection class loads
local_connection = None

# All connections should be added to the following list, so
# further global changes can be propagated to the remote systems.
# The first element should be Globals.local_connection.  For a
# server, the second is the connection to the client.
connections = []

# Each process should have a connection number unique to the
# session.  The client has connection number 0.
connection_number = 0

# Dictionary pairing connection numbers with connections.  Set in
# SetConnections for all connections.
connection_dict = {}

# True if the script is the end that writes to the increment and
# mirror directories.  True for purely local sessions.
isbackup_writer = None  # compat201

# Connection of the backup writer
backup_writer = None  # compat201

# When backing up, issource should be true on the reader and isdest on
# the writer.  When restoring, issource should be true on the mirror
# and isdest should be true on the target.
issource = None
isdest = None

# This list is used by the set function below.  When a new
# connection is created with init_connection, its Globals class
# will match this one for all the variables mentioned in this
# list.
changed_settings = []

# chars_to_quote is a string whose characters should be quoted.  It
# should be set if certain characters in filenames on the source side
# should be escaped (see locations.map.filenames for more info).
chars_to_quote = None
chars_to_quote_regexp = None
chars_to_quote_unregexp = None
# the quoting character is used to mark quoted characters
quoting_char = b";"

# evaluate if DOS device names (AUX, PRN, CON, NUL, COM, LPT) should be quoted
# or spaces at the end of file and directory names.
# The default is based on the operating system type (nt or posix).
escape_dos_devices = os.name == "nt"
escape_trailing_spaces = os.name == "nt"

# If true, the timestamps use the following format: "2008-09-01T04-49-04-07-00"
# (instead of "2008-09-01T04:49:04-07:00"). This creates timestamps which
# don't need to be escaped on Windows.
use_compatible_timestamps = 0

# Normally there shouldn't be any case of duplicate timestamp but it seems
# we had the issue at some point in time, hence we need the flag to allow
# users to clean up their repository. The default is to abort on such cases.

allow_duplicate_timestamps = False

# If true, then hardlinks will be preserved to mirror and recorded
# in the increments directory.  There is also a difference here
# between None and 0.  When restoring, None or 1 means to preserve
# hardlinks iff can find a hardlink dictionary.  0 means ignore
# hardlink information regardless.
preserve_hardlinks = 1

# If this is false, then rdiff-backup will not compress any
# increments.  Default is to compress based on regexp below.
compression = 1

# If true, filelists and directory statistics will be split on
# nulls instead of newlines.
null_separator = None

# On the backup writer connection, holds the root incrementing branch
# object.  Access is provided to increment error counts.
ITRB = None

# If set, a file will be marked as changed if its inode changes.  See
# the man page under --no-compare-inode for more information.
compare_inode = 1

# If set, directories can be fsync'd just like normal files, to
# guarantee that any changes have been comitted to disk.
fsync_directories = None

# If set, exit with error instead of dropping ACLs or ACL entries.
never_drop_acls = None

# Apply this mask to permissions before chmoding.  (Set to 0777 to
# prevent highbit permissions on systems which don't support them.)
permission_mask = 0o7777

# If true, symlinks permissions are affected by the process umask, and
# we should change the umask when creating them in order to preserve
# the original permissions
symlink_perms = None

# If set, the path that should be used instead of the default Python
# tempfile.tempdir value on remote connections
remote_tempdir = None


# @API(get, 200)
def get(name):
    """Return the value of something in this module"""
    return globals()[name]


# @API(set_api_version, 201)
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
