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
from rdiffbackup.singletons import specifics

# If true, when copying attributes, also change target's uid/gid
change_ownership = None

# If true, try to reset the atimes of the source partition.
preserve_atime = None

# The following three attributes represent whether extended attributes
# are supported.
# If eas_active is true, then the current session supports them.
# If eas_write is true, then the extended attributes should also be written to
# the destination side.
# Finally, eas_conn is relative to the current connection, and should be true iff
# that particular connection supports extended attributes.
# This last variable is in the specifics.
eas_active = None
eas_write = None

# The following settings are like the extended attribute settings, but
# apply to access control lists instead.
acls_active = None
acls_write = None

# Like the above, but applies to support of Windows access control lists.
win_acls_active = None
win_acls_write = None

# Like above two setting groups, but applies to support of Mac OS X
# style resource forks.
resource_forks_active = None
resource_forks_write = None

# Like the above, but applies to MacOS Carbon Finder creator/type info.
# As of 1.0.2 this has defaulted to off because of bugs
carbonfile_active = None
carbonfile_write = None

# Connection of the backup writer
backup_writer = None  # compat201

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


def get(setting_name):
    """Return the value of a setting in this module"""
    return globals()[setting_name]


# This list is used by the set function below.  When a new
# connection is created with init_connection, the variables
# listed here will be dispatched to the connection's generics.
changed_settings = []


def set(setting_name, value):
    """
    Set the value of something in this module on this connection and,
    potentially delayed, on all others.
    """
    # we always save generic values here, so that they can be later transferred
    changed_settings.append(setting_name)
    # if there are no connections yet, only set locally
    if specifics.connection_dict:
        for conn in specifics.connection_dict.values():
            conn.generics.set_local(setting_name, value)
    else:
        globals()[setting_name] = value


def dispatch_settings(conn):
    """
    A function to dispatch all generic settings remembered but not yet dispatched
    to the (assumed new) given connection.
    """
    for setting_name in changed_settings:
        conn.generics.set_local(setting_name, get(setting_name))


# @API(set_local, 200)
def set_local(setting_name, value):
    """Like set above, but only set current connection"""
    globals()[setting_name] = value
