import unittest
from commontest import *
from rdiff_backup import log, restore, Globals, rpath, TempFile

Log.setverbosity(3)
lc = Globals.local_connection
tempdir = rpath.RPath(Globals.local_connection, "testfiles/output")
restore_base_rp = rpath.RPath(Globals.local_connection,
							  "testfiles/restoretest")
restore_base_filenames = restore_base_rp.listdir()
mirror_time = 1041109438 # just some late time

class RestoreFileComparer:
	"""Holds a file to be restored and tests against it

	Each object has a restore file and a dictionary of times ->
	rpaths.  When the restore file is restored to one of the given
	times, the resulting file should be the same as the related rpath.

	"""
	def __init__(self, rf):
		self.rf = rf
		self.time_rp_dict = {}

	def add_rpath(self, rp, t):
		"""Add rp, which represents what rf should be at given time t"""
		assert not self.time_rp_dict.has_key(t)
		self.time_rp_dict[t] = rp

	def compare_at_time(self, t):
		"""Restore file, make sure it is the same at time t"""
		log.Log("Checking result at time %s" % (t,), 7)
		tf = TempFile.new(tempdir.append("foo"))
		restore._mirror_time = mirror_time
		restore._rest_time = t
		self.rf.set_relevant_incs()
		out_rorpath = self.rf.get_attribs().getRORPath()
		correct_result = self.time_rp_dict[t]

		if out_rorpath.isreg():
			out_rorpath.setfile(self.rf.get_restore_fp())
		rpath.copy_with_attribs(out_rorpath, tf)
		assert tf.equal_verbose(correct_result, check_index = 0), \
			   "%s, %s" % (tf, correct_result)
		if tf.isreg():
			assert rpath.cmpfileobj(tf.open("rb"), correct_result.open("rb"))
		if tf.lstat(): tf.delete()

	def compare_all(self):
		"""Check restore results for all available times"""
		for t in self.time_rp_dict.keys(): self.compare_at_time(t)


class RestoreTest(unittest.TestCase):
	"""Test Restore class"""
	def get_rfcs(self):
		"""Return available RestoreFileCompararer objects"""
		base_rf = restore.RestoreFile(restore_base_rp, restore_base_rp, [])
		rfs = base_rf.yield_sub_rfs()
		rfcs = []
		for rf in rfs:
			if rf.mirror_rp.dirsplit()[1] in ["dir"]:
				log.Log("skipping 'dir'", 5)
				continue

			rfc = RestoreFileComparer(rf)
			for inc in rf.inc_list:
				test_time = inc.getinctime()
				rfc.add_rpath(self.get_correct(rf.mirror_rp, test_time),
							  test_time)
			rfc.add_rpath(rf.mirror_rp, mirror_time)
			rfcs.append(rfc)
		return rfcs

	def get_correct(self, mirror_rp, test_time):
		"""Return correct version with base mirror_rp at time test_time"""
		assert -1 < test_time < 2000000000, test_time
		dirname, basename = mirror_rp.dirsplit()
		for filename in restore_base_filenames:
			comps = filename.split(".")
			base = ".".join(comps[:-1])
			t = Time.stringtotime(comps[-1])
			if t == test_time and basename == base:
				return restore_base_rp.append(filename)
		# Correct rp must be empty
		return restore_base_rp.append("%s.%s" %
							 (basename, Time.timetostring(test_time)))

	def testRestoreSingle(self):
		"""Test restoring files one at at a time"""
		MakeOutputDir()
		for rfc in self.get_rfcs():
			if rfc.rf.inc_rp.isincfile(): continue
			log.Log("Comparing %s" % (rfc.rf.inc_rp.path,), 5)
			rfc.compare_all()
		
	def testBothLocal(self):
		"""Test directory restore everything local"""
		self.restore_dir_test(1,1)

	def testMirrorRemote(self):
		"""Test directory restore mirror is remote"""
		self.restore_dir_test(0, 1)

	def testDestRemote(self):
		"""Test directory restore destination is remote"""
		self.restore_dir_test(1, 0)

	def testBothRemote(self):
		"""Test directory restore everything is remote"""
		self.restore_dir_test(0, 0)

	def restore_dir_test(self, mirror_local, dest_local):
		"""Run whole dir tests

		If any of the above tests don't work, try rerunning
		makerestoretest3.

		"""
		Myrm("testfiles/output")
		target_rp = rpath.RPath(Globals.local_connection, "testfiles/output")
		mirror_rp = rpath.RPath(Globals.local_connection,
								"testfiles/restoretest3")
		inc1_rp = rpath.RPath(Globals.local_connection,
							  "testfiles/increment1")
		inc2_rp = rpath.RPath(Globals.local_connection,
							  "testfiles/increment2")
		inc3_rp = rpath.RPath(Globals.local_connection,
							  "testfiles/increment3")
		inc4_rp = rpath.RPath(Globals.local_connection,
							  "testfiles/increment4")

		InternalRestore(mirror_local, dest_local, "testfiles/restoretest3",
						"testfiles/output", 45000)
		assert CompareRecursive(inc4_rp, target_rp)
		InternalRestore(mirror_local, dest_local, "testfiles/restoretest3",
						"testfiles/output", 35000)
		assert CompareRecursive(inc3_rp, target_rp, compare_hardlinks = 0)
		InternalRestore(mirror_local, dest_local, "testfiles/restoretest3",
						"testfiles/output", 25000)
		assert CompareRecursive(inc2_rp, target_rp, compare_hardlinks = 0)
		InternalRestore(mirror_local, dest_local, "testfiles/restoretest3",
						"testfiles/output", 5000)
		assert CompareRecursive(inc1_rp, target_rp, compare_hardlinks = 0)

#	def testRestoreCorrupt(self):
#		"""Test restoring a partially corrupt archive
#
#		The problem here is that a directory is missing from what is
#		to be restored, but because the previous backup was aborted in
#		the middle, some of the files in that directory weren't marked
#		as .missing.
#
#		"""
#		Myrm("testfiles/output")
#		InternalRestore(1, 1, "testfiles/restoretest4", "testfiles/output",
#						10000)
#		assert os.lstat("testfiles/output")
#		self.assertRaises(OSError, os.lstat, "testfiles/output/tmp")
#		self.assertRaises(OSError, os.lstat, "testfiles/output/rdiff-backup")

	def testRestoreNoincs(self):
		"""Test restoring a directory with no increments, just mirror"""
		Myrm("testfiles/output")
		InternalRestore(1, 1, 'testfiles/restoretest5/regular_file', 'testfiles/output',
						10000)
		assert os.lstat("testfiles/output")

if __name__ == "__main__": unittest.main()
