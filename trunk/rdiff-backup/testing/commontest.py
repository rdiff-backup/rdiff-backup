"""commontest - Some functions and constants common to several test cases"""
import os, sys
from rdiff_backup.log import Log
from rdiff_backup.rpath import RPath
from rdiff_backup import Globals, Hardlink, SetConnections, Main, \
	 selection, lazy, Time, rpath

RBBin = "../rdiff-backup"
SourceDir = "../rdiff_backup"
AbsCurdir = os.getcwd() # Absolute path name of current directory
AbsTFdir = AbsCurdir+"/testfiles"
MiscDir = "../misc"
__no_execute__ = 1 # Keeps the actual rdiff-backup program from running

def Myrm(dirstring):
	"""Run myrm on given directory string"""
	root_rp = rpath.RPath(Globals.local_connection, dirstring)
	for rp in selection.Select(root_rp).set_iter():
		if rp.isdir(): rp.chmod(0700) # otherwise may not be able to remove
	assert not os.system("rm -rf %s" % (dirstring,))

def Make():
	"""Make sure the rdiff-backup script in the source dir is up-to-date"""
	os.chdir(SourceDir)
	os.system("python ./Make")
	os.chdir(AbsCurdir)

def MakeOutputDir():
	"""Initialize the testfiles/output directory"""
	Myrm("testfiles/output")
	rp = rpath.RPath(Globals.local_connection, "testfiles/output")
	rp.mkdir()
	return rp

def rdiff_backup(source_local, dest_local, src_dir, dest_dir,
				 current_time = None, extra_options = ""):
	"""Run rdiff-backup with the given options

	source_local and dest_local are boolean values.  If either is
	false, then rdiff-backup will be run pretending that src_dir and
	dest_dir, respectively, are remote.  The server process will be
	run in directories test1 and test2/tmp respectively.

	src_dir and dest_dir are the source and destination
	(mirror) directories, relative to the testing directory.

	If current time is true, add the --current-time option with the
	given number of seconds.

	extra_options are just added to the command line.

	"""
	if not source_local:
		src_dir = ("cd test1; ../%s/rdiff-backup --server::../%s" %
				   (SourceDir, src_dir))
	if not dest_local:
		dest_dir = ("test2/tmp; ../../%s/rdiff-backup --server::../../%s" %
					(SourceDir, dest_dir))

	cmdargs = [RBBin, extra_options]
	if not (source_local and dest_local): cmdargs.append("--remote-schema %s")

	if current_time: cmdargs.append("--current-time %s" % current_time)
	cmdargs.extend([src_dir, dest_dir])
	cmdline = " ".join(cmdargs)
	print "Executing: ", cmdline
	assert not os.system(cmdline)

def cmd_schemas2rps(schema_list, remote_schema):
	"""Input list of file descriptions and the remote schema, return rps

	File descriptions should be strings of the form 'hostname.net::foo'

	"""
	return map(SetConnections.cmdpair2rp,
			   SetConnections.get_cmd_pairs(schema_list, remote_schema))

def InternalBackup(source_local, dest_local, src_dir, dest_dir,
				   current_time = None):
	"""Backup src to dest internally

	This is like rdiff_backup but instead of running a separate
	rdiff-backup script, use the separate *.py files.  This way the
	script doesn't have to be rebuild constantly, and stacktraces have
	correct line/file references.

	"""
	Globals.current_time = current_time
	#_reset_connections()
	remote_schema = '%s'

	if not source_local:
		src_dir = "cd test1; python ../server.py ../%s::../%s" % \
				  (SourceDir, src_dir)
	if not dest_local:
		dest_dir = "cd test2/tmp; python ../../server.py ../../%s::../../%s" \
				   % (SourceDir, dest_dir)

	rpin, rpout = cmd_schemas2rps([src_dir, dest_dir], remote_schema)
	Main.misc_setup([rpin, rpout])
	Main.Backup(rpin, rpout)
	Main.cleanup()

def InternalMirror(source_local, dest_local, src_dir, dest_dir):
	"""Mirror src to dest internally

	like InternalBackup, but only mirror.  Do this through
	InternalBackup, but then delete rdiff-backup-data directory.

	"""
	# Save attributes of root to restore later
	src_root = rpath.RPath(Globals.local_connection, src_dir)
	dest_root = rpath.RPath(Globals.local_connection, dest_dir)
	dest_rbdir = dest_root.append("rdiff-backup-data")
	dest_incdir = dest_rbdir.append("increments")

	# We need to create these directories or else failure because
	# --force option not given.
	if not dest_root.lstat(): dest_root.mkdir()
	if not dest_rbdir.lstat(): dest_rbdir.mkdir()
	if not dest_incdir.lstat(): dest_incdir.mkdir()
	
	InternalBackup(source_local, dest_local, src_dir, dest_dir)
	dest_root.setdata()
	Myrm(dest_rbdir.path)
	# Restore old attributes
	rpath.copy_attribs(src_root, dest_root)

def InternalRestore(mirror_local, dest_local, mirror_dir, dest_dir, time):
	"""Restore mirror_dir to dest_dir at given time

	This will automatically find the increments.XXX.dir representing
	the time specified.  The mirror_dir and dest_dir are relative to
	the testing directory and will be modified for remote trials.

	"""
	Main.force = 1
	remote_schema = '%s'
	#_reset_connections()
	if not mirror_local:
		mirror_dir = "cd test1; python ../server.py ../%s::../%s" % \
					 (SourceDir, mirror_dir)
	if not dest_local:
		dest_dir = "cd test2/tmp; python ../../server.py ../../%s::../../%s" \
				   % (SourceDir, dest_dir)

	mirror_rp, dest_rp = cmd_schemas2rps([mirror_dir, dest_dir], remote_schema)
	Main.misc_setup([mirror_rp, dest_rp])
	inc = get_increment_rp(mirror_rp, time)
	if inc: Main.Restore(get_increment_rp(mirror_rp, time), dest_rp)
	else: # use alternate syntax
		Main.restore_timestr = str(time)
		Main.RestoreAsOf(mirror_rp, dest_rp)
	Main.cleanup()

def get_increment_rp(mirror_rp, time):
	"""Return increment rp matching time in seconds"""
	data_rp = mirror_rp.append("rdiff-backup-data")
	if not data_rp.isdir(): return None
	for filename in data_rp.listdir():
		rp = data_rp.append(filename)
		if rp.isincfile() and rp.getincbase_str() == "increments":
			if rp.getinctime() == time: return rp
	return None # Couldn't find appropriate increment

def _reset_connections(src_rp, dest_rp):
	"""Reset some global connection information"""
	Globals.isbackup_reader = Globals.isbackup_writer = None
	#Globals.connections = [Globals.local_connection]
	#Globals.connection_dict = {0: Globals.local_connection}
	SetConnections.UpdateGlobal('rbdir', None)
	Main.misc_setup([src_rp, dest_rp])

def CompareRecursive(src_rp, dest_rp, compare_hardlinks = 1,
					 equality_func = None, exclude_rbdir = 1,
					 ignore_tmp_files = None):
	"""Compare src_rp and dest_rp, which can be directories

	This only compares file attributes, not the actual data.  This
	will overwrite the hardlink dictionaries if compare_hardlinks is
	specified.

	"""
	if compare_hardlinks: reset_hardlink_dicts()
	src_rp.setdata()
	dest_rp.setdata()

	Log("Comparing %s and %s, hardlinks %s" % (src_rp.path, dest_rp.path,
											   compare_hardlinks), 3)
	src_select = selection.Select(src_rp)
	dest_select = selection.Select(dest_rp)

	if ignore_tmp_files:
		# Ignoring temp files can be useful when we want to check the
		# correctness of a backup which aborted in the middle.  In
		# these cases it is OK to have tmp files lying around.
		src_select.add_selection_func(src_select.regexp_get_sf(
			".*rdiff-backup.tmp.[^/]+$", 0))
		dest_select.add_selection_func(dest_select.regexp_get_sf(
			".*rdiff-backup.tmp.[^/]+$", 0))

	if exclude_rbdir:
		src_select.parse_rbdir_exclude()
		dest_select.parse_rbdir_exclude()
	else:
		# include rdiff-backup-data/increments
		src_select.add_selection_func(src_select.glob_get_tuple_sf(
			('rdiff-backup-data', 'increments'), 1))
		dest_select.add_selection_func(dest_select.glob_get_tuple_sf(
			('rdiff-backup-data', 'increments'), 1))
		
		# but exclude rdiff-backup-data
		src_select.add_selection_func(src_select.glob_get_tuple_sf(
			('rdiff-backup-data',), 0))
		dest_select.add_selection_func(dest_select.glob_get_tuple_sf(
			('rdiff-backup-data',), 0))

	dsiter1, dsiter2 = src_select.set_iter(), dest_select.set_iter()

	def hardlink_equal(src_rorp, dest_rorp):
		if not src_rorp.equal_verbose(dest_rorp): return None
		if Hardlink.rorp_eq(src_rorp, dest_rorp): return 1
		Log("%s: %s" % (src_rorp.index, Hardlink.get_indicies(src_rorp, 1)), 3)
		Log("%s: %s" % (dest_rorp.index,
						Hardlink.get_indicies(dest_rorp, None)), 3)
		return None

	def rbdir_equal(src_rorp, dest_rorp):
		"""Like hardlink_equal, but make allowances for data directories"""
		if not src_rorp.index and not dest_rorp.index: return 1
		if (src_rorp.index and src_rorp.index[0] == 'rdiff-backup-data' and
			src_rorp.index == dest_rorp.index):
			# Don't compare dirs - they don't carry significant info
			if dest_rorp.isdir() and src_rorp.isdir(): return 1
			if dest_rorp.isreg() and src_rorp.isreg():
				# Don't compare gzipped files because it is apparently
				# non-deterministic.
				if dest_rorp.index[-1].endswith('gz'): return 1
				# Don't compare .missing increments because they don't matter
				if dest_rorp.index[-1].endswith('.missing'): return 1
		if compare_hardlinks:
			if Hardlink.rorp_eq(src_rorp, dest_rorp): return 1
		elif src_rorp.equal_verbose(dest_rorp): return 1
		Log("%s: %s" % (src_rorp.index, Hardlink.get_indicies(src_rorp, 1)), 3)
		Log("%s: %s" % (dest_rorp.index,
						Hardlink.get_indicies(dest_rorp, None)), 3)
		return None

	if equality_func: result = lazy.Iter.equal(dsiter1, dsiter2,
											   1, equality_func)
	elif compare_hardlinks:
		dsiter1 = Hardlink.add_rorp_iter(dsiter1, 1)
		dsiter2 = Hardlink.add_rorp_iter(dsiter2, None)		
		if exclude_rbdir:
			result = lazy.Iter.equal(dsiter1, dsiter2, 1, hardlink_equal)
		else: result = lazy.Iter.equal(dsiter1, dsiter2, 1, rbdir_equal)
	elif not exclude_rbdir:
		result = lazy.Iter.equal(dsiter1, dsiter2, 1, rbdir_equal)
	else: result = lazy.Iter.equal(dsiter1, dsiter2, 1)

	for i in dsiter1: pass # make sure all files processed anyway
	for i in dsiter2: pass
	return result

def reset_hardlink_dicts():
	"""Clear the hardlink dictionaries"""
	Hardlink._src_inode_indicies = {}
	Hardlink._src_index_indicies = {}
	Hardlink._dest_inode_indicies = {}
	Hardlink._dest_index_indicies = {}
	Hardlink._restore_index_path = {}

def BackupRestoreSeries(source_local, dest_local, list_of_dirnames,
						compare_hardlinks = 1,
						dest_dirname = "testfiles/output",
						restore_dirname = "testfiles/rest_out",
						compare_backups = 1):
	"""Test backing up/restoring of a series of directories

	The dirnames correspond to a single directory at different times.
	After each backup, the dest dir will be compared.  After the whole
	set, each of the earlier directories will be recovered to the
	restore_dirname and compared.

	"""
	Globals.set('preserve_hardlinks', compare_hardlinks)
	time = 10000
	dest_rp = rpath.RPath(Globals.local_connection, dest_dirname)
	restore_rp = rpath.RPath(Globals.local_connection, restore_dirname)
	
	Myrm(dest_dirname)
	for dirname in list_of_dirnames:
		src_rp = rpath.RPath(Globals.local_connection, dirname)
		reset_hardlink_dicts()
		_reset_connections(src_rp, dest_rp)

		InternalBackup(source_local, dest_local, dirname, dest_dirname, time)
		time += 10000
		_reset_connections(src_rp, dest_rp)
		if compare_backups:
			assert CompareRecursive(src_rp, dest_rp, compare_hardlinks)

	time = 10000
	for dirname in list_of_dirnames[:-1]:
		reset_hardlink_dicts()
		Myrm(restore_dirname)
		InternalRestore(dest_local, source_local, dest_dirname,
						restore_dirname, time)
		src_rp = rpath.RPath(Globals.local_connection, dirname)
		assert CompareRecursive(src_rp, restore_rp)

		# Restore should default back to newest time older than it
		# with a backup then.
		if time == 20000: time = 21000

		time += 10000

def MirrorTest(source_local, dest_local, list_of_dirnames,
			   compare_hardlinks = 1,
			   dest_dirname = "testfiles/output"):
	"""Mirror each of list_of_dirnames, and compare after each"""
	Globals.set('preserve_hardlinks', compare_hardlinks)
	dest_rp = rpath.RPath(Globals.local_connection, dest_dirname)

	Myrm(dest_dirname)
	for dirname in list_of_dirnames:
		src_rp = rpath.RPath(Globals.local_connection, dirname)
		reset_hardlink_dicts()
		_reset_connections(src_rp, dest_rp)

		InternalMirror(source_local, dest_local, dirname, dest_dirname)
		_reset_connections(src_rp, dest_rp)
		assert CompareRecursive(src_rp, dest_rp, compare_hardlinks)
