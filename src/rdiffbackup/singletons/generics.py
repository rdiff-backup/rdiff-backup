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
A variety of variables which need to have the same value across connections.
They are generic to all instances of rdiff-backup involved.
"""

import os
import yaml
from importlib import metadata
from rdiff_backup import log

# If true, when copying attributes, also change target's uid/gid
change_ownership = None

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

# Fsync everything by default. Use --no-fsync only if you really know what you are doing
# Not having the data written to disk may render your backup unusable in case of FS failure.
# Using --no-fsync disables only fsync of files during backup and sync() system call upon backup finish
# and pre-regress
do_fsync = True

# This is the current time, either as integer (epoch) or formatted string.
# It is set once at the beginning of the program and defines the backup's
# date and time
current_time = None
current_time_string = None


# @API(get, 200)
def get(name):
    """Return the value of something in this module"""
    return globals()[name]


def set(name, val):
    """
    Set the value of something in this module on this connection and, delayed,
    on all others

    Use this instead of writing the values directly if the setting
    matters to remote sides.  This function updates the
    changed_settings list, so other connections know to copy the changes
    during connection initiation. After the connection has been initiated,
    use C<set_all> instead.
    """
    changed_settings.append(name)
    globals()[name] = val


def set_all(setting_name, value):
    """
    Sets the setting given to the value on all connections

    Where set relies on each connection to grab the value at a later stage,
    set_all forces the value on all connections at once.
    """
    for conn in connection_dict.values():
        conn.Globals.set_local(setting_name, value)


# @API(set_local, 200)
def set_local(name, val):
    """Like set above, but only set current connection"""
    globals()[name] = val
