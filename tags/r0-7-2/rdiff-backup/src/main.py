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

	def parse_cmdlineoptions(self):
		"""Parse argument list and set global preferences"""
		def sel_fl(filename):
			"""Helper function for including/excluding filelists below"""
			try: return open(filename, "r")
			except IOError: Log.FatalError("Error opening file %s" % filename)

		try: optlist, self.args = getopt.getopt(sys.argv[1:], "blmsv:V",
			 ["backup-mode", "change-source-perms",
			  "checkpoint-interval=", "current-time=", "exclude=",
			  "exclude-device-files", "exclude-filelist=",
			  "exclude-filelist-stdin", "exclude-mirror=",
			  "exclude-regexp=", "force", "include=",
			  "include-filelist=", "include-filelist-stdin",
			  "include-regexp=", "list-increments", "mirror-only",
			  "no-compression", "no-compression-regexp=",  
			  "no-hard-links", "no-resume", "remote-cmd=",
			  "remote-schema=", "remove-older-than=", "resume",
			  "resume-window=", "server", "terminal-verbosity=",
			  "test-server", "verbosity", "version",
			  "windows-time-format"])
		except getopt.error:
			self.commandline_error("Error parsing commandline options")

		for opt, arg in optlist:
			if opt == "-b" or opt == "--backup-mode": self.action = "backup"
			elif opt == "--change-source-perms":
				Globals.set('change_source_perms', 1)
			elif opt == "--checkpoint-interval":
				Globals.set_integer('checkpoint_interval', arg)
			elif opt == "--current-time":
				Globals.set_integer('current_time', arg)
			elif opt == "--exclude": self.select_opts.append((opt, arg))
			elif opt == "--exclude-device-files":
				self.select_opts.append((opt, arg))
			elif opt == "--exclude-filelist":
				self.select_opts.append((opt, (arg, sel_fl(arg))))
			elif opt == "--exclude-filelist-stdin":
				self.select_opts.append((opt, ("standard input", sys.stdin)))
			elif opt == "--exclude-mirror":
				self.select_mirror_opts.append(("--exclude", arg))
			elif opt == "--exclude-regexp": self.select_opts.append((opt, arg))
			elif opt == "--force": self.force = 1
			elif opt == "--include": self.select_opts.append((opt, arg))
			elif opt == "--include-filelist":
				self.select_opts.append((opt, (arg, sel_fl(arg))))
			elif opt == "--include-filelist-stdin":
				self.select_opts.append((opt, ("standard input", sys.stdin)))
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
			elif opt == "--remote-cmd": self.remote_cmd = arg
			elif opt == "--remote-schema": self.remote_schema = arg
			elif opt == "--remove-older-than":
				self.remove_older_than_string = arg
				self.action = "remove-older-than"
			elif opt == '--resume': Globals.resume = 1
			elif opt == '--resume-window':
				Globals.set_integer('resume_window', arg)
			elif opt == "-s" or opt == "--server": self.action = "server"
			elif opt == "--terminal-verbosity":
				Log.setterm_verbosity(arg)
			elif opt == "--test-server": self.action = "test-server"
			elif opt == "-V" or opt == "--version":
				print "rdiff-backup " + Globals.version
				sys.exit(0)
			elif opt == "-v" or opt == "--verbosity":
				Log.setverbosity(arg)
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
		if l < 2 and (self.action == "backup" or self.action == "mirror"):
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
		"""Set default change ownership flag, umask, Select objects"""
		if ((len(rps) == 2 and rps[1].conn.os.getuid() == 0) or
			(len(rps) < 2 and os.getuid() == 0)):
			# Allow change_ownership if destination connection is root
			for conn in Globals.connections:
				conn.Globals.set('change_ownership', 1)
			for rp in rps: rp.setdata() # Update with userinfo

		os.umask(077)
		rps[0].conn.Globals.set_select(1, rps[0], self.select_opts)
		if len(rps) == 2:
			rps[1].conn.Globals.set_select(None, rps[1],
										   self.select_mirror_opts)
		Globals.postset_regexp('no_compression_regexp',
							   Globals.no_compression_regexp_string)

	def take_action(self, rps):
		"""Do whatever self.action says"""
		if self.action == "server":
			PipeConnection(sys.stdin, sys.stdout).Server()
		elif self.action == "backup": self.Backup(rps[0], rps[1])
		elif self.action == "restore": apply(self.Restore, rps)
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
		HighLevel.Mirror(src_rp, dest_rp, None) # No checkpointing - no rbdir

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
		self.backup_init_dirs(rpin, rpout)
		Time.setcurtime(Globals.current_time)
		RSI = Resume.ResumeCheck()
		if self.prevtime:
			Time.setprevtime(self.prevtime)
			SaveState.init_filenames(1)
			HighLevel.Mirror_and_increment(rpin, rpout, self.incdir, RSI)
		else:
			SaveState.init_filenames(None)
			HighLevel.Mirror(rpin, rpout, 1, RSI)
		self.backup_touch_curmirror(rpin, rpout)

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

		if rpout.lstat() and not self.datadir.lstat() and not self.force:
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
		mirrorfiles = filter(lambda f: f.startswith("current_mirror."),
							 self.datadir.listdir())
		mirrorrps = map(lambda x: self.datadir.append(x), mirrorfiles)
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
		"""Make a file like current_mirror.time.snapshot to record time

		Also updates rpout so mod times don't get messed up.

		"""
		map(RPath.delete, self.backup_get_mirrorrps())
		mirrorrp = self.datadir.append("current_mirror.%s.%s" %
										  (Time.curtimestr, "snapshot"))
		Log("Touching mirror marker %s" % mirrorrp.path, 6)
		mirrorrp.touch()
		RPath.copy_attribs(rpin, rpout)


	def Restore(self, src_rp, dest_rp = None):
		"""Main restoring function - take src_path to dest_path"""
		Log("Starting Restore", 5)
		rpin, rpout = self.restore_check_paths(src_rp, dest_rp)
		inc_tup = self.restore_get_inctup(rpin)
		mirror_base, mirror_rel_index = self.restore_get_mirror(rpin)
		rtime = Time.stringtotime(rpin.getinctime())
		Log.open_logfile(self.datadir.append("restore.log"))
		HighLevel.Restore(rtime, mirror_base, mirror_rel_index, inc_tup, rpout)

	def restore_check_paths(self, rpin, rpout):
		"""Check paths and return pair of corresponding rps"""
		if not rpin.lstat():
			Log.FatalError("Increment file %s does not exist" % rpin.path)
		if not rpin.isincfile():
			Log.FatalError("""File %s does not look like an increment file.

Try restoring from an increment file (the filenames look like
"foobar.2001-09-01T04:49:04-07:00.diff").""" % rpin.path)

		if not rpout: rpout = RPath(Globals.local_connection,
									rpin.getincbase_str())
		if rpout.lstat():
			Log.FatalError("Restore target %s already exists.  "
						   "Will not overwrite." % rpout.path)
		return rpin, rpout

	def restore_get_inctup(self, rpin):
		"""Return increment tuple (incrp, list of incs)"""
		rpin_dir = rpin.dirsplit()[0]
		if not rpin_dir: rpin_dir = "/"
		rpin_dir_rp = RPath(rpin.conn, rpin_dir)
		incbase = rpin.getincbase()
		incbasename = incbase.dirsplit()[1]
		inclist = filter(lambda rp: rp.isincfile() and
						 rp.getincbase_str() == incbasename,
						 map(rpin_dir_rp.append, rpin_dir_rp.listdir()))
		return IndexedTuple((), (incbase, inclist))

	def restore_get_mirror(self, rpin):
		"""Return (mirror file, relative index) and set the data dir

		The idea here is to keep backing up on the path until we find
		something named "rdiff-backup-data".  Then use that as a
		reference to calculate the oldfile.  This could fail if the
		increment file is pointed to in a funny way, using symlinks or
		somesuch.

		The mirror file will have index (), so also return the index
		relative to the rootrp.

		"""
		pathcomps = os.path.join(rpin.conn.os.getcwd(),
								 rpin.getincbase().path).split("/")
		for i in range(1, len(pathcomps)):
			datadirrp = RPath(rpin.conn, "/".join(pathcomps[:i+1]))
			if pathcomps[i] == "rdiff-backup-data" and datadirrp.isdir():
				break
		else: Log.FatalError("Unable to find rdiff-backup-data dir")

		Globals.rbdir = self.datadir = datadirrp
		rootrp = RPath(rpin.conn, "/".join(pathcomps[:i]))
		if not rootrp.lstat():
			Log.FatalError("Root of mirror area %s does not exist" %
						   rootrp.path)
		else: Log("Using root mirror %s" % rootrp.path, 6)

		from_datadir = pathcomps[i+1:]
		if not from_datadir: raise RestoreError("Problem finding mirror file")
		rel_index = tuple(from_datadir[1:])
		mirrorrp = RPath(rootrp.conn,
						 apply(os.path.join, (rootrp.path,) + rel_index))
		Log("Using mirror file %s" % mirrorrp.path, 6)
		return (mirrorrp, rel_index)


	def ListIncrements(self, rootrp):
		"""Print out a summary of the increments and their times"""
		datadir = self.li_getdatadir(rootrp,
			 """Unable to open rdiff-backup-data dir.

The argument to rdiff-backup -l or rdiff-backup --list-increments
should be the root of the target backup directory, of which
rdiff-backup-data is a subdirectory.  So, if you ran

rdiff-backup /home/foo /mnt/back/bar

earlier, try:

rdiff-backup -l /mnt/back/bar
""")
		print Manage.describe_root_incs(datadir)

	def li_getdatadir(self, rootrp, errormsg):
		"""Return data dir if can find it, otherwise use errormsg"""
		datadir = rootrp.append("rdiff-backup-data")
		if not datadir.lstat() or not datadir.isdir():
			Log.FatalError(errormsg)
		return datadir


	def RemoveOlderThan(self, rootrp):
		"""Remove all increment files older than a certain time"""
		datadir = self.li_getdatadir(rootrp,
									 """Unable to open rdiff-backup-data dir.

Try finding the increments first using --list-increments.""")
		time = self.rot_get_earliest_time()
		timep = Time.timetopretty(time)
		Log("Deleting increment(s) before %s" % timep, 4)
		incobjs = filter(lambda x: x.time < time, Manage.get_incobjs(datadir))
		incobjs_time = ", ".join(map(IncObj.pretty_time, incobjs))
		if not incobjs:
			Log.FatalError("No increments older than %s found" % timep)
		elif len(incobjs) > 1 and not self.force:
			Log.FatalError("Found %d relevant increments, dated %s.\n"
				"If you want to delete multiple increments in this way, "
				"use the --force." % (len(incobjs), incobjs_time))

		Log("Deleting increment%sat %s" % (len(incobjs) == 1 and " " or "s ",
										   incobjs_time), 3)
		Manage.delete_earlier_than(datadir, time)
		
	def rot_get_earliest_time(self):
		"""Return earliest time in seconds that will not be deleted"""
		seconds = Time.intstringtoseconds(self.remove_older_than_string)
		return time.time() - seconds



if __name__ == "__main__" and not globals().has_key('__no_execute__'):
	Globals.Main = Main()
	Globals.Main.Main()
