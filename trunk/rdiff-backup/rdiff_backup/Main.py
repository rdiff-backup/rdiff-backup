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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
# USA

"""Start (and end) here - read arguments, set global settings, etc."""

from __future__ import generators
import getopt, sys, re, os
from log import Log, LoggerError, ErrorLog
import Globals, Time, SetConnections, selection, robust, rpath, \
	   manage, backup, connection, restore, FilenameMapping, \
	   Security, Hardlink, regress, C, fs_abilities


action = None
remote_cmd, remote_schema = None, None
force = None
select_opts = []
select_files = []
# These are global because they are set while we are trying to figure
# whether to restore or to backup
restore_root, restore_index, restore_root_set = None, None, 0

def parse_cmdlineoptions(arglist):
	"""Parse argument list and set global preferences"""
	global args, action, force, restore_timestr, remote_cmd, remote_schema
	global remove_older_than_string
	def sel_fl(filename):
		"""Helper function for including/excluding filelists below"""
		try: return open(filename, "r")
		except IOError: Log.FatalError("Error opening file %s" % filename)

	try: optlist, args = getopt.getopt(arglist, "blr:sv:V",
		 ["backup-mode", "calculate-average", "check-destination-dir",
		  "current-time=", "exclude=", "exclude-device-files",
		  "exclude-filelist=", "exclude-filelist-stdin",
		  "exclude-globbing-filelist=", "exclude-mirror=",
		  "exclude-other-filesystems", "exclude-regexp=",
		  "exclude-special-files", "force", "include=",
		  "include-filelist=", "include-filelist-stdin",
		  "include-globbing-filelist=", "include-regexp=",
		  "list-at-time=", "list-changed-since=", "list-increments",
		  "no-compare-inode", "no-compression",
		  "no-compression-regexp=", "no-file-statistics",
		  "no-hard-links", "null-separator",
		  "override-chars-to-quote=", "parsable-output",
		  "print-statistics", "remote-cmd=", "remote-schema=",
		  "remove-older-than=", "restore-as-of=", "restrict=",
		  "restrict-read-only=", "restrict-update-only=", "server",
		  "ssh-no-compression", "terminal-verbosity=", "test-server",
		  "verbosity=", "version"])
	except getopt.error, e:
		commandline_error("Bad commandline options: %s" % str(e))

	for opt, arg in optlist:
		if opt == "-b" or opt == "--backup-mode": action = "backup"
		elif opt == "--calculate-average": action = "calculate-average"
		elif opt == "--check-destination-dir": action = "check-destination-dir"
		elif opt == "--current-time":
			Globals.set_integer('current_time', arg)
		elif opt == "--exclude": select_opts.append((opt, arg))
		elif opt == "--exclude-device-files": select_opts.append((opt, arg))
		elif opt == "--exclude-filelist":
			select_opts.append((opt, arg))
			select_files.append(sel_fl(arg))
		elif opt == "--exclude-filelist-stdin":
			select_opts.append(("--exclude-filelist", "standard input"))
			select_files.append(sys.stdin)
		elif opt == "--exclude-globbing-filelist":
			select_opts.append((opt, arg))
			select_files.append(sel_fl(arg))
		elif (opt == "--exclude-other-filesystems" or
			  opt == "--exclude-regexp" or
			  opt == "--exclude-special-files"): select_opts.append((opt, arg))
		elif opt == "--force": force = 1
		elif opt == "--include": select_opts.append((opt, arg))
		elif opt == "--include-filelist":
			select_opts.append((opt, arg))
			select_files.append(sel_fl(arg))
		elif opt == "--include-filelist-stdin":
			select_opts.append(("--include-filelist", "standard input"))
			select_files.append(sys.stdin)
		elif opt == "--include-globbing-filelist":
			select_opts.append((opt, arg))
			select_files.append(sel_fl(arg))
		elif opt == "--include-regexp": select_opts.append((opt, arg))
		elif opt == "--list-at-time":
			restore_timestr, action = arg, "list-at-time"
		elif opt == "--list-changed-since":
			restore_timestr, action = arg, "list-changed-since"
		elif opt == "-l" or opt == "--list-increments":
			action = "list-increments"
		elif opt == "--no-compare-inode": Globals.set("compare_inode", 0)
		elif opt == "--no-compression": Globals.set("compression", None)
		elif opt == "--no-compression-regexp":
			Globals.set("no_compression_regexp_string", arg)
		elif opt == "--no-file-statistics": Globals.set('file_statistics', 0)
		elif opt == "--no-hard-links": Globals.set('preserve_hardlinks', 0)
		elif opt == "--null-separator": Globals.set("null_separator", 1)
		elif opt == "--override-chars-to-quote":
			Globals.set('chars_to_quote', arg)
		elif opt == "--parsable-output": Globals.set('parsable_output', 1)
		elif opt == "--print-statistics": Globals.set('print_statistics', 1)
		elif opt == "-r" or opt == "--restore-as-of":
			restore_timestr, action = arg, "restore-as-of"
		elif opt == "--remote-cmd": remote_cmd = arg
		elif opt == "--remote-schema": remote_schema = arg
		elif opt == "--remove-older-than":
			remove_older_than_string = arg
			action = "remove-older-than"
		elif opt == "--restrict": Globals.restrict_path = arg
		elif opt == "--restrict-read-only":
			Globals.security_level = "read-only"
			Globals.restrict_path = arg
		elif opt == "--restrict-update-only":
			Globals.security_level = "update-only"
			Globals.restrict_path = arg
		elif opt == "-s" or opt == "--server":
			action = "server"
			Globals.server = 1
		elif opt == "--ssh-no-compression":
			Globals.set('ssh_compression', None)
		elif opt == "--terminal-verbosity": Log.setterm_verbosity(arg)
		elif opt == "--test-server": action = "test-server"
		elif opt == "-V" or opt == "--version":
			print "rdiff-backup " + Globals.version
			sys.exit(0)
		elif opt == "-v" or opt == "--verbosity": Log.setverbosity(arg)
		else: Log.FatalError("Unknown option %s" % opt)

def check_action():
	"""Check to make sure action is compatible with args"""
	global action
	arg_action_dict = {0: ['server'],
					   1: ['list-increments', 'remove-older-than',
						   'list-at-time', 'list-changed-since',
						   'check-destination-dir'],
					   2: ['backup', 'restore', 'restore-as-of']}
	l = len(args)
	if not action: assert l == 2, args # cannot tell backup or restore yet
	elif action == 'calculate-average':
		if l == 0: commandline_error("No arguments given")
	elif l > 2 or action not in arg_action_dict[l]:
		commandline_error("Wrong number of arguments given.  See man page.")

def final_set_action(rps):
	"""If no action set, decide between backup and restore at this point"""
	global action
	if action: return
	assert len(rps) == 2, rps
	if restore_get_root(rps[0]): action = "restore"
	else: action = "backup"

def commandline_error(message):
	sys.stderr.write("Error: %s\n" % message)
	sys.stderr.write("See the rdiff-backup manual page for instructions\n")
	sys.exit(1)

def misc_setup(rps):
	"""Set default change ownership flag, umask, relay regexps"""
	os.umask(077)
	Time.setcurtime(Globals.current_time)
	SetConnections.UpdateGlobal("client_conn", Globals.local_connection)
	Globals.postset_regexp('no_compression_regexp',
						   Globals.no_compression_regexp_string)
	for conn in Globals.connections:
		conn.robust.install_signal_handlers()
		conn.Hardlink.initialize_dictionaries()

def take_action(rps):
	"""Do whatever action says"""
	if action == "server":
		connection.PipeConnection(sys.stdin, sys.stdout).Server()
		sys.exit(0)
	elif action == "backup": Backup(rps[0], rps[1])
	elif action == "restore": Restore(*rps)
	elif action == "restore-as-of": Restore(rps[0], rps[1], 1)
	elif action == "test-server": SetConnections.TestConnections()
	elif action == "list-at-time": ListAtTime(rps[0])
	elif action == "list-changed-since": ListChangedSince(rps[0])
	elif action == "list-increments": ListIncrements(rps[0])
	elif action == "remove-older-than": RemoveOlderThan(rps[0])
	elif action == "calculate-average": CalculateAverage(rps)
	elif action == "check-destination-dir": CheckDest(rps[0])
	else: raise AssertionError("Unknown action " + action)

def cleanup():
	"""Do any last minute cleaning before exiting"""
	Log("Cleaning up", 6)
	if ErrorLog.isopen(): ErrorLog.close()
	Log.close_logfile()
	if not Globals.server: SetConnections.CloseConnections()

def Main(arglist):
	"""Start everything up!"""
	parse_cmdlineoptions(arglist)
	check_action()
	cmdpairs = SetConnections.get_cmd_pairs(args, remote_schema, remote_cmd)
	Security.initialize(action or "mirror", cmdpairs)
	rps = map(SetConnections.cmdpair2rp, cmdpairs)
	final_set_action(rps)
	misc_setup(rps)
	take_action(rps)
	cleanup()


def Backup(rpin, rpout):
	"""Backup, possibly incrementally, src_path to dest_path."""
	SetConnections.BackupInitConnections(rpin.conn, rpout.conn)
	backup_check_dirs(rpin, rpout)
	backup_set_fs_globals(rpin, rpout)
	if Globals.chars_to_quote:
		rpout = FilenameMapping.get_quotedrpath(rpout)
		SetConnections.UpdateGlobal(
			'rbdir', FilenameMapping.get_quotedrpath(Globals.rbdir))
	backup_set_rbdir(rpin, rpout)
	backup_set_select(rpin)
	if prevtime:
		rpout.conn.Main.backup_touch_curmirror_local(rpin, rpout)
		Time.setprevtime(prevtime)
		backup.Mirror_and_increment(rpin, rpout, incdir)
		rpout.conn.Main.backup_remove_curmirror_local()
	else:
		backup.Mirror(rpin, rpout)
		rpout.conn.Main.backup_touch_curmirror_local(rpin, rpout)

def backup_set_select(rpin):
	"""Create Select objects on source connection"""
	rpin.conn.backup.SourceStruct.set_source_select(rpin, select_opts,
													*select_files)

def backup_check_dirs(rpin, rpout):
	"""Make sure in and out dirs exist and are directories"""
	if rpout.lstat() and not rpout.isdir():
		if not force: Log.FatalError("Destination %s exists and is not a "
									 "directory" % rpout.path)
		else:
			Log("Deleting %s" % rpout.path, 3)
			rpout.delete()
	if not rpout.lstat():
		try: rpout.mkdir()
		except os.error:
			Log.FatalError("Unable to create directory %s" % rpout.path)

	if not rpin.lstat():
		Log.FatalError("Source directory %s does not exist" % rpin.path)
	elif not rpin.isdir():
		Log.FatalError("Source %s is not a directory" % rpin.path)
	backup_warn_if_infinite_regress(rpin, rpout)
	Globals.rbdir = rpout.append_path("rdiff-backup-data")

def backup_set_rbdir(rpin, rpout):
	"""Initialize data dir and logging"""
	global incdir, prevtime
	SetConnections.UpdateGlobal('rbdir', Globals.rbdir)
	checkdest_if_necessary(rpout)
	incdir = Globals.rbdir.append_path("increments")
	prevtime = backup_get_mirrortime()

	assert rpout.lstat(), (rpout.path, rpout.lstat())
	if rpout.isdir() and not rpout.listdir(): # rpout is empty dir
		if Globals.change_permissions:
			rpout.chmod(0700) # just make sure permissions aren't too lax
	elif not Globals.rbdir.lstat() and not force: Log.FatalError(
"""Destination directory

%s

exists, but does not look like a rdiff-backup directory.  Running
rdiff-backup like this could mess up what is currently in it.  If you
want to update or overwrite it, run rdiff-backup with the --force
option.""" % rpout.path)

	if not Globals.rbdir.lstat(): Globals.rbdir.mkdir()
	inc_base = Globals.rbdir.append_path("increments")
	if not inc_base.lstat(): inc_base.mkdir()
	if Log.verbosity > 0:
		Log.open_logfile(Globals.rbdir.append("backup.log"))
	ErrorLog.open(Time.curtimestr, compress = Globals.compression)

def backup_warn_if_infinite_regress(rpin, rpout):
	"""Warn user if destination area contained in source area"""
	if rpout.conn is rpin.conn: # it's meaningful to compare paths
		if ((len(rpout.path) > len(rpin.path)+1 and
			 rpout.path[:len(rpin.path)] == rpin.path and
			 rpout.path[len(rpin.path)] == '/') or
			(rpin.path == "." and rpout.path[0] != '/' and
			 rpout.path[:2] != '..')):
			# Just a few heuristics, we don't have to get every case
			if Globals.backup_reader.Globals.select_source.Select(rpout): Log(
"""Warning: The destination directory '%s' may be contained in the
source directory '%s'.  This could cause an infinite regress.  You
may need to use the --exclude option.""" % (rpout.path, rpin.path), 2)

def backup_get_mirrortime():
	"""Return time in seconds of previous mirror, or None if cannot"""
	incbase = Globals.rbdir.append_path("current_mirror")
	mirror_rps = restore.get_inclist(incbase)
	assert len(mirror_rps) <= 1, \
		   "Found %s current_mirror rps, expected <=1" % (len(mirror_rps),)
	if mirror_rps: return mirror_rps[0].getinctime()
	else: return None

def backup_set_fs_globals(rpin, rpout):
	"""Use fs_abilities to set the globals that depend on filesystem"""
	src_fsa = fs_abilities.FSAbilities().init_readonly(rpin)
	SetConnections.UpdateGlobal('read_acls', src_fsa.acls)
	if src_fsa.eas: rpin.get_ea()
	SetConnections.UpdateGlobal('read_eas', src_fsa.eas)

	dest_fsa = fs_abilities.FSAbilities().init_readwrite(
		Globals.rbdir, override_chars_to_quote = Globals.chars_to_quote)
	SetConnections.UpdateGlobal('preserve_hardlinks', dest_fsa.hardlinks)
	SetConnections.UpdateGlobal('fsync_directories', dest_fsa.fsync_dirs)
	SetConnections.UpdateGlobal('write_acls', dest_fsa.acls)
	SetConnections.UpdateGlobal('write_eas', Globals.read_eas and dest_fsa.eas)
	SetConnections.UpdateGlobal('change_ownership', dest_fsa.ownership)
	SetConnections.UpdateGlobal('chars_to_quote', dest_fsa.chars_to_quote)
	if Globals.chars_to_quote:
		for conn in Globals.connections:
			conn.FilenameMapping.set_init_quote_vals()
	
def backup_touch_curmirror_local(rpin, rpout):
	"""Make a file like current_mirror.time.data to record time

	When doing an incremental backup, this should happen before any
	other writes, and the file should be removed after all writes.
	That way we can tell whether the previous session aborted if there
	are two current_mirror files.

	When doing the initial full backup, the file can be created after
	everything else is in place.

	"""
	mirrorrp = Globals.rbdir.append("current_mirror.%s.%s" % (Time.curtimestr,
															  "data"))
	Log("Touching mirror marker %s" % mirrorrp.path, 6)
	mirrorrp.touch()
	mirrorrp.fsync_with_dir()

def backup_remove_curmirror_local():
	"""Remove the older of the current_mirror files.  Use at end of session"""
	assert Globals.rbdir.conn is Globals.local_connection
	curmir_incs = restore.get_inclist(Globals.rbdir.append("current_mirror"))
	assert len(curmir_incs) == 2
	if curmir_incs[0].getinctime() < curmir_incs[1].getinctime():
		older_inc = curmir_incs[0]
	else: older_inc = curmir_incs[1]

	C.sync() # Make sure everything is written before curmirror is removed
	older_inc.delete()


def Restore(src_rp, dest_rp, restore_as_of = None):
	"""Main restoring function

	Here src_rp should be the source file (either an increment or
	mirror file), dest_rp should be the target rp to be written.

	"""
	if not restore_root_set: assert restore_get_root(src_rp)
	restore_check_paths(src_rp, dest_rp, restore_as_of)
	restore_set_fs_globals(Globals.rbdir)
	src_rp = restore_init_quoting(src_rp)
	restore_check_backup_dir(restore_root, src_rp, restore_as_of)
	if restore_as_of:
		try: time = Time.genstrtotime(restore_timestr)
		except Time.TimeException, exc: Log.FatalError(str(exc))
	else: time = src_rp.getinctime()
	inc_rpath = Globals.rbdir.append_path('increments', restore_index)
	restore_set_select(restore_root, dest_rp)
	restore_start_log(src_rp, dest_rp, time)
	restore.Restore(restore_root.new_index(restore_index),
					inc_rpath, dest_rp, time)
	Log("Restore finished", 4)

def restore_init_quoting(src_rp):
	"""Change rpaths into quoted versions of themselves if necessary"""
	global restore_root
	if not Globals.chars_to_quote: return src_rp
	for conn in Globals.connections: conn.FilenameMapping.set_init_quote_vals()
	restore_root = FilenameMapping.get_quotedrpath(restore_root)
	SetConnections.UpdateGlobal(
		'rbdir', FilenameMapping.get_quotedrpath(Globals.rbdir))
	return FilenameMapping.get_quotedrpath(src_rp)

def restore_set_fs_globals(target):
	"""Use fs_abilities to set the globals that depend on filesystem"""
	target_fsa = fs_abilities.FSAbilities().init_readwrite(target, 0)
	SetConnections.UpdateGlobal('read_acls', target_fsa.acls)
	SetConnections.UpdateGlobal('write_acls', target_fsa.acls)
	SetConnections.UpdateGlobal('read_eas', target_fsa.eas)
	SetConnections.UpdateGlobal('write_eas', target_fsa.eas)
	if Globals.read_eas: target.get_ea()
	SetConnections.UpdateGlobal('preserve_hardlinks', target_fsa.hardlinks)
	SetConnections.UpdateGlobal('change_ownership', target_fsa.ownership)

	mirror_fsa = fs_abilities.FSAbilities().init_readwrite(Globals.rbdir)
	if Globals.chars_to_quote is None: # otherwise already overridden
		if mirror_fsa.chars_to_quote:
			SetConnections.UpdateGlobal('chars_to_quote',
										mirror_fsa.chars_to_quote)
		else: SetConnections.UpdateGlobal('chars_to_quote', "")

def restore_set_select(mirror_rp, target):
	"""Set the selection iterator on mirror side from command line args

	Here we set the selector on the mirror side, because that is where
	we will be filtering, but the pathnames are relative to the target
	directory.

	"""
	if select_opts: 
		mirror_rp.conn.restore.MirrorStruct.set_mirror_select(
			target, select_opts, *select_files)

def restore_start_log(rpin, target, time):
	"""Open restore log file, log initial message"""
	try: Log.open_logfile(Globals.rbdir.append("restore.log"))
	except LoggerError, e: Log("Warning, " + str(e), 2)

	# Log following message at file verbosity 3, but term verbosity 4
	log_message = ("Starting restore of %s to %s as it was as of %s." %
				   (rpin.path, target.path, Time.timetopretty(time)))
	if Log.term_verbosity >= 4: Log.log_to_term(log_message, 4)
	if Log.verbosity >= 3: Log.log_to_file(log_message)

def restore_check_paths(rpin, rpout, restoreasof = None):
	"""Check paths and return pair of corresponding rps"""
	if not restoreasof:
		if not rpin.lstat():
			Log.FatalError("Source file %s does not exist" % rpin.path)
	if not force and rpout.lstat() and (not rpout.isdir() or rpout.listdir()):
		Log.FatalError("Restore target %s already exists, "
					   "specify --force to overwrite." % rpout.path)

def restore_check_backup_dir(mirror_root, src_rp, restore_as_of):
	"""Make sure backup dir root rpin is in consistent state"""
	if not restore_as_of and not src_rp.isincfile():
		Log.FatalError("""File %s does not look like an increment file.

Try restoring from an increment file (the filenames look like
"foobar.2001-09-01T04:49:04-07:00.diff").""" % src_rp.path)

	result = checkdest_need_check(mirror_root)
	if result is None:
		Log.FatalError("%s does not appear to be an rdiff-backup directory."
					   % (Globals.rbdir.path,))
	elif result == 1: Log.FatalError(
		"Previous backup to %s seems to have failed.\nRerun rdiff-backup "
		"rdiff-with --check-destination-dir option to revert directory "
		"to state before unsuccessful session." % (mirror_root.path,))

def restore_get_root(rpin):
	"""Set data dir, restore_root and index, or return None if fail

	The idea here is to keep backing up on the path until we find
	a directory that contains "rdiff-backup-data".  That is the
	mirror root.  If the path from there starts
	"rdiff-backup-data/increments*", then the index is the
	remainder minus that.  Otherwise the index is just the path
	minus the root.

	All this could fail if the increment file is pointed to in a
	funny way, using symlinks or somesuch.

	"""
	global restore_root, restore_index
	if rpin.isincfile(): relpath = rpin.getincbase().path
	else: relpath = rpin.path
	pathcomps = os.path.join(rpin.conn.os.getcwd(), relpath).split("/")
	assert len(pathcomps) >= 2 # path should be relative to /

	i = len(pathcomps)
	while i >= 2:
		parent_dir = rpath.RPath(rpin.conn, "/".join(pathcomps[:i]))
		if (parent_dir.isdir() and
			"rdiff-backup-data" in parent_dir.listdir()): break
		i = i-1
	else: return None

	restore_root = parent_dir
	Log("Using mirror root directory %s" % restore_root.path, 6)
	SetConnections.UpdateGlobal('rbdir',
								restore_root.append_path("rdiff-backup-data"))
	if not Globals.rbdir.isdir():
		Log.FatalError("Unable to read rdiff-backup-data directory %s" %
					   Globals.rbdir.path)

	from_datadir = tuple(pathcomps[i:])
	if not from_datadir or from_datadir[0] != "rdiff-backup-data":
		restore_index = from_datadir # in mirror, not increments
	else:
		assert (from_datadir[1] == "increments" or
				(len(from_datadir) == 2 and
				 from_datadir[1].startswith('increments'))), from_datadir
		restore_index = from_datadir[2:]
	return 1


def ListIncrements(rp):
	"""Print out a summary of the increments and their times"""
	mirror_root, index = restore_get_root(rp)
	restore_check_backup_dir(mirror_root)
	mirror_rp = mirror_root.new_index(index)
	inc_rpath = Globals.rbdir.append_path('increments', index)
	incs = restore.get_inclist(inc_rpath)
	mirror_time = restore.MirrorStruct.get_mirror_time()
	if Globals.parsable_output:
		print manage.describe_incs_parsable(incs, mirror_time, mirror_rp)
	else: print manage.describe_incs_human(incs, mirror_time, mirror_rp)


def CalculateAverage(rps):
	"""Print out the average of the given statistics files"""
	statobjs = map(lambda rp: StatsObj().read_stats_from_rp(rp), rps)
	average_stats = StatsObj().set_to_average(statobjs)
	print average_stats.get_stats_logstring(
		"Average of %d stat files" % len(rps))


def RemoveOlderThan(rootrp):
	"""Remove all increment files older than a certain time"""
	rom_check_dir(rootrp)
	try: time = Time.genstrtotime(remove_older_than_string)
	except Time.TimeException, exc: Log.FatalError(str(exc))
	timep = Time.timetopretty(time)
	Log("Deleting increment(s) before %s" % timep, 4)

	times_in_secs = [inc.getinctime() for inc in 
		  restore.get_inclist(Globals.rbdir.append_path("increments"))]
	times_in_secs = filter(lambda t: t < time, times_in_secs)
	if not times_in_secs:
		Log.FatalError("No increments older than %s found, exiting."
					   % (timep,), 1, errlevel = 0)

	times_in_secs.sort()
	inc_pretty_time = "\n".join(map(Time.timetopretty, times_in_secs))
	if len(times_in_secs) > 1 and not force:
		Log.FatalError("Found %d relevant increments, dated:\n%s"
			"\nIf you want to delete multiple increments in this way, "
			"use the --force." % (len(times_in_secs), inc_pretty_time))

	if len(times_in_secs) == 1:
		Log("Deleting increment at time:\n" + inc_pretty_time, 3)
	else: Log("Deleting increments at times:\n" + inc_pretty_time, 3)
	manage.delete_earlier_than(Globals.rbdir, time)

def rom_check_dir(rootrp):
	"""Check destination dir before RemoveOlderThan"""
	SetConnections.UpdateGlobal('rbdir',
								rootrp.append_path("rdiff-backup-data"))
	if not Globals.rbdir.isdir():
		Log.FatalError("Unable to open rdiff-backup-data dir %s" %
					   (Globals.rbdir.path,))
	checkdest_if_necessary(rootrp)


def ListChangedSince(rp):
	"""List all the files under rp that have changed since restoretime"""
	try: rest_time = Time.genstrtotime(restore_timestr)
	except Time.TimeException, exc: Log.FatalError(str(exc))
	mirror_root, index = restore_get_root(rp)
	restore_check_backup_dir(mirror_root)
	mirror_rp = mirror_root.new_index(index)
	inc_rp = mirror_rp.append_path("increments", index)
	restore.ListChangedSince(mirror_rp, inc_rp, rest_time)


def ListAtTime(rp):
	"""List files in archive under rp that are present at restoretime"""
	try: rest_time = Time.genstrtotime(restore_timestr)
	except Time.TimeException, exc: Log.FatalError(str(exc))
	mirror_root, index = restore_get_root(rp)
	restore_check_backup_dir(mirror_root)
	mirror_rp = mirror_root.new_index(index)
	inc_rp = mirror_rp.append_path("increments", index)
	restore.ListAtTime(mirror_rp, inc_rp, rest_time)
	

def CheckDest(dest_rp):
	"""Check the destination directory, """
	if Globals.rbdir is None:
		SetConnections.UpdateGlobal('rbdir',
									dest_rp.append_path("rdiff-backup-data"))
	need_check = checkdest_need_check(dest_rp)
	if need_check is None:
		Log.FatalError("No destination dir found at %s" % (dest_rp.path,))
	elif need_check == 0:
		Log.FatalError("Destination dir %s does not need checking" %
					   (dest_rp.path,))
	dest_rp.conn.regress.Regress(dest_rp)

def checkdest_need_check(dest_rp):
	"""Return None if no dest dir found, 1 if dest dir needs check, 0 o/w"""
	if not dest_rp.isdir() or not Globals.rbdir.isdir(): return None
	if Globals.rbdir.listdir() == ['chars_to_quote']:
		# This may happen the first backup just after we test for quoting
		return None
	curmirroot = Globals.rbdir.append("current_mirror")
	curmir_incs = restore.get_inclist(curmirroot)
	if not curmir_incs:
		Log.FatalError(
"""Bad rdiff-backup-data dir on destination side

The rdiff-backup data directory
%s
exists, but we cannot find a valid current_mirror marker.  You can
avoid this message by removing this directory; however any data in it
will be lost.
""" % (Globals.rbdir.path,))
	elif len(curmir_incs) == 1: return 0
	else:
		assert len(curmir_incs) == 2, "Found too many current_mirror incs!"
		return 1

def checkdest_if_necessary(dest_rp):
	"""Check the destination dir if necessary.

	This can/should be run before an incremental backup.

	"""
	need_check = checkdest_need_check(dest_rp)
	if need_check == 1:
		Log("Previous backup seems to have failed, regressing "
			"destination now.", 2)
		dest_rp.conn.regress.Regress(dest_rp)
