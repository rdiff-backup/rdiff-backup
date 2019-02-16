from __future__ import generators
import unittest, os, re, sys, time
from commontest import *
from rdiff_backup import Globals, log, rpath, robust, FilenameMapping

"""Regression tests"""

Globals.exclude_mirror_regexps = [re.compile(".*/rdiff-backup-data")]
log.Log.setverbosity(3)

lc = Globals.local_connection

class Local:
	"""This is just a place to put increments relative to the local
	connection"""
	def get_local_rp(extension):
		return rpath.RPath(Globals.local_connection, "testfiles/" + extension)

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
	timbar_out = get_local_rp('timbar.pyc') # in cur directory

	wininc2 = get_local_rp('win-increment2')
	wininc3 = get_local_rp('win-increment3')

class PathSetter(unittest.TestCase):
	def setUp(self):
		self.reset_schema()

	def reset_schema(self):
		self.rb_schema = (SourceDir +
						  "/../rdiff-backup -v5 --no-compare-inode " 
						  "--remote-schema './chdir-wrapper2 %s' ")

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
		self.exec_rb_extra_args(time, '', *args)

	def exec_rb_extra_args(self, time, extra_args, *args):
		self.exec_rb_extra_args_retval(time, extra_args, 0, *args)

	def exec_rb_extra_args_retval(self, time, extra_args, ret_val, *args):
		"""Like exec_rb_extra_args, but require return val to be ret_val

		Because of some problems I have with os.system, return val is
		only accurate to 0 or non-zero.

		"""
		arglist = []
		if time: arglist.extend(["--current-time",  str(time)])
		if args[0][0] == "/": arglist.append(args[0])
		else: arglist.append(self.src_prefix + args[0])
		if len(args) > 1:
			if args[1][0] == "/": arglist.append(args[1])
			else: arglist.append(self.dest_prefix + args[1])
			assert len(args) == 2

		arg_string = ' '.join(map(lambda s: "'%s'" % (s,), arglist))
		cmdstr = "%s %s %s" % (self.rb_schema, extra_args, arg_string)
		print "executing " + cmdstr
		actual_val = os.system(cmdstr)
		assert ((actual_val == 0 and ret_val == 0) or
				(actual_val > 0 and ret_val > 0)), \
				"Bad return val %s" % (actual_val,)

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

	def exec_rb_restore_extra_args(self, time, extra_args, *args):
		"""Like exec_rb_restore, but can provide extra arguments"""
		arglist = []
		arglist.append("--restore-as-of %s" % str(time))
		arglist.append(extra_args)
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
							 'testfiles/timbar.pyc testfiles/vft2_out')

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
		self.exec_rb(None, timbar_paths[0], 'testfiles/timbar.pyc')
		self.refresh(Local.timbar_in, Local.timbar_out)
		assert Local.timbar_in.equal_loose(Local.timbar_out)

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

	def getinc_paths(self, basename, directory, quoted = 0):
		"""Return increment.______.dir paths"""
		if quoted:
			FilenameMapping.set_init_quote_vals()
			dirrp = FilenameMapping.QuotedRPath(Globals.local_connection,
												  directory)
		else: dirrp = rpath.RPath(Globals.local_connection, directory)
		incbasenames = [filename for filename in robust.listrp(dirrp)
						if filename.startswith(basename)]
		incbasenames.sort()
		incrps = map(dirrp.append, incbasenames)
		return map(lambda x: x.path,
				   filter(lambda incrp: incrp.isincfile(), incrps))


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

	def testProcLocal(self):
		"""Test initial backup of /proc locally"""
		Myrm("testfiles/procoutput")
		procout = rpath.RPath(Globals.local_connection, 'testfiles/procoutput')
		self.set_connections(None, None, None, None)
		self.exec_rb(10000, '/proc', procout.path)
		time.sleep(1)
		self.exec_rb(20000, '/proc', procout.path)
		time.sleep(1)
		self.exec_rb(30000, Local.inc1rp.path, procout.path)
		assert CompareRecursive(Local.inc1rp, procout)
		time.sleep(1)
		self.exec_rb(40000, '/proc', procout.path)

	def testProcRemote(self):
		"""Test mirroring proc remote"""
		Myrm("testfiles/procoutput")
		procout = rpath.RPath(Globals.local_connection, 'testfiles/procoutput')
		self.set_connections(None, None, "test2/tmp/", "../../")
		self.exec_rb(10000, '/proc', procout.path)
		time.sleep(1)
		self.exec_rb(20000, '/proc', procout.path)
		time.sleep(1)
		self.exec_rb(30000, Local.inc1rp.path, procout.path)
		assert CompareRecursive(Local.inc1rp, procout)
		time.sleep(1)
		self.exec_rb(40000, '/proc', procout.path)

	def testProcRemote2(self):
		"""Test mirroring proc, this time when proc is remote, dest local"""
		Myrm("testfiles/procoutput")
		self.set_connections("test1/", "../", None, None)
		self.exec_rb(None, '/proc', 'testfiles/procoutput')

	def testWindowsMode(self):
		"""Test backup with quoting enabled

		We need to delete from the increment? directories long file
		names, because quoting adds too many extra letters.

		"""
		def delete_long(base_rp, length = 100):
			"""Delete filenames longer than length given"""
			for rp in selection.Select(base_rp).set_iter():
				if len(rp.dirsplit()[1]) > length: rp.delete()

		if not Local.wininc2.lstat() or not Local.wininc3.lstat():
			os.system("cp -a testfiles/increment2 testfiles/win-increment2")
			os.system("cp -a testfiles/increment3 testfiles/win-increment3")
			delete_long(Local.wininc2)
			delete_long(Local.wininc3)

		old_schema = self.rb_schema
		self.rb_schema = old_schema+" --override-chars-to-quote '^a-z0-9_ -.' "
		self.set_connections(None, None, None, None)

		self.delete_tmpdirs()
		# Back up increment2, this contains a file with colons
		self.exec_rb(20000, 'testfiles/win-increment2', 'testfiles/output')
		self.rb_schema = old_schema # Quoting setting should now be saved
		time.sleep(1)

		# Back up increment3
		self.exec_rb(30000, 'testfiles/win-increment3', 'testfiles/output')

		# Now check to make sure no ":" in output directory
		popen_fp = os.popen("find testfiles/output -name '*:*' | wc")
		wc_output = popen_fp.read()
		popen_fp.close()
		assert wc_output.split() == ["0", "0", "0"], wc_output

		# Start restore of increment 2
		Globals.chars_to_quote = '^a-z0-9_ -.'
		inc_paths = self.getinc_paths("increments.",
									  "testfiles/output/rdiff-backup-data", 1)
		Globals.chars_to_quote = None
		assert len(inc_paths) == 1, inc_paths
		self.exec_rb(None, inc_paths[0], 'testfiles/restoretarget2')
		assert CompareRecursive(Local.wininc2, Local.rpout2,
								compare_hardlinks = 0)

		# Restore increment 3 again, using different syntax
		self.rb_schema = old_schema + '-r 30000 '
		self.exec_rb(None, 'testfiles/output', 'testfiles/restoretarget3')
		assert CompareRecursive(Local.wininc3, Local.rpout3,
								compare_hardlinks = 0)
		self.rb_schema = old_schema

	def testLegacy(self):
		"""Test restoring directory with no mirror_metadata file"""
		self.delete_tmpdirs()
		self.set_connections(None, None, None, None)
		self.exec_rb(10000, 'testfiles/various_file_types',
					 'testfiles/output')
		self.exec_rb(20000, 'testfiles/empty', 'testfiles/output')
		assert not os.system(MiscDir + '/myrm testfiles/output/rdiff-backup-data/mirror_metadata*')
		self.exec_rb_extra_args(None, '-r0', 'testfiles/output',
								'testfiles/restoretarget1')
		assert CompareRecursive(Local.vftrp, Local.rpout1,
								compare_hardlinks = 0)


class FinalMisc(PathSetter):
	"""Test miscellaneous operations like list-increments, etc.

	Many of these just run and make sure there were no errors; they
	don't verify the output.

	"""
	def testListIncrementsLocal(self):
		"""Test --list-increments switch.  Assumes restoretest3 valid rd dir"""
		self.set_connections(None, None, None, None)
		self.exec_rb_extra_args(None, "--list-increments",
								"testfiles/restoretest3")

	def testListIncrementsRemote(self):
		"""Test --list-increments mode remotely.  Uses restoretest3"""
		self.set_connections('test1', '../', None, None)
		self.exec_rb_extra_args(None, "--list-increments",
								"testfiles/restoretest3")

	def testListChangeSinceLocal(self):
		"""Test --list-changed-since mode locally.  Uses restoretest3"""
		self.set_connections(None, None, None, None)
		self.exec_rb_extra_args(None, '--list-changed-since 10000',
								'testfiles/restoretest3')
		self.exec_rb_extra_args(None, '--list-changed-since 2B',
								'testfiles/restoretest3')

	def testListChangeSinceRemote(self):
		"""Test --list-changed-since mode remotely.  Uses restoretest3"""
		self.set_connections('test1', '../', None, None)
		self.exec_rb_extra_args(None, '--list-changed-since 10000',
								'testfiles/restoretest3')

	def testListAtTimeLocal(self):
		"""Test --list-at-time mode locally.  Uses restoretest3"""
		self.set_connections(None, None, None, None)
		self.exec_rb_extra_args(None, '--list-at-time 20000',
								'testfiles/restoretest3')
		
	def testListAtTimeRemote(self):
		"""Test --list-at-time mode locally.  Uses restoretest3"""
		self.set_connections('test1', '../', None, None)
		self.exec_rb_extra_args(None, '--list-at-time 20000',
								'testfiles/restoretest3')

	def testListIncrementSizesLocal(self):
		"""Test --list-increment-sizes switch.  Uses restoretest3"""
		self.set_connections(None, None, None, None)
		self.exec_rb_extra_args(None, "--list-increment-sizes",
								"testfiles/restoretest3")

	def testListIncrementSizesRemote(self):
		"""Test --list-increment-sizes switch.  Uses restoretest3"""
		self.set_connections('test1', '../', None, None)
		self.exec_rb_extra_args(None, "--list-increment-sizes",
								"testfiles/restoretest3")

	def testListIncrementsRemote(self):
		"""Test --list-increment-sizes mode remotely.  Uses restoretest3"""
		self.set_connections('test1', '../', None, None)
		self.exec_rb_extra_args(None, "--list-increment-sizes",
								"testfiles/restoretest3")

	def get_all_increments(self, rp):
		"""Iterate all increments at or below given directory"""
		assert rp.isdir()
		dirlist = rp.listdir()
		dirlist.sort()
		for filename in dirlist:
			subrp = rp.append(filename)
			if subrp.isincfile(): yield subrp
			elif subrp.isdir():
				for subsubrp in self.get_all_increments(subrp):
					yield subsubrp

	def testRemoveOlderThan(self):
		"""Test --remove-older-than.  Uses restoretest3"""
		Myrm("testfiles/output")
		assert not os.system("cp -a testfiles/restoretest3 testfiles/output")
		self.set_connections(None, None, None, None)
		self.exec_rb_extra_args(None, "--remove-older-than 20000",
								"testfiles/output")
		rbdir = rpath.RPath(Globals.local_connection,
							"testfiles/output/rdiff-backup-data")
		for inc in self.get_all_increments(rbdir):
			assert inc.getinctime() >= 20000

	def testRemoveOlderThan2(self):
		"""Test --remove-older-than, but '1B'.  Uses restoretest3"""
		Myrm("testfiles/output")
		assert not os.system("cp -a testfiles/restoretest3 testfiles/output")
		self.set_connections(None, None, None, None)
		self.exec_rb_extra_args(None, "--remove-older-than 1B --force",
								"testfiles/output")
		rbdir = rpath.RPath(Globals.local_connection,
							"testfiles/output/rdiff-backup-data")
		for inc in self.get_all_increments(rbdir):
			assert inc.getinctime() >= 30000

	def testRemoveOlderThanCurrent(self):
		"""Make sure --remove-older-than doesn't delete current incs"""
		Myrm("testfiles/output")
		assert not os.system('cp -a testfiles/restoretest3 testfiles/output')
		self.set_connections(None, None, None, None)
		self.exec_rb_extra_args(None, '--remove-older-than now --force',
								'testfiles/output')
		rbdir = rpath.RPath(Globals.local_connection,
							"testfiles/output/rdiff-backup-data")

		has_cur_mirror, has_metadata = 0, 0
		for inc in self.get_all_increments(rbdir):
			if inc.getincbase().index[-1] == 'current_mirror':
				has_cur_mirror = 1
			elif inc.getincbase().index[-1] == 'mirror_metadata':
				has_metadata = 1
		assert has_cur_mirror and has_metadata, (has_cur_mirror, has_metadata)

	def testRemoveOlderThanQuoting(self):
		"""Test --remove-older-than when dest directory is quoted"""
		Myrm("testfiles/output")
		self.set_connections(None, None, None, None)
		self.exec_rb_extra_args(None, "--override-chars-to-quote '^a-z0-9_ -.'"
		  " --current-time 10000", "testfiles/increment1", "testfiles/output")
		self.exec_rb_extra_args(None, "--override-chars-to-quote '^a-z0-9_ -.'"
		  " --current-time 20000", "testfiles/increment2", "testfiles/output")
		self.exec_rb_extra_args(None, "--remove-older-than now",
								"testfiles/output")

	def testRemoveOlderThanRemote(self):
		"""Test --remove-older-than remotely"""
		Myrm("testfiles/output")
		assert not os.system("cp -a testfiles/restoretest3 testfiles/output")
		self.set_connections("test1/", "../", None, None)
		self.exec_rb_extra_args(None, "--remove-older-than 20000",
								"testfiles/output")
		rbdir = rpath.RPath(Globals.local_connection,
							"testfiles/output/rdiff-backup-data")
		for inc in self.get_all_increments(rbdir):
			assert inc.getinctime() >= 20000


class FinalSelection(PathSetter):
	"""Test selection options"""
	def system(self, cmd):
		print "Executing: ", cmd
		assert not os.system(cmd)

	def testSelLocal(self):
		"""Quick backup testing a few selection options"""
		self.delete_tmpdirs()

		# Test --include option
		assert not \
			 self.system(self.rb_schema +
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
		mirror_rp = rpath.RPath(Globals.local_connection, "testfiles/output")
		restore_filename = get_increment_rp(mirror_rp, 10000).path
		self.system(self.rb_schema +
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
		excluderp = rpath.RPath(Globals.local_connection,
								"testfiles/vft_out/exclude")
		fp = excluderp.open("w")
		fp.write("""
../testfiles/various_file_types/regular_file
../testfiles/various_file_types/test
""")
		assert not fp.close()

		# Make an include list
		includerp = rpath.RPath(Globals.local_connection,
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

	def testSelRestoreLocal(self):
		"""Test selection options when restoring locally"""
		self.set_connections(None, None, None, None)
		self.run_sel_restore_test()

	def testSelRestoreRemote(self):
		"""Test selection options when both sides are remote"""
		self.set_connections("test1/", "../", "test2/tmp/", "../../")
		self.run_sel_restore_test("../../")

	def run_sel_restore_test(self, prefix = ""):
		"""Test selection options with restore"""
		self.make_restore_sel_dir()
		existing_file = self.make_restore_existing_target()
		file1_target = Local.rpout1.append("file1")
		file2_target = Local.rpout1.append("file2")
		excludes = ("--exclude %s --exclude %s --force" %
					(prefix + file1_target.path, prefix + existing_file.path))
		self.exec_rb_restore_extra_args("now", excludes,
										Local.rpout.path, Local.rpout1.path)
		for rp in (file1_target, file2_target, existing_file):
			rp.setdata()
		assert not file1_target.lstat(), file1_target.lstat()
		assert file2_target.lstat()
		assert existing_file.lstat() # excluded file shouldn't be deleted

	def make_restore_sel_dir(self):
		"""Create rdiff-backup repository at Local.rpout"""
		self.delete_tmpdirs()
		Local.vft_in.mkdir()
		rp1 = Local.vft_in.append("file1")
		rp2 = Local.vft_in.append("file2")
		rp1.touch()
		rp2.touch()
		self.exec_rb(None, Local.vft_in.path, Local.rpout.path)
		Myrm(Local.vft_in.path)

	def make_restore_existing_target(self):
		"""Create an existing file in the restore target directory"""
		Local.rpout1.mkdir()
		existing_file = Local.rpout1.append("existing_file")
		existing_file.touch()
		return existing_file

class FinalCorrupt(PathSetter):
	"""Test messing with things a bit and making sure they still work"""
	def make_dir(self):
		self.delete_tmpdirs()
		rp1 = rpath.RPath(Globals.local_connection, 'testfiles/final_deleted1')
		if rp1.lstat(): Myrm(rp1.path)
		rp1.mkdir()
		rp1_1 = rp1.append('regfile')
		rp1_1.touch()
		rp1_2 = rp1.append('dir')
		rp1_2.mkdir()
		rp1_2_1 = rp1_2.append('regfile2')
		rp1_2_1.write_string('foo')

		rp2 = rpath.RPath(Globals.local_connection, 'testfiles/final_deleted2')
		if rp2.lstat(): Myrm(rp2.path)
		os.system('cp -a %s %s' % (rp1.path, rp2.path))
		rp2_2_1 = rp2.append('dir').append('regfile2')
		assert rp2_2_1.lstat()
		rp2_2_1.delete()
		rp2_2_1.touch()
		return rp1, rp1_2, rp2

	def test_dest_delete(self):
		"""Test deleting a directory from the destination dir

		Obviously that directory can no longer be restored, but the
		rest of the files should be OK.  Just runs locally for now.

		"""
		in_dir1, in_subdir, in_dir2 = self.make_dir()
		self.set_connections(None, None, None, None)
		self.exec_rb(10000, in_dir1.path, 'testfiles/output')

		out_subdir = rpath.RPath(Globals.local_connection,
								 'testfiles/output/%s' %
								 (in_subdir.index[-1],))
		log.Log("Deleting %s" % (out_subdir.path,), 3)
		out_subdir.delete()
		self.exec_rb(20000, in_dir2.path, 'testfiles/output')

		self.exec_rb_restore(10000, 'testfiles/output',
							 'testfiles/restoretarget1')


class FinalBugs(PathSetter):
	"""Test for specific bugs that have been reported"""
	def test_symlink_popple(self):
		"""Test for Popple's symlink bug

		Earlier, certain symlinks could cause data loss in _source_
		directory when regressing.  See mailing lists around 4/2/05
		for more info.

		"""
		self.delete_tmpdirs()
		self.set_connections(None, None, None, None)

		# Make directories
		rp1 = rpath.RPath(Globals.local_connection, 'testfiles/sym_in1')
		if rp1.lstat(): rp1.delete()
		rp1.mkdir()
		rp1_d = rp1.append('subdir')
		rp1_d.mkdir()
		rp1_d_f = rp1_d.append('file')
		rp1_d_f.touch()
		
		rp2 = rpath.RPath(Globals.local_connection, 'testfiles/sym_in2')
		if rp2.lstat(): rp2.delete()
		rp2.mkdir()
		rp2_s = rp2.append('subdir')
		rp2_s.symlink("%s/%s" % (os.getcwd(), rp1_d.path))

		# Backup
		self.exec_rb(10000, rp1.path, 'testfiles/output')
		self.exec_rb(20000, rp2.path, 'testfiles/output')

		# Make failed backup
		rbdir = rpath.RPath(Globals.local_connection,
							'testfiles/output/rdiff-backup-data')
		curmir = rbdir.append('current_mirror.%s.data' %
							  (Time.timetostring(30000),))
		curmir.touch()

		# Regress
		self.exec_rb_extra_args(30000, '--check-destination-dir',
								'testfiles/output')

		# Check to see if file still there
		rp1_d_f.setdata()
		assert rp1_d_f.isreg(), 'File %s corrupted' % (rp1_d_f.path,)

	def test_CCPP_keyerror(self):
		"""Test when no change until middle of a directory

		This tests CCPP, to make sure it isn't asked to provide rorps
		for indicies that are out of the cache.

		"""
		self.delete_tmpdirs()
		rdiff_backup(1, 1, 'testfiles/bigdir', 'testfiles/output')
		rp = rpath.RPath(Globals.local_connection,
						 'testfiles/bigdir/subdir3/subdir49/file49')
		assert rp.isreg(), rp
		rp.touch()
		rdiff_backup(1, 1, 'testfiles/bigdir', 'testfiles/output')
		
if __name__ == "__main__": unittest.main()
