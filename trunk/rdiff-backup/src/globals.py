import re, os

#######################################################################
#
# globals - aggregate some configuration options
#

class Globals:

	# The current version of rdiff-backup
	version = "0.7.1"
	
	# If this is set, use this value in seconds as the current time
	# instead of reading it from the clock.
	current_time = None

	# This determines how many bytes to read at a time when copying
	blocksize = 32768

	# This is used by the BufferedRead class to determine how many
	# bytes to request from the underlying file per read().  Larger
	# values may save on connection overhead and latency.
	conn_bufsize = 4096

	# True if script is running as a server
	server = None

	# uid and gid of the owner of the rdiff-backup process.  This can
	# vary depending on the connection.
	process_uid = os.getuid()
	process_gid = os.getgid()

	# If true, when copying attributes, also change target's uid/gid
	change_ownership = None

	# If true, change the permissions of unwriteable mirror files
	# (such as directories) so that they can be written, and then
	# change them back.
	change_mirror_perms = 1

	# If true, temporarily change permissions of unreadable files in
	# the source directory to make sure we can read all files.
	change_source_perms = None

	# If true, try to reset the atimes of the source partition.
	preserve_atime = None

	# This is a list of compiled regular expressions.  If one of them
	# matches a file in the source area, do not process that file.
	exclude_regexps = []

	# Another list of compiled regexps; this time the file is excluded
	# if it matches something in the destination area.
	exclude_mirror_regexps = []

	# If this is true, rdiff-backup will exclude any dev files it
	# sees, in the same way it excludes files matching the exclude
	# regexps.
	exclude_device_files = None

	# This will be set as soon as the LocalConnection class loads
	local_connection = None

	# If this is true, instead of processing whole directory, just
	# examine files read in from standard input.
	include_from_stdin = None

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

	# This list is used by the set function below.  When a new
	# connection is created with init_connection, its Globals class
	# will match this one for all the variables mentioned in this
	# list.
	changed_settings = []

	# rdiff-backup will try to checkpoint its state every
	# checkpoint_interval seconds.  Then when resuming, at most this
	# amount of time is lost.
	checkpoint_interval = 20

	# The RPath of the rdiff-backup-data directory.
	rbdir = None

	# Indicates if a resume or a lack of resume is forced.  This
	# should be None for the default.  0 means don't resume, and 1
	# means resume.
	resume = None

	# If there has been an aborted backup fewer than this many seconds
	# ago, attempt to resume it where it left off instead of starting
	# a new one.
	resume_window = 7200

	# This string is used when recognizing and creating time strings.
	# If the time_separator is ":", then W3 datetime strings like
	# 2001-12-07T04:22:01-07:00 are produced.  It can be set to "_" to
	# make filenames that don't contain colons, which aren't allowed
	# under MS windows NT.
	time_separator = ":"

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
	# to .snapshots and .diffs).  The second below is the compiled
	# version of the first.
	no_compression_regexp_string = ".*\\.(gz|z|bz|bz2|tgz|zip|rpm|deb|" \
							"jpg|gif|png|mp3|ogg|avi|wmv|mpeg|mpg|rm|mov)$"
	no_compression_regexp = None

	def get(cls, name):
		"""Return the value of something in this class"""
		return cls.__dict__[name]
	get = classmethod(get)

	def set(cls, name, val):
		"""Set the value of something in this class

		Use this instead of writing the values directly if the setting
		matters to remote sides.  This function updates the
		changed_settings list, so other connections know to copy the
		changes.

		"""
		cls.changed_settings.append(name)
		cls.__dict__[name] = val
	set = classmethod(set)

	def set_integer(cls, name, val):
		"""Like set, but make sure val is an integer"""
		try: intval = int(val)
		except ValueError:
			Log.FatalError("Variable %s must be set to an integer -\n"
						   "received %s instead." % (name, val))
		cls.set(name, intval)
	set_integer = classmethod(set_integer)

	def get_dict_val(cls, name, key):
		"""Return val from dictionary in this class"""
		return cls.__dict__[name][key]
	get_dict_val = classmethod(get_dict_val)

	def set_dict_val(cls, name, key, val):
		"""Set value for dictionary in this class"""
		cls.__dict__[name][key] = val
	set_dict_val = classmethod(set_dict_val)

	def add_regexp(cls, regstr, mirror=None):
		"""Add a regular expression to the exclude list"""
		for conn in Globals.connections:
			conn.Globals.add_regexp_local(regstr, mirror)
	add_regexp = classmethod(add_regexp)

	def add_regexp_local(cls, regstr, mirror):
		"""Add the regex only to the local Globals class"""
		compiled = re.compile(regstr)
		if mirror: Globals.exclude_mirror_regexps.append(compiled)
		else: Globals.exclude_regexps.append(compiled)
	add_regexp_local = classmethod(add_regexp_local)

	def postset_regexp(cls, name, re_string, flags = None):
		"""Compile re_string on all existing connections, set to name"""
		for conn in Globals.connections:
			conn.Globals.postset_regexp_local(name, re_string, flags)
	postset_regexp = classmethod(postset_regexp)

	def postset_regexp_local(cls, name, re_string, flags):
		"""Set name to compiled re_string locally"""
		if flags: cls.__dict__[name] = re.compile(re_string, flags)
		else: cls.__dict__[name] = re.compile(re_string)
	postset_regexp_local = classmethod(postset_regexp_local)
