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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
# USA

"""Hold a variety of constants usually set at initialization."""

import re, os


# The current version of rdiff-backup
version = "$version"

# If this is set, use this value in seconds as the current time
# instead of reading it from the clock.
current_time = None

# This determines how many bytes to read at a time when copying
blocksize = 32768

# This is used by the BufferedRead class to determine how many
# bytes to request from the underlying file per read().  Larger
# values may save on connection overhead and latency.
conn_bufsize = 98304

# This is used in rorpiter.CacheIndexable.  The number represents the
# number of rpaths which may be stuck in buffers when moving over a
# remote connection.
pipeline_max_length = 500

# True if script is running as a server
server = None

# uid and gid of the owner of the rdiff-backup process.  This can
# vary depending on the connection.
process_uid = os.getuid()
process_gid = os.getgid()
process_groups = os.getgroups()

# If true, when copying attributes, also change target's uid/gid
change_ownership = None

# If true, change the permissions of unwriteable mirror files
# (such as directories) so that they can be written, and then
# change them back.  This defaults to 1 just in case the process
# is not running as root (root doesn't need to change
# permissions).
change_mirror_perms = (process_uid != 0)

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

# Like above two setting groups, but applies to support of Mac OS X
# style resource forks.
resource_forks_active = None
resource_forks_write = None
resource_forks_conn = None

# Like the above, but applies to MacOS Carbon Finder creator/type info.
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

# True if the script is the end that reads the source directory
# for backups.  It is true for purely local sessions.
isbackup_reader = None

# Connection of the real backup reader (for which isbackup_reader
# is true)
backup_reader = None

# True if the script is the end that writes to the increment and
# mirror directories.  True for purely local sessions.
isbackup_writer = None

# Connection of the backup writer
backup_writer = None

# Connection of the client
client_conn = None

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

# The RPath or QuotedRPath of the rdiff-backup-data directory.
rbdir = None

# chars_to_quote is a string whose characters should be quoted.  It
# should be true if certain characters in filenames on the source side
# should be escaped (see FilenameMapping for more info).
chars_to_quote = None
quoting_char = ';'

# If true, emit output intended to be easily readable by a
# computer.  False means output is intended for humans.
parsable_output = None

# If true, then hardlinks will be preserved to mirror and recorded
# in the increments directory.  There is also a difference here
# between None and 0.  When restoring, None or 1 means to preserve
# hardlinks iff can find a hardlink dictionary.  0 means ignore
# hardlink information regardless.
preserve_hardlinks = 1

# If this is false, then rdiff-backup will not compress any
# increments.  Default is to compress based on regexp below.
compression = 1

# Increments based on files whose names match this
# case-insensitive regular expression won't be compressed (applies
# to .snapshots and .diffs).  The second below will be the
# compiled version of the first.
no_compression_regexp_string = "(?i).*\\.(gz|z|bz|bz2|tgz|zip|rpm|deb|" \
						"jpg|gif|png|jp2|mp3|ogg|avi|wmv|mpeg|mpg|rm|mov|flac|shn)$"
no_compression_regexp = None

# If true, filelists and directory statistics will be split on
# nulls instead of newlines.
null_separator = None

# Determines whether or not ssh will be run with the -C switch
ssh_compression = 1

# If true, print statistics after successful backup
print_statistics = None

# Controls whether file_statistics file is written in
# rdiff-backup-data dir.  These can sometimes take up a lot of space.
file_statistics = 1

# On the writer connection, the following will be set to the mirror
# Select iterator.
select_mirror = None

# On the backup writer connection, holds the root incrementing branch
# object.  Access is provided to increment error counts.
ITRB = None

# security_level has 4 values and controls which requests from remote
# systems will be honored.  "all" means anything goes. "read-only"
# means that the requests must not write to disk.  "update-only" means
# that requests shouldn't destructively update the disk (but normal
# incremental updates are OK).  "minimal" means only listen to a few
# basic requests.
security_level = "all"

# If this is set, it indicates that the remote connection should only
# deal with paths inside of restrict_path.
restrict_path = None

# If set, a file will be marked as changed if its inode changes.  See
# the man page under --no-compare-inode for more information.
compare_inode = 1

# If set, directories can be fsync'd just like normal files, to
# guarantee that any changes have been committed to disk.
fsync_directories = 1

# If set, exit with error instead of dropping ACLs or ACL entries.
never_drop_acls = None


def get(name):
	"""Return the value of something in this module"""
	return globals()[name]

def is_not_None(name):
	"""Returns true if value is not None"""
	return globals()[name] is not None

def set(name, val):
	"""Set the value of something in this module

	Use this instead of writing the values directly if the setting
	matters to remote sides.  This function updates the
	changed_settings list, so other connections know to copy the
	changes.

	"""
	changed_settings.append(name)
	globals()[name] = val

def set_local(name, val):
	"""Like set above, but only set current connection"""
	globals()[name] = val

def set_integer(name, val):
	"""Like set, but make sure val is an integer"""
	try: intval = int(val)
	except ValueError:
		Log.FatalError("Variable %s must be set to an integer -\n"
					   "received %s instead." % (name, val))
	set(name, intval)

def set_float(name, val, min = None, max = None, inclusive = 1):
	"""Like set, but make sure val is float within given bounds"""
	def error():
		s = "Variable %s must be set to a float" % (name,)
		if min is not None and max is not None:
			s += " between %s and %s " % (min, max)
			if inclusive: s += "inclusive"
			else: s += "not inclusive"
		elif min is not None or max is not None:
			if inclusive: inclusive_string = "or equal to "
			else: inclusive_string = ""
			if min is not None:
				s += " greater than %s%s" % (inclusive_string, min)
			else: s+= " less than %s%s" % (inclusive_string, max)
		Log.FatalError(s)

	try: f = float(val)
	except ValueError: error()
	if min is not None:
		if inclusive and f < min: error()
		elif not inclusive and f <= min: error()
	if max is not None:
		if inclusive and f > max: error()
		elif not inclusive and f >= max: error()
	set(name, f)

def get_dict_val(name, key):
	"""Return val from dictionary in this class"""
	return globals()[name][key]

def set_dict_val(name, key, val):
	"""Set value for dictionary in this class"""
	globals()[name][key] = val

def postset_regexp(name, re_string, flags = None):
	"""Compile re_string on all existing connections, set to name"""
	for conn in connections:
		conn.Globals.postset_regexp_local(name, re_string, flags)

def postset_regexp_local(name, re_string, flags):
	"""Set name to compiled re_string locally"""
	if flags: globals()[name] = re.compile(re_string, flags)
	else: globals()[name] = re.compile(re_string)


