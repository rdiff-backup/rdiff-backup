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

"""Start (and end) here - read arguments, set global settings, etc."""

from __future__ import generators
import getopt, sys, re, os
from log import Log
import Globals, Time, SetConnections, selection, robust, rpath, \
	   manage, highlevel, connection, restore, FilenameMapping, \
	   Security, Hardlink


action = None
remote_cmd, remote_schema = None, None
force = None
select_opts, select_mirror_opts = [], []
select_files = []

def parse_cmdlineoptions(arglist):
	"""Parse argument list and set global preferences"""
	global args, action, force, restore_timestr, remote_cmd, remote_schema
	global remove_older_than_string
	def sel_fl(filename):
		"""Helper function for including/excluding filelists below"""
		try: return open(filename, "r")
		except IOError: Log.FatalError("Error opening file %s" % filename)

	try: optlist, args = getopt.getopt(arglist, "blr:sv:V",
		 ["backup-mode", "calculate-average", "chars-to-quote=",
		  "current-time=", "exclude=", "exclude-device-files",
		  "exclude-filelist=", "exclude-filelist-stdin",
		  "exclude-globbing-filelist=", "exclude-mirror=",
		  "exclude-other-filesystems", "exclude-regexp=",
		  "exclude-special-files", "force", "include=",
		  "include-filelist=", "include-filelist-stdin",
		  "include-globbing-filelist=", "include-regexp=",
		  "list-changed-since=", "list-increments", "no-compression",
		  "no-compression-regexp=", "no-hard-links", "null-separator",
		  "parsable-output", "print-statistics", "quoting-char=",
		  "remote-cmd=", "remote-schema=", "remove-older-than=",
		  "restore-as-of=", "restrict=", "restrict-read-only=",
		  "restrict-update-only=", "server", "sleep-ratio=",
		  "ssh-no-compression", "terminal-verbosity=", "test-server",
		  "verbosity=", "version", "windows-mode",
		  "windows-time-format"])
	except getopt.error, e:
		commandline_error("Bad commandline options: %s" % str(e))

	for opt, arg in optlist:
		if opt == "-b" or opt == "--backup-mode": action = "backup"
		elif opt == "--calculate-average": action = "calculate-average"
		elif opt == "--chars-to-quote":
			Globals.set('chars_to_quote', arg)
			Globals.set('quoting_enabled', 1)
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
		elif opt == "--exclude-mirror":
			select_mirror_opts.append(("--exclude", arg))
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
		elif opt == "--list-changed-since":
			restore_timestr, action = arg, "list-changed-since"
		elif opt == "-l" or opt == "--list-increments":
			action = "list-increments"
		elif opt == "--no-compression": Globals.set("compression", None)
		elif opt == "--no-compression-regexp":
			Globals.set("no_compression_regexp_string", arg)
		elif opt == "--no-hard-links": Globals.set('preserve_hardlinks', 0)
		elif opt == "--null-separator": Globals.set("null_separator", 1)
		elif opt == "--parsable-output": Globals.set('parsable_output', 1)
		elif opt == "--print-statistics": Globals.set('print_statistics', 1)
		elif opt == "--quoting-char":
			Globals.set('quoting_char', arg)
			Globals.set('quoting_enabled', 1)
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
		elif opt == "--sleep-ratio":
			Globals.set_float("sleep_ratio", arg, 0, 1, inclusive=0)
		elif opt == "--ssh-no-compression":
			Globals.set('ssh_compression', None)
		elif opt == "--terminal-verbosity": Log.setterm_verbosity(arg)
		elif opt == "--test-server": action = "test-server"
		elif opt == "-V" or opt == "--version":
			print "rdiff-backup " + Globals.version
			sys.exit(0)
		elif opt == "-v" or opt == "--verbosity": Log.setverbosity(arg)
		elif opt == "--windows-mode":
			Globals.set('time_separator', "_")
			Globals.set('chars_to_quote', "A-Z:")
			Globals.set('quoting_enabled', 1)
			Globals.set('preserve_hardlinks', 0)
			select_opts.append(("--exclude-special-files", None))
		elif opt == '--windows-time-format':
			Globals.set('time_separator', "_")
		else: Log.FatalError("Unknown option %s" % opt)

def set_action():
	"""Check arguments and try to set action"""
	global action
	l = len(args)
	if not action:
		if l == 0: commandline_error("No arguments given")
		elif l == 1: action = "restore"
		elif l == 2:
			if rpath.RPath(Globals.local_connection, args[0]).isincfile():
				action = "restore"
			else: action = "backup"
		else: commandline_error("Too many arguments given")

	if l == 0 and action != "server":
		commandline_error("No arguments given")
	if l > 0 and action == "server":
		commandline_error("Too many arguments given")
	if l < 2 and (action == "backup" or action == "restore-as-of"):
		commandline_error("Two arguments are required (source, destination).")
	if l == 2 and (action == "list-increments" or
				   action == "remove-older-than" or
				   action == "list-changed-since"):
		commandline_error("Only use one argument, "
						  "the root of the backup directory")
	if l > 2 and action != "calculate-average":
		commandline_error("Too many arguments given")

def commandline_error(message):
	sys.stderr.write("Error: %s\n" % message)
	sys.stderr.write("See the rdiff-backup manual page for instructions\n")
	sys.exit(1)

def misc_setup(rps):
	"""Set default change ownership flag, umask, relay regexps"""
	if ((len(rps) == 2 and rps[1].conn.os.getuid() == 0) or
		(len(rps) < 2 and os.getuid() == 0)):
		# Allow change_ownership if destination connection is root
		for conn in Globals.connections:
			conn.Globals.set('change_ownership', 1)
		for rp in rps: rp.setdata() # Update with userinfo

	os.umask(077)
	Time.setcurtime(Globals.current_time)
	FilenameMapping.set_init_quote_vals()
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
	elif action == "backup": Backup(rps[0], rps[1])
	elif action == "restore": Restore(*rps)
	elif action == "restore-as-of": RestoreAsOf(rps[0], rps[1])
	elif action == "test-server": SetConnections.TestConnections()
	elif action == "list-changed-since": ListChangedSince(rps[0])
	elif action == "list-increments": ListIncrements(rps[0])
	elif action == "remove-older-than": RemoveOlderThan(rps[0])
	elif action == "calculate-average": CalculateAverage(rps)
	else: raise AssertionError("Unknown action " + action)

def cleanup():
	"""Do any last minute cleaning before exiting"""
	Log("Cleaning up", 6)
	Log.close_logfile()
	if not Globals.server: SetConnections.CloseConnections()

def Main(arglist):
	"""Start everything up!"""
	parse_cmdlineoptions(arglist)
	set_action()
	cmdpairs = SetConnections.get_cmd_pairs(args, remote_schema, remote_cmd)
	Security.initialize(action, cmdpairs)
	rps = map(SetConnections.cmdpair2rp, cmdpairs)
	misc_setup(rps)
	take_action(rps)
	cleanup()


def Backup(rpin, rpout):
	"""Backup, possibly incrementally, src_path to dest_path."""
	SetConnections.BackupInitConnections(rpin.conn, rpout.conn)
	backup_set_select(rpin)
	backup_init_dirs(rpin, rpout)
	if prevtime:
		Time.setprevtime(prevtime)
		highlevel.Mirror_and_increment(rpin, rpout, incdir)
	else: highlevel.Mirror(rpin, rpout)
	rpout.conn.Main.backup_touch_curmirror_local(rpin, rpout)

def backup_set_select(rpin):
	"""Create Select objects on source connection"""
	rpin.conn.highlevel.HLSourceStruct.set_source_select(rpin, select_opts,
														 *select_files)

def backup_init_dirs(rpin, rpout):
	"""Make sure rpin and rpout are valid, init data dir and logging"""
	global datadir, incdir, prevtime
	if rpout.lstat() and not rpout.isdir():
		if not force: Log.FatalError("Destination %s exists and is not a "
									 "directory" % rpout.path)
		else:
			Log("Deleting %s" % rpout.path, 3)
			rpout.delete()

	if not rpin.lstat():
		Log.FatalError("Source directory %s does not exist" % rpin.path)
	elif not rpin.isdir():
		Log.FatalError("Source %s is not a directory" % rpin.path)

	datadir = rpout.append("rdiff-backup-data")
	SetConnections.UpdateGlobal('rbdir', datadir)
	incdir = rpath.RPath(rpout.conn, os.path.join(datadir.path, "increments"))
	prevtime = backup_get_mirrortime()

	if rpout.lstat():
		if rpout.isdir() and not rpout.listdir(): # rpout is empty dir
			rpout.chmod(0700) # just make sure permissions aren't too lax
		elif not datadir.lstat() and not force: Log.FatalError(
"""Destination directory

%s

exists, but does not look like a rdiff-backup directory.  Running
rdiff-backup like this could mess up what is currently in it.  If you
want to update or overwrite it, run rdiff-backup with the --force
option.""" % rpout.path)

	if not rpout.lstat():
		try: rpout.mkdir()
		except os.error:
			Log.FatalError("Unable to create directory %s" % rpout.path)
	if not datadir.lstat(): datadir.mkdir()
	if Log.verbosity > 0:
		Log.open_logfile(datadir.append("backup.log"))
	backup_warn_if_infinite_regress(rpin, rpout)

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

def backup_get_mirrorrps():
	"""Return list of current_mirror rps"""
	datadir = Globals.rbdir
	if not datadir.isdir(): return []
	mirrorrps = [datadir.append(fn) for fn in datadir.listdir()
				 if fn.startswith("current_mirror.")]
	return filter(lambda rp: rp.isincfile(), mirrorrps)

def backup_get_mirrortime():
	"""Return time in seconds of previous mirror, or None if cannot"""
	mirrorrps = backup_get_mirrorrps()
	if not mirrorrps: return None
	if len(mirrorrps) > 1:
		Log(
"""Warning: duplicate current_mirror files found.  Perhaps something
went wrong during your last backup?  Using """ + mirrorrps[-1].path, 2)

	timestr = mirrorrps[-1].getinctime()
	return Time.stringtotime(timestr)

def backup_touch_curmirror_local(rpin, rpout):
	"""Make a file like current_mirror.time.data to record time

	Also updates rpout so mod times don't get messed up.  This should
	be run on the destination connection.

	"""
	datadir = Globals.rbdir
	map(rpath.RPath.delete, backup_get_mirrorrps())
	mirrorrp = datadir.append("current_mirror.%s.%s" % (Time.curtimestr,
														"data"))
	Log("Touching mirror marker %s" % mirrorrp.path, 6)
	mirrorrp.touch()
	rpath.copy_attribs(rpin, rpout)

def Restore(src_rp, dest_rp = None):
	"""Main restoring function

	Here src_rp should be an increment file, and if dest_rp is
	missing it defaults to the base of the increment.

	"""
	rpin, rpout = restore_check_paths(src_rp, dest_rp)
	time = Time.stringtotime(rpin.getinctime())
	restore_common(rpin, rpout, time)

def RestoreAsOf(rpin, target):
	"""Secondary syntax for restore operation

	rpin - RPath of mirror file to restore (not nec. with correct index)
	target - RPath of place to put restored file

	"""
	restore_check_paths(rpin, target, 1)
	try: time = Time.genstrtotime(restore_timestr)
	except Time.TimeException, exc: Log.FatalError(str(exc))
	restore_common(rpin, target, time)

def restore_common(rpin, target, time):
	"""Restore operation common to Restore and RestoreAsOf"""
	mirror_root, index = restore_get_root(rpin)
	mirror = mirror_root.new_index(index)
	inc_rpath = datadir.append_path('increments', index)
	restore_init_select(mirror_root, target)
	restore_start_log(rpin, target, time)
	restore.Restore(inc_rpath, mirror, target, time)
	Log("Restore ended", 4)

def restore_start_log(rpin, target, time):
	"""Open restore log file, log initial message"""
	try: Log.open_logfile(datadir.append("restore.log"))
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
		elif not rpin.isincfile():
			Log.FatalError("""File %s does not look like an increment file.

Try restoring from an increment file (the filenames look like
"foobar.2001-09-01T04:49:04-07:00.diff").""" % rpin.path)

	if not rpout: rpout = rpath.RPath(Globals.local_connection,
									  rpin.getincbase_str())
	if rpout.lstat():
		Log.FatalError("Restore target %s already exists, "
					   "and will not be overwritten." % rpout.path)
	return rpin, rpout

def restore_init_select(rpin, rpout):
	"""Initialize Select

	Unlike the backup selections, here they are on the local
	connection, because the backup operation is pipelined in a way
	the restore operation isn't.

	"""
	restore._select_mirror = selection.Select(rpin)
	restore._select_mirror.ParseArgs(select_mirror_opts, [])
	restore._select_mirror.parse_rbdir_exclude()
	restore._select_source = selection.Select(rpout)

def restore_get_root(rpin):
	"""Return (mirror root, index) and set the data dir

	The idea here is to keep backing up on the path until we find
	a directory that contains "rdiff-backup-data".  That is the
	mirror root.  If the path from there starts
	"rdiff-backup-data/increments*", then the index is the
	remainder minus that.  Otherwise the index is just the path
	minus the root.

	All this could fail if the increment file is pointed to in a
	funny way, using symlinks or somesuch.

	"""
	global datadir
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
	else: Log.FatalError("Unable to find rdiff-backup-data directory")

	rootrp = parent_dir
	Log("Using mirror root directory %s" % rootrp.path, 6)

	datadir = rootrp.append_path("rdiff-backup-data")
	SetConnections.UpdateGlobal('rbdir', datadir)
	if not datadir.isdir():
		Log.FatalError("Unable to read rdiff-backup-data directory %s" %
					   datadir.path)

	from_datadir = tuple(pathcomps[i:])
	if not from_datadir or from_datadir[0] != "rdiff-backup-data":
		return (rootrp, from_datadir) # in mirror, not increments
	assert from_datadir[1] == "increments"
	return (rootrp, from_datadir[2:])


def ListIncrements(rp):
	"""Print out a summary of the increments and their times"""
	mirror_root, index = restore_get_root(rp)
	Globals.rbdir = datadir = \
					mirror_root.append_path("rdiff-backup-data")
	mirrorrp = mirror_root.new_index(index)
	inc_rpath = datadir.append_path('increments', index)
	incs = restore.get_inclist(inc_rpath)
	mirror_time = restore.get_mirror_time()
	if Globals.parsable_output:
		print manage.describe_incs_parsable(incs, mirror_time, mirrorrp)
	else: print manage.describe_incs_human(incs, mirror_time, mirrorrp)


def CalculateAverage(rps):
	"""Print out the average of the given statistics files"""
	statobjs = map(lambda rp: StatsObj().read_stats_from_rp(rp), rps)
	average_stats = StatsObj().set_to_average(statobjs)
	print average_stats.get_stats_logstring(
		"Average of %d stat files" % len(rps))


def RemoveOlderThan(rootrp):
	"""Remove all increment files older than a certain time"""
	datadir = rootrp.append("rdiff-backup-data")
	if not datadir.lstat() or not datadir.isdir():
		Log.FatalError("Unable to open rdiff-backup-data dir %s" %
					   (datadir.path,))

	try: time = Time.genstrtotime(remove_older_than_string)
	except Time.TimeException, exc: Log.FatalError(str(exc))
	timep = Time.timetopretty(time)
	Log("Deleting increment(s) before %s" % timep, 4)

	times_in_secs = map(lambda inc: Time.stringtotime(inc.getinctime()),
						restore.get_inclist(datadir.append("increments")))
	times_in_secs = filter(lambda t: t < time, times_in_secs)
	if not times_in_secs:
		Log.FatalError("No increments older than %s found" % timep)

	times_in_secs.sort()
	inc_pretty_time = "\n".join(map(Time.timetopretty, times_in_secs))
	if len(times_in_secs) > 1 and not force:
		Log.FatalError("Found %d relevant increments, dated:\n%s"
			"\nIf you want to delete multiple increments in this way, "
			"use the --force." % (len(times_in_secs), inc_pretty_time))

	if len(times_in_secs) == 1:
		Log("Deleting increment at time:\n" + inc_pretty_time, 3)
	else: Log("Deleting increments at times:\n" + inc_pretty_time, 3)
	manage.delete_earlier_than(datadir, time)


def ListChangedSince(rp):
	"""List all the files under rp that have changed since restoretime"""
	try: rest_time = Time.genstrtotime(restore_timestr)
	except Time.TimeException, exc: Log.FatalError(str(exc))
	mirror_root, index = restore_get_root(rp)
	Globals.rbdir = datadir = mirror_root.append_path("rdiff-backup-data")
	mirror_time = restore.get_mirror_time()

	def get_rids_recursive(rid):
		"""Yield all the rids under rid that have inc newer than rest_time"""
		yield rid
		for sub_rid in restore.yield_rids(rid, rest_time, mirror_time):
			for sub_sub_rid in get_rids_recursive(sub_rid): yield sub_sub_rid

	def determineChangeType(incList):
		"returns the type of change determined from incList"
		assert len(incList) > 0
		last_inc_type = incList[-1].getinctype() # examine earliest change
		if last_inc_type == 'snapshot': return "misc change"
		elif last_inc_type == 'missing': return "new file"
		elif last_inc_type == 'diff': return "modified"
		elif last_inc_type == 'dir': return "dir change"
		else: return "Unknown!"

	inc_rpath = datadir.append_path('increments', index)
	inc_list = restore.get_inclist(inc_rpath)
	root_rid = restore.RestoreIncrementData(index, inc_rpath, inc_list)
	for rid in get_rids_recursive(root_rid):
		if rid.inc_list:
			print "%-11s: %s" % (determineChangeType(rid.inc_list),
								 rid.get_indexpath())

