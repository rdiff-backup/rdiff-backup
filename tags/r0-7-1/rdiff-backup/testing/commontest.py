"""commontest - Some functions and constants common to several test cases"""
import os

SourceDir = "../src"
AbsCurdir = os.getcwd() # Absolute path name of current directory
AbsTFdir = AbsCurdir+"/testfiles"
MiscDir = "../misc"
__no_execute__ = 1 # Keeps the actual rdiff-backup program from running

def rbexec(src_file):
	"""Changes to the source directory, execfile src_file, return"""
	os.chdir(SourceDir)
	execfile(src_file, globals())
	os.chdir(AbsCurdir)

def Make():
	"""Make sure the rdiff-backup script in the source dir is up-to-date"""
	os.chdir(SourceDir)
	os.system("python ./Make")
	os.chdir(AbsCurdir)

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

	cmdargs = [SourceDir + "/rdiff-backup", extra_options]
	if not (source_local and dest_local): cmdargs.append("--remote-schema %s")

	if current_time: cmdargs.append("--current-time %s" % current_time)

	os.system(" ".join(cmdargs))	

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

	rpin, rpout = SetConnections.InitRPs([src_dir, dest_dir], remote_schema)
	Globals.postset_regexp('no_compression_regexp',
						   Globals.no_compression_regexp_string, re.I)
	_get_main().Backup(rpin, rpout)
	_get_main().cleanup()

def InternalMirror(source_local, dest_local, src_dir, dest_dir,
				   checkpointing = None):
	"""Mirror src to dest internally, like InternalBackup"""
	remote_schema = '%s'

	if not source_local:
		src_dir = "cd test1; python ../server.py ../%s::../%s" % \
				  (SourceDir, src_dir)
	if not dest_local:
		dest_dir = "cd test2/tmp; python ../../server.py ../../%s::../../%s" \
				   % (SourceDir, dest_dir)

	rpin, rpout = SetConnections.InitRPs([src_dir, dest_dir], remote_schema)
	if not rpout.lstat(): rpout.mkdir()
	if checkpointing: # rdiff-backup-data must exist to checkpoint
		data_dir = rpout.append("rdiff-backup-data")
		if not data_dir.lstat(): data_dir.mkdir()
		Globals.add_regexp(data_dir.path, 1)
		SetConnections.UpdateGlobal('rbdir', data_dir)
	HighLevel.Mirror(rpin, rpout, checkpointing)
	_get_main().cleanup()

def InternalRestore(mirror_local, dest_local, mirror_dir, dest_dir, time):
	"""Restore mirror_dir to dest_dir at given time

	This will automatically find the increments.XXX.dir representing
	the time specified.  The mirror_dir and dest_dir are relative to
	the testing directory and will be modified for remote trials.

	"""
	remote_schema = '%s'
	#_reset_connections()
	if not mirror_local:
		mirror_dir = "cd test1; python ../server.py ../%s::../%s" % \
					 (SourceDir, mirror_dir)
	if not dest_local:
		dest_dir = "cd test2/tmp; python ../../server.py ../../%s::../../%s" \
				   % (SourceDir, dest_dir)

	mirror_rp, dest_rp = SetConnections.InitRPs([mirror_dir, dest_dir],
												remote_schema)

	def get_increment_rp(time):
		"""Return increment rp matching time"""
		data_rp = mirror_rp.append("rdiff-backup-data")
		for filename in data_rp.listdir():
			rp = data_rp.append(filename)
			if (rp.isincfile() and rp.getincbase_str() == "increments" and
				Time.stringtotime(rp.getinctime()) == time):
				return rp
		assert None, ("No increments.XXX.dir found in directory "
					  "%s with that time" % data_rp.path)

	_get_main().Restore(get_increment_rp(time), dest_rp)
	_get_main().cleanup()

def _reset_connections(src_rp, dest_rp):
	"""Reset some global connection information"""
	Globals.isbackup_reader = Globals.isbackup_writer = None
	#Globals.connections = [Globals.local_connection]
	#Globals.connection_dict = {0: Globals.local_connection}
	SetConnections.UpdateGlobal('rbdir', None)
	SetConnections.UpdateGlobal('exclude_regexps', [])
	SetConnections.UpdateGlobal('exclude_mirror_regexps', [])
	Globals.add_regexp(dest_rp.append("rdiff-backup-data").path, 1)
	Globals.add_regexp(src_rp.append("rdiff-backup-data").path, None)

def _get_main():
	"""Set Globals.Main if it doesn't exist, and return"""
	try: return Globals.Main
	except AttributeError:
		Globals.Main = Main()
		return Globals.Main

def CompareRecursive(src_rp, dest_rp, compare_hardlinks = 1):
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
	dsiter1, dsiter2 = map(DestructiveStepping.Iterate_with_Finalizer,
						   [src_rp, dest_rp], [1, None])

	def hardlink_equal(src_rorp, dest_rorp):
		if src_rorp != dest_rorp: return None
		if Hardlink.rorp_eq(src_rorp, dest_rorp): return 1
		Log("%s: %s" % (src_rorp.index, Hardlink.get_indicies(src_rorp, 1)), 3)
		Log("%s: %s" % (dest_rorp.index,
						Hardlink.get_indicies(dest_rorp, None)), 3)
		return None

	if compare_hardlinks:
		dsiter1 = Hardlink.add_rorp_iter(dsiter1, 1)
		dsiter2 = Hardlink.add_rorp_iter(dsiter2, None)
		result = Iter.equal(dsiter1, dsiter2, 1, hardlink_equal)
	else: result = Iter.equal(dsiter1, dsiter2, 1)

	for i in dsiter1: pass # make sure all files processed anyway
	for i in dsiter2: pass
	return result

def reset_hardlink_dicts():
	"""Clear the hardlink dictionaries"""
	Hardlink._src_inode_indicies = {}
	Hardlink._src_index_indicies = {}
	Hardlink._dest_inode_indicies = {}
	Hardlink._dest_index_indicies = {}

def BackupRestoreSeries(source_local, dest_local, list_of_dirnames,
						compare_hardlinks = 1,
						dest_dirname = "testfiles/output",
						restore_dirname = "testfiles/rest_out"):
	"""Test backing up/restoring of a series of directories

	The dirnames correspond to a single directory at different times.
	After each backup, the dest dir will be compared.  After the whole
	set, each of the earlier directories will be recovered to the
	restore_dirname and compared.

	"""
	Globals.set('preserve_hardlinks', compare_hardlinks)
	time = 10000
	dest_rp = RPath(Globals.local_connection, dest_dirname)
	restore_rp = RPath(Globals.local_connection, restore_dirname)
	
	os.system(MiscDir + "/myrm " + dest_dirname)
	for dirname in list_of_dirnames:
		src_rp = RPath(Globals.local_connection, dirname)
		reset_hardlink_dicts()
		_reset_connections(src_rp, dest_rp)

		InternalBackup(source_local, dest_local, dirname, dest_dirname, time)
		time += 10000
		_reset_connections(src_rp, dest_rp)
		assert CompareRecursive(src_rp, dest_rp, compare_hardlinks)

	time = 10000
	for dirname in list_of_dirnames[:-1]:
		reset_hardlink_dicts()
		os.system(MiscDir + "/myrm " + restore_dirname)
		InternalRestore(dest_local, source_local, dest_dirname,
						restore_dirname, time)
		src_rp = RPath(Globals.local_connection, dirname)
		assert CompareRecursive(src_rp, restore_rp)
		time += 10000

def MirrorTest(source_local, dest_local, list_of_dirnames,
			   compare_hardlinks = 1,
			   dest_dirname = "testfiles/output"):
	"""Mirror each of list_of_dirnames, and compare after each"""
	Globals.set('preserve_hardlinks', compare_hardlinks)
	dest_rp = RPath(Globals.local_connection, dest_dirname)

	os.system(MiscDir + "/myrm " + dest_dirname)
	for dirname in list_of_dirnames:
		src_rp = RPath(Globals.local_connection, dirname)
		reset_hardlink_dicts()
		_reset_connections(src_rp, dest_rp)

		InternalMirror(source_local, dest_local, dirname, dest_dirname)
		_reset_connections(src_rp, dest_rp)
		assert CompareRecursive(src_rp, dest_rp, compare_hardlinks)
