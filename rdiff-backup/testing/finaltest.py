import unittest, os, re, sys
from commontest import *
from rdiff_backup.log import *
from rdiff_backup.rpath import *
from rdiff_backup import Globals

"""Regression tests"""

Globals.exclude_mirror_regexps = [re.compile(".*/rdiff-backup-data")]
Log.setverbosity(7)

lc = Globals.local_connection

class Local:
	"""This is just a place to put increments relative to the local
	connection"""
	def get_local_rp(extension):
		return RPath(Globals.local_connection, "testfiles/" + extension)

	vftrp = get_local_rp('various_file_types')
	inc1rp = get_local_rp('increment1')
	inc2rp = get_local_rp('increment2')
	inc3rp = get_local_rp('increment3')
	inc4rp = get_local_rp('increment4')

	rpout = get_local_rp('output')
	rpout_inc = get_local_rp('output_inc')
	rpout1 = get_local_rp('restoretarget1')
	rpout2 = get_local_rp('restoretarget2')
	rpout3 = get_local_rp('restoretarget3')
	rpout4 = get_local_rp('restoretarget4')

	prefix = get_local_rp('.')

	vft_in = get_local_rp('vft_out')
	vft_out = get_local_rp('increment2/various_file_types')
	vft2_in = get_local_rp('vft2_out')

	timbar_in = get_local_rp('increment1/timbar.pyc')
	timbar_out = get_local_rp('../timbar.pyc') # in cur directory

class PathSetter(unittest.TestCase):
	def setUp(self):
		self.reset_schema()

	def reset_schema(self):
		self.rb_schema = SourceDir + \
			 "/../rdiff-backup -v3 --remote-schema './chdir-wrapper2 %s' "

	def refresh(self, *rp_list):
		"""Reread data for the given rps"""
		for rp in rp_list: rp.setdata()

	def set_connections(self, src_pre, src_back, dest_pre, dest_back):
		"""Set source and destination prefixes"""
		if src_pre: self.src_prefix = "%s::%s" % (src_pre, src_back)
		else: self.src_prefix = './'

		if dest_pre: self.dest_prefix = "%s::%s" % (dest_pre, dest_back)
		else: self.dest_prefix = './'

	def exec_rb(self, time, *args):
		"""Run rdiff-backup on given arguments"""
		arglist = []
		if time: arglist.append("--current-time %s" % str(time))
		arglist.append(self.src_prefix + args[0])
		if len(args) > 1:
			arglist.append(self.dest_prefix + args[1])
			assert len(args) == 2

		cmdstr = self.rb_schema + ' '.join(arglist)
		print "executing " + cmdstr
		assert not os.system(cmdstr)

	def exec_rb_extra_args(self, time, extra_args, *args):
		"""Run rdiff-backup on given arguments"""
		arglist = []
		if time: arglist.append("--current-time %s" % str(time))
		arglist.append(self.src_prefix + args[0])
		if len(args) > 1:
			arglist.append(self.dest_prefix + args[1])
			assert len(args) == 2

		cmdstr = "%s %s %s" % (self.rb_schema, extra_args, ' '.join(arglist))
		print "executing " + cmdstr
		assert not os.system(cmdstr)

	def exec_rb_restore(self, time, *args):
		"""Restore using rdiff-backup's new syntax and given time"""
		arglist = []
		arglist.append("--restore-as-of %s" % str(time))
		arglist.append(self.src_prefix + args[0])
		if len(args) > 1:
			arglist.append(self.dest_prefix + args[1])
			assert len(args) == 2

		cmdstr = self.rb_schema + " ".join(arglist)
		print "Restoring via cmdline: " + cmdstr
		assert not os.system(cmdstr)

	def delete_tmpdirs(self):
		"""Remove any temp directories created by previous tests"""
		assert not os.system(MiscDir + '/myrm testfiles/output* '
							 'testfiles/restoretarget* testfiles/vft_out '
							 'timbar.pyc testfiles/vft2_out')

	def runtest(self):
		self.delete_tmpdirs()

		# Backing up increment1
		self.exec_rb(10000, 'testfiles/increment1', 'testfiles/output')
		assert CompareRecursive(Local.inc1rp, Local.rpout)
		time.sleep(1)

		# Backing up increment2
		self.exec_rb(20000, 'testfiles/increment2', 'testfiles/output')
		assert CompareRecursive(Local.inc2rp, Local.rpout)
		time.sleep(1)

		# Backing up increment3
		self.exec_rb(30000, 'testfiles/increment3', 'testfiles/output')
		assert CompareRecursive(Local.inc3rp, Local.rpout)
		time.sleep(1)

		# Backing up increment4
		self.exec_rb(40000, 'testfiles/increment4', 'testfiles/output')
		assert CompareRecursive(Local.inc4rp, Local.rpout)

		# Getting restore rps
		inc_paths = self.getinc_paths("increments.",
									  "testfiles/output/rdiff-backup-data")
		assert len(inc_paths) == 3

		# Restoring increment1
		self.exec_rb(None, inc_paths[0], 'testfiles/restoretarget1')
		assert CompareRecursive(Local.inc1rp, Local.rpout1)

		# Restoring increment2
		self.exec_rb(None, inc_paths[1], 'testfiles/restoretarget2')
		assert CompareRecursive(Local.inc2rp, Local.rpout2)

		# Restoring increment3
		self.exec_rb(None, inc_paths[2], 'testfiles/restoretarget3')
		assert CompareRecursive(Local.inc3rp, Local.rpout3)

		# Test restoration of a few random files
		vft_paths = self.getinc_paths("various_file_types.",
					     "testfiles/output/rdiff-backup-data/increments")
		self.exec_rb(None, vft_paths[1], 'testfiles/vft_out')
		self.refresh(Local.vft_in, Local.vft_out)
		assert CompareRecursive(Local.vft_in, Local.vft_out)

		timbar_paths = self.getinc_paths("timbar.pyc.",
						 "testfiles/output/rdiff-backup-data/increments")
		self.exec_rb(None, timbar_paths[0])
		self.refresh(Local.timbar_in, Local.timbar_out)
		assert RPath.cmp_with_attribs(Local.timbar_in, Local.timbar_out)

		self.exec_rb_restore(25000, 'testfiles/output/various_file_types',
							 'testfiles/vft2_out')
		self.refresh(Local.vft2_in, Local.vft_out)
		assert CompareRecursive(Local.vft2_in, Local.vft_out)

		# Make sure too many increment files not created
		assert len(self.getinc_paths("nochange.",
			  "testfiles/output/rdiff-backup-data/increments")) == 0
		nochange_incs = len(self.getinc_paths("",
			"testfiles/output/rdiff-backup-data/increments/nochange"))
		assert nochange_incs == 1 or nochange_incs == 0, nochange_incs

	def getinc_paths(self, basename, directory):
		"""Return increment.______.dir paths"""
		incfiles = filter(lambda s: s.startswith(basename),
						  os.listdir(directory))
		incfiles.sort()
		incrps = map(lambda f: RPath(lc, directory+"/"+f), incfiles)
		return map(lambda x: x.path, filter(RPath.isincfile, incrps))


class Final(PathSetter):
	def testLocal(self):
		"""Run test sequence everything local"""
		self.set_connections(None, None, None, None)
		self.runtest()

	def testRemoteAll(self):
		"""Run test sequence everything remote"""
		self.set_connections("test1/", '../', 'test2/tmp/', '../../')
		self.runtest()

	def testRemoteSource(self):
		"""Run test sequence when remote side is source"""
		self.set_connections("test1/", "../", None, None)
		self.runtest()

	def testRemoteDest(self):
		"""Run test sequence when remote side is destination"""
		self.set_connections(None, None, "test2/tmp", "../../")
		self.runtest()

	def testMirroringLocal(self):
		"""Run mirroring only everything remote"""
		self.delete_tmpdirs()
		self.set_connections(None, None, None, None)
		self.exec_rb_extra_args(10000, "-m",
								"testfiles/various_file_types",
								"testfiles/output")
		assert CompareRecursive(Local.vftrp, Local.rpout, exclude_rbdir = None)

	def testMirroringRemote(self):
		"""Run mirroring only everything remote"""
		self.delete_tmpdirs()
		self.set_connections("test1/", "../", "test2/tmp/", "../../")
		self.exec_rb_extra_args(10000, "-m",
								"testfiles/various_file_types",
								"testfiles/output")
		assert CompareRecursive(Local.vftrp, Local.rpout, exclude_rbdir = None)

	def testProcRemote(self):
		"""Test mirroring proc"""
		self.set_connections(None, None, "test2/tmp/", "../../")
		self.exec_rb(None, '../../../../../../proc', 'testfiles/procoutput')

	def testWindowsMode(self):
		"""Test backup with the --windows-mode option"""
		old_schema = self.rb_schema
		self.rb_schema = old_schema + " --windows-mode "
		self.set_connections(None, None, None, None)

		self.delete_tmpdirs()
		
		# Back up increment2, this contains a file with colons
		self.exec_rb(20000, 'testfiles/increment2', 'testfiles/output')
		time.sleep(1)

		# Back up increment3
		self.exec_rb(30000, 'testfiles/increment3', 'testfiles/output')

		Globals.time_separator = "_"
		inc_paths = self.getinc_paths("increments.",
									  "testfiles/output/rdiff-backup-data")
		Globals.time_separator = ":"
		assert len(inc_paths) == 1
		# Restore increment2
		self.exec_rb(None, inc_paths[0], 'testfiles/restoretarget2')
		assert CompareRecursive(Local.inc2rp, Local.rpout2)

		# Now check to make sure no ":" in output directory
		popen_fp = os.popen("find testfiles/output -name '*:*' | wc")
		wc_output = popen_fp.read()
		popen_fp.close()
		assert wc_output.split() == ["0", "0", "0"], wc_output


class FinalSelection(PathSetter):
	"""Test selection options"""
	def testSelLocal(self):
		"""Quick backup testing a few selection options"""
		self.delete_tmpdirs()

		# Test --include option
		assert not \
			   os.system(self.rb_schema +
						 "--current-time 10000 "
						 "--include testfiles/increment2/various_file_types "
						 "--exclude '**' "
						 "testfiles/increment2 testfiles/output")

		assert os.lstat("testfiles/output/various_file_types/regular_file")
		self.assertRaises(OSError, os.lstat, "testfiles/output/test.py")

		# Now try reading list of files
		fp = os.popen(self.rb_schema +
					  "--current-time 20000 "
					  "--include-filelist-stdin --exclude '**' "
					  "testfiles/increment2 testfiles/output", "w")
		fp.write("""
testfiles/increment2/test.py
testfiles/increment2/changed_dir""")
		assert not fp.close()

		assert os.lstat("testfiles/output/changed_dir")
		assert os.lstat("testfiles/output/test.py")
		self.assertRaises(OSError, os.lstat,
						  "testfiles/output/various_file_types")
		self.assertRaises(OSError, os.lstat,
						  "testfiles/output/changed_dir/foo")

		# Test selective restoring
		mirror_rp = RPath(Globals.local_connection, "testfiles/output")
		restore_filename = get_increment_rp(mirror_rp, 10000).path
		assert not os.system(self.rb_schema +
		   "--include testfiles/restoretarget1/various_file_types/"
							 "regular_file "
		   "--exclude '**' " +
		   restore_filename + " testfiles/restoretarget1")
		assert os.lstat("testfiles/restoretarget1/various_file_types/"
						"regular_file")
		self.assertRaises(OSError, os.lstat, "testfiles/restoretarget1/tester")
		self.assertRaises(OSError, os.lstat,
				 "testfiles/restoretarget1/various_file_types/executable")

		fp = os.popen(self.rb_schema +
					  "--include-filelist-stdin " + restore_filename +
					  " testfiles/restoretarget2", "w")
		fp.write("""
- testfiles/restoretarget2/various_file_types/executable""")
		assert not fp.close()
		assert os.lstat("testfiles/restoretarget2/various_file_types/"
						"regular_file")
		self.assertRaises(OSError, os.lstat,
			   "testfiles/restoretarget2/various_file_types/executable")

	def testSelFilesRemote(self):
		"""Test for bug found in 0.7.[34] - filelist where source remote"""
		self.delete_tmpdirs()
		self.set_connections("test1/", "../", 'test2/tmp/', '../../')
		self.rb_schema += ("--exclude-filelist testfiles/vft_out/exclude "
						   "--include-filelist testfiles/vft_out/include "
						   "--exclude '**' ")

		# Make an exclude list
		os.mkdir("testfiles/vft_out")
		excluderp = RPath(Globals.local_connection,
						  "testfiles/vft_out/exclude")
		fp = excluderp.open("w")
		fp.write("""
../testfiles/various_file_types/regular_file
../testfiles/various_file_types/test
""")
		assert not fp.close()

		# Make an include list
		includerp = RPath(Globals.local_connection,
						  "testfiles/vft_out/include")
		fp = includerp.open("w")
		fp.write("""
../testfiles/various_file_types/executable
../testfiles/various_file_types/symbolic_link
../testfiles/various_file_types/regular_file
../testfiles/various_file_types/test
""")
		assert not fp.close()

		self.exec_rb(None, 'testfiles/various_file_types', 'testfiles/output')

		self.reset_schema()
		self.exec_rb_restore("now", 'testfiles/output',
							 'testfiles/restoretarget1')
		assert os.lstat('testfiles/restoretarget1/executable')
		assert os.lstat('testfiles/restoretarget1/symbolic_link')
		self.assertRaises(OSError, os.lstat,
						  'testfiles/restoretarget1/regular_file')
		self.assertRaises(OSError, os.lstat,
						  'testfiles/restoretarget1/executable2')


class FinalCorrupt(PathSetter):
	def testBackupOverlay(self):
		"""Test backing up onto a directory already backed up for that time

		This will test to see if rdiff-backup will ignore files who
		already have an increment where it wants to put something.
		Just make sure rdiff-backup doesn't exit with an error.
		
		"""
		self.delete_tmpdirs()
		assert not os.system("cp -a testfiles/corruptbackup testfiles/output")
		self.set_connections(None, None, None, None)
		self.exec_rb(None, 'testfiles/corruptbackup_source',
					 'testfiles/output')

	def testBackupOverlayRemote(self):
		"""Like above but destination is remote"""
		self.delete_tmpdirs()
		assert not os.system("cp -a testfiles/corruptbackup testfiles/output")
		self.set_connections(None, None, "test1/", '../')
		self.exec_rb(None, 'testfiles/corruptbackup_source',
					 'testfiles/output')

	def testCheckpointData(self):
		"""Destination directory has bad checkpoint data, no sym"""
		self.delete_tmpdirs()
		assert not os.system("cp -a testfiles/corrupt_dest1 testfiles/output")
		self.set_connections(None, None, None, None)
		self.exec_rb(None, 'testfiles/various_file_types', 'testfiles/output')

	def testCheckpointData2(self):
		"""Destination directory has bad checkpoint data, with sym"""
		self.delete_tmpdirs()
		assert not os.system("cp -a testfiles/corrupt_dest2 testfiles/output")
		self.set_connections(None, None, None, None)
		self.exec_rb(None, 'testfiles/various_file_types', 'testfiles/output')
		

		
if __name__ == "__main__": unittest.main()
