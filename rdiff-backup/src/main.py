#!/usr/bin/python

execfile("setconnections.py")
import getopt, sys, re

#######################################################################
#
# main - Start here: Read arguments, set global settings, etc.
#

class Main:
	def __init__(self):
		self.action = None
		self.remote_cmd, self.remote_schema = None, None
		self.force = None
		self.select_opts, self.select_mirror_opts = [], []
		self.select_files = []

	def parse_cmdlineoptions(self):
		"""Parse argument list and set global preferences"""
		def sel_fl(filename):
			"""Helper function for including/excluding filelists below"""
			try: return open(filename, "r")
			except IOError: Log.FatalError("Error opening file %s" % filename)

		try: optlist, self.args = getopt.getopt(sys.argv[1:], "blmr:sv:V",
			 ["backup-mode", "change-source-perms",
			  "chars-to-quote=", "checkpoint-interval=",
			  "current-time=", "exclude=", "exclude-device-files",
			  "exclude-filelist=", "exclude-filelist-stdin",
			  "exclude-mirror=", "exclude-regexp=", "force",
			  "include=", "include-filelist=",
			  "include-filelist-stdin", "include-regexp=",
			  "list-increments", "mirror-only", "no-compression",
			  "no-compression-regexp=", "no-hard-links", "no-resume",
			  "parsable-output", "quoting-char=", "remote-cmd=",
			  "remote-schema=", "remove-older-than=",
			  "restore-as-of=", "resume", "resume-window=", "server",
			  "terminal-verbosity=", "test-server", "verbosity",
			  "version", "windows-mode", "windows-time-format"])
		except getopt.error, e:
			self.commandline_error("Bad commandline options: %s" % str(e))

		for opt, arg in optlist:
			if opt == "-b" or opt == "--backup-mode": self.action = "backup"
			elif opt == "--change-source-perms":
				Globals.set('change_source_perms', 1)
			elif opt == "--chars-to-quote":
				Globals.set('chars_to_quote', arg)
				Globals.set('quoting_enabled', 1)
			elif opt == "--checkpoint-interval":
				Globals.set_integer('checkpoint_interval', arg)
			elif opt == "--current-time":
				Globals.set_integer('current_time', arg)
			elif opt == "--exclude": self.select_opts.append((opt, arg))
			elif opt == "--exclude-device-files":
				self.select_opts.append((opt, arg))
			elif opt == "--exclude-filelist":
				self.select_opts.append((opt, arg))
				self.select_files.append(sel_fl(arg))
			elif opt == "--exclude-filelist-stdin":
				self.select_opts.append(("--exclude-filelist",
										 "standard input"))
				self.select_files.append(sys.stdin)
			elif opt == "--exclude-mirror":
				self.select_mirror_opts.append(("--exclude", arg))
			elif opt == "--exclude-regexp": self.select_opts.append((opt, arg))
			elif opt == "--force": self.force = 1
			elif opt == "--include": self.select_opts.append((opt, arg))
			elif opt == "--include-filelist":
				self.select_opts.append((opt, arg))
				self.select_files.append(sel_fl(arg))
			elif opt == "--include-filelist-stdin":
				self.select_opts.append(("--include-filelist",
										 "standard input"))
				self.select_files.append(sys.stdin)
			elif opt == "--include-regexp":
				self.select_opts.append((opt, arg))
			elif opt == "-l" or opt == "--list-increments":
				self.action = "list-increments"
			elif opt == "-m" or opt == "--mirror-only": self.action = "mirror"
			elif opt == "--no-compression": Globals.set("compression", None)
			elif opt == "--no-compression-regexp":
				Globals.set("no_compression_regexp_string", arg)
			elif opt == "--no-hard-links": Globals.set('preserve_hardlinks', 0)
			elif opt == '--no-resume': Globals.resume = 0
			elif opt == "-r" or opt == "--restore-as-of":
				self.restore_timestr = arg
				self.action = "restore-as-of"
			elif opt == "--parsable-output": Globals.set('parsable_output', 1)
			elif opt == "--quoting-char":
				Globals.set('quoting_char', arg)
				Globals.set('quoting_enabled', 1)
			elif opt == "--remote-cmd": self.remote_cmd = arg
			elif opt == "--remote-schema": self.remote_schema = arg
			elif opt == "--remove-older-than":
				self.remove_older_than_string = arg
				self.action = "remove-older-than"
			elif opt == '--resume': Globals.resume = 1
			elif opt == '--resume-window':
				Globals.set_integer('resume_window', arg)
			elif opt == "-s" or opt == "--server": self.action = "server"
			elif opt == "--terminal-verbosity": Log.setterm_verbosity(arg)
			elif opt == "--test-server": self.action = "test-server"
			elif opt == "-V" or opt == "--version":
				print "rdiff-backup " + Globals.version
				sys.exit(0)
			elif opt == "-v" or opt == "--verbosity": Log.setverbosity(arg)
			elif opt == "--windows-mode":
				Globals.set('time_separator', "_")
				Globals.set('chars_to_quote', ":")
				Globals.set('quoting_enabled', 1)
			elif opt == '--windows-time-format':
				Globals.set('time_separator', "_")
			else: Log.FatalError("Unknown option %s" % opt)

	def set_action(self):
		"""Check arguments and try to set self.action"""
		l = len(self.args)
		if not self.action:
			if l == 0: self.commandline_error("No arguments given")
			elif l == 1: self.action = "restore"
			elif l == 2:
				if RPath(Globals.local_connection, self.args[0]).isincfile():
					self.action = "restore"
				else: self.action = "backup"
			else: self.commandline_error("Too many arguments given")

		if l == 0 and self.action != "server" and self.action != "test-server":
			self.commandline_error("No arguments given")
		if l > 0 and self.action == "server":
			self.commandline_error("Too many arguments given")
		if l < 2 and (self.action == "backup" or self.action == "mirror" or
					  self.action == "restore-as-of"):
			self.commandline_error("Two arguments are required "
								   "(source, destination).")
		if l == 2 and (self.action == "list-increments" or
					   self.action == "remove-older-than"):
			self.commandline_error("Only use one argument, "
								   "the root of the backup directory")
		if l > 2: self.commandline_error("Too many arguments given")

	def commandline_error(self, message):
		sys.stderr.write("Error: %s\n" % message)
		sys.stderr.write("See the rdiff-backup manual page for instructions\n")
		sys.exit(1)

	def misc_setup(self, rps):
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

		# This is because I originally didn't think compiled regexps
		# could be pickled, and so must be compiled on remote side.
		Globals.postset_regexp('no_compression_regexp',
							   Globals.no_compression_regexp_string)

	def take_action(self, rps):
		"""Do whatever self.action says"""
		if self.action == "server":
			PipeConnection(sys.stdin, sys.stdout).Server()
		elif self.action == "backup": self.Backup(rps[0], rps[1])
		elif self.action == "restore": self.Restore(*rps)
		elif self.action == "restore-as-of": self.RestoreAsOf(rps[0], rps[1])
		elif self.action == "mirror": self.Mirror(rps[0], rps[1])
		elif self.action == "test-server": SetConnections.TestConnections()
		elif self.action == "list-increments": self.ListIncrements(rps[0])
		elif self.action == "remove-older-than": self.RemoveOlderThan(rps[0])
		else: raise AssertionError("Unknown action " + self.action)

	def cleanup(self):
		"""Do any last minute cleaning before exiting"""
		Log("Cleaning up", 6)
		Log.close_logfile()
		if not Globals.server: SetConnections.CloseConnections()

	def Main(self):
		"""Start everything up!"""
		self.parse_cmdlineoptions()
		self.set_action()
		rps = SetConnections.InitRPs(self.args,
									 self.remote_schema, self.remote_cmd)
		self.misc_setup(rps)
		self.take_action(rps)
		self.cleanup()


	def Mirror(self, src_rp, dest_rp):
		"""Turn dest_path into a copy of src_path"""
		Log("Mirroring %s to %s" % (src_rp.path, dest_rp.path), 5)
		self.mirror_check_paths(src_rp, dest_rp)
		# Since no "rdiff-backup-data" dir, use root of destination.
		SetConnections.UpdateGlobal('rbdir', dest_rp)
		SetConnections.BackupInitConnections(src_rp.conn, dest_rp.conn)
		RSI = Globals.backup_writer.Resume.ResumeCheck()
		SaveState.init_filenames(None)
		HighLevel.Mirror(src_rp, dest_rp, 1, RSI, None)

	def mirror_check_paths(self, rpin, rpout):
		"""Check paths and return rpin, rpout"""
		if not rpin.lstat():
			Log.FatalError("Source directory %s does not exist" % rpin.path)
		if rpout.lstat() and not self.force:
			Log.FatalError(
"""Destination %s exists so continuing could mess it up.  Run
rdiff-backup with the --force option if you want to mirror anyway.""" %
			rpout.path)


	def Backup(self, rpin, rpout):
		"""Backup, possibly incrementally, src_path to dest_path."""
		SetConnections.BackupInitConnections(rpin.conn, rpout.conn)
		self.backup_init_select(rpin, rpout)
		self.backup_init_dirs(rpin, rpout)
		RSI = Globals.backup_writer.Resume.ResumeCheck()
		if self.prevtime:
			Time.setprevtime(self.prevtime)
			SaveState.init_filenames(1)
			HighLevel.Mirror_and_increment(rpin, rpout, self.incdir, RSI)
		else:
			SaveState.init_filenames(None)
			HighLevel.Mirror(rpin, rpout, 1, RSI)
		self.backup_touch_curmirror(rpin, rpout)

	def backup_init_select(self, rpin, rpout):
		"""Create Select objects on source and dest connections"""
		rpin.conn.Globals.set_select(DSRPath(1, rpin), self.select_opts,
									 None, *self.select_files)
		rpout.conn.Globals.set_select(DSRPath(None, rpout),
									  self.select_mirror_opts, 1)

	def backup_init_dirs(self, rpin, rpout):
		"""Make sure rpin and rpout are valid, init data dir and logging"""
		if rpout.lstat() and not rpout.isdir():
			if not self.force:
				Log.FatalError("Destination %s exists and is not a "
							   "directory" % rpout.path)
			else:
				Log("Deleting %s" % rpout.path, 3)
				rpout.delete()
			
		if not rpin.lstat():
			Log.FatalError("Source directory %s does not exist" % rpin.path)
		elif not rpin.isdir():
			Log.FatalError("Source %s is not a directory" % rpin.path)

		self.datadir = rpout.append("rdiff-backup-data")
		SetConnections.UpdateGlobal('rbdir', self.datadir)
		self.incdir = RPath(rpout.conn, os.path.join(self.datadir.path,
													 "increments"))
		self.prevtime = self.backup_get_mirrortime()

		if rpout.lstat():
			if rpout.isdir() and not rpout.listdir(): # rpout is empty dir
				rpout.chmod(0700) # just make sure permissions aren't too lax
			elif not self.datadir.lstat() and not self.force:
				Log.FatalError(
"""Destination directory %s exists, but does not look like a
rdiff-backup directory.  Running rdiff-backup like this could mess up
what is currently in it.  If you want to overwrite it, run
rdiff-backup with the --force option.""" % rpout.path)

		if not rpout.lstat():
			try: rpout.mkdir()
			except os.error:
				Log.FatalError("Unable to create directory %s" % rpout.path)
		if not self.datadir.lstat(): self.datadir.mkdir()
		if Log.verbosity > 0:
			Log.open_logfile(self.datadir.append("backup.log"))
		self.backup_warn_if_infinite_regress(rpin, rpout)

	def backup_warn_if_infinite_regress(self, rpin, rpout):
		"""Warn user if destination area contained in source area"""
		if rpout.conn is rpin.conn: # it's meaningful to compare paths
			if ((len(rpout.path) > len(rpin.path)+1 and
				 rpout.path[:len(rpin.path)] == rpin.path and
				 rpout.path[len(rpin.path)] == '/') or
				(rpin.path == "." and rpout.path[0] != '/' and
				 rpout.path[:2] != '..')):
				# Just a few heuristics, we don't have to get every case
				if Globals.backup_reader.Globals.select_source \
				   .Select(rpout): Log(
"""Warning: The destination directory '%s' may be contained in the
source directory '%s'.  This could cause an infinite regress.  You
may need to use the --exclude option.""" % (rpout.path, rpin.path), 2)

	def backup_get_mirrorrps(self):
		"""Return list of current_mirror rps"""
		if not self.datadir.isdir(): return []
		mirrorrps = [self.datadir.append(fn) for fn in self.datadir.listdir()
					 if fn.startswith("current_mirror.")]
		return filter(lambda rp: rp.isincfile(), mirrorrps)

	def backup_get_mirrortime(self):
		"""Return time in seconds of previous mirror, or None if cannot"""
		mirrorrps = self.backup_get_mirrorrps()
		if not mirrorrps: return None
		if len(mirrorrps) > 1:
			Log(
"""Warning: duplicate current_mirror files found.  Perhaps something
went wrong during your last backup?  Using """ + mirrorrps[-1].path, 2)

		timestr = mirrorrps[-1].getinctime()
		return Time.stringtotime(timestr)
	
	def backup_touch_curmirror(self, rpin, rpout):
		"""Make a file like current_mirror.time.data to record time

		Also updates rpout so mod times don't get messed up.

		"""
		map(RPath.delete, self.backup_get_mirrorrps())
		mirrorrp = self.datadir.append("current_mirror.%s.%s" %
										  (Time.curtimestr, "data"))
		Log("Touching mirror marker %s" % mirrorrp.path, 6)
		mirrorrp.touch()
		RPath.copy_attribs(rpin, rpout)


	def Restore(self, src_rp, dest_rp = None):
		"""Main restoring function

		Here src_rp should be an increment file, and if dest_rp is
		missing it defaults to the base of the increment.

		"""
		rpin, rpout = self.restore_check_paths(src_rp, dest_rp)
		time = Time.stringtotime(rpin.getinctime())
		self.restore_common(rpin, rpout, time)

	def RestoreAsOf(self, rpin, target):
		"""Secondary syntax for restore operation

		rpin - RPath of mirror file to restore (not nec. with correct index)
		target - RPath of place to put restored file

		"""
		self.restore_check_paths(rpin, target, 1)
		try: time = Time.genstrtotime(self.restore_timestr)
		except TimeError, exp: Log.FatalError(str(exp))
		self.restore_common(rpin, target, time)

	def restore_common(self, rpin, target, time):
		"""Restore operation common to Restore and RestoreAsOf"""
		Log("Starting Restore", 5)
		mirror_root, index = self.restore_get_root(rpin)
		mirror = mirror_root.new_index(index)
		inc_rpath = self.datadir.append_path('increments', index)
		self.restore_init_select(mirror_root, target)
		Log.open_logfile(self.datadir.append("restore.log"))
		Restore.Restore(inc_rpath, mirror, target, time)

	def restore_check_paths(self, rpin, rpout, restoreasof = None):
		"""Check paths and return pair of corresponding rps"""
		if not restoreasof:
			if not rpin.lstat():
				Log.FatalError("Source file %s does not exist" % rpin.path)
			elif not rpin.isincfile():
				Log.FatalError("""File %s does not look like an increment file.

Try restoring from an increment file (the filenames look like
"foobar.2001-09-01T04:49:04-07:00.diff").""" % rpin.path)

		if not rpout: rpout = RPath(Globals.local_connection,
									rpin.getincbase_str())
		if rpout.lstat():
			Log.FatalError("Restore target %s already exists,"
						   "and will not be overwritten." % rpout.path)
		return rpin, rpout

	def restore_init_select(self, rpin, rpout):
		"""Initialize Select

		Unlike the backup selections, here they are on the local
		connection, because the backup operation is pipelined in a way
		the restore operation isn't.

		"""
		Globals.set_select(DSRPath(1, rpin), self.select_mirror_opts, None)
		Globals.set_select(DSRPath(None, rpout), self.select_opts, None,
						   *self.select_files)

	def restore_get_root(self, rpin):
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
		if rpin.isincfile(): relpath = rpin.getincbase().path
		else: relpath = rpin.path
		pathcomps = os.path.join(rpin.conn.os.getcwd(), relpath).split("/")
		assert len(pathcomps) >= 2 # path should be relative to /

		i = len(pathcomps)
		while i >= 2:
			parent_dir = RPath(rpin.conn, "/".join(pathcomps[:i]))
			if (parent_dir.isdir() and
				"rdiff-backup-data" in parent_dir.listdir()): break
			i = i-1
		else: Log.FatalError("Unable to find rdiff-backup-data directory")

		self.rootrp = rootrp = parent_dir
		Log("Using mirror root directory %s" % rootrp.path, 6)

		self.datadir = rootrp.append_path("rdiff-backup-data")
		SetConnections.UpdateGlobal('rbdir', self.datadir)
		if not self.datadir.isdir():
			Log.FatalError("Unable to read rdiff-backup-data directory %s" %
						   self.datadir.path)

		from_datadir = tuple(pathcomps[i:])
		if not from_datadir or from_datadir[0] != "rdiff-backup-data":
			return (rootrp, from_datadir) # in mirror, not increments
		assert from_datadir[1] == "increments"
		return (rootrp, from_datadir[2:])


	def ListIncrements(self, rp):
		"""Print out a summary of the increments and their times"""
		mirror_root, index = self.restore_get_root(rp)
		Globals.rbdir = datadir = \
						mirror_root.append_path("rdiff-backup-data")
		mirrorrp = mirror_root.new_index(index)
		inc_rpath = datadir.append_path('increments', index)
		incs = Restore.get_inclist(inc_rpath)
		mirror_time = Restore.get_mirror_time()
		if Globals.parsable_output:
			print Manage.describe_incs_parsable(incs, mirror_time, mirrorrp)
		else: print Manage.describe_incs_human(incs, mirror_time, mirrorrp)


	def RemoveOlderThan(self, rootrp):
		"""Remove all increment files older than a certain time"""
		datadir = rootrp.append("rdiff-backup-data")
		if not datadir.lstat() or not datadir.isdir():
			Log.FatalError("Unable to open rdiff-backup-data dir %s" %
						   (datadir.path,))

		try: time = Time.genstrtotime(self.remove_older_than_string)
		except TimeError, exp: Log.FatalError(str(exp))
		timep = Time.timetopretty(time)
		Log("Deleting increment(s) before %s" % timep, 4)

		itimes = [Time.stringtopretty(inc.getinctime())
				  for inc in Restore.get_inclist(datadir.append("increments"))
				  if Time.stringtotime(inc.getinctime()) < time]
		
		if not itimes:
			Log.FatalError("No increments older than %s found" % timep)
		inc_pretty_time = "\n".join(itimes)
		if len(itimes) > 1 and not self.force:
			Log.FatalError("Found %d relevant increments, dated:\n%s"
				"\nIf you want to delete multiple increments in this way, "
				"use the --force." % (len(itimes), inc_pretty_time))
			
		Log("Deleting increment%sat times:\n%s" %
			(len(itimes) == 1 and " " or "s ", inc_pretty_time), 3)
		Manage.delete_earlier_than(datadir, time)
		


if __name__ == "__main__" and not globals().has_key('__no_execute__'):
	Globals.Main = Main()
	Globals.Main.Main()
