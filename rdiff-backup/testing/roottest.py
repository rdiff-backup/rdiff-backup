import unittest, os
from commontest import *
from rdiff_backup import Globals, log

"""Root tests

This is mainly a copy of regressiontest.py, but contains the two tests
that are meant to be run as root.
"""

Globals.set('change_source_perms', None)
Globals.counter = 0
log.Log.setverbosity(6)

def Run(cmd):
	print "Running: ", cmd
	assert not os.system(cmd)

class RootTest(unittest.TestCase):
	dirlist1 = ["testfiles/root", "testfiles/various_file_types", "testfiles/increment4"]
	dirlist2 = ["testfiles/increment4", "testfiles/root",
				"testfiles/increment1"]
	def testLocal1(self): BackupRestoreSeries(1, 1, self.dirlist1)
	def testLocal2(self): BackupRestoreSeries(1, 1, self.dirlist2)
	def testRemote(self): BackupRestoreSeries(None, None, self.dirlist1)

class NonRoot(unittest.TestCase):
	"""Test backing up as non-root user

	Test backing up a directory with files of different userids and
	with device files in it, as a non-root user.  When restoring as
	root, everything should be restored normally.

	"""
	user = 'ben'
	def make_root_dirs(self):
		"""Make directory createable only by root"""
		rp = rpath.RPath(Globals.local_connection, "testfiles/root_out1")
		if rp.lstat(): Myrm(rp.path)
		rp.mkdir()
		rp1 = rp.append("1")
		rp1.touch()
		rp2 = rp.append("2")
		rp2.touch()
		rp2.chown(1, 1)
		rp3 = rp.append("3")
		rp3.touch()
		rp3.chown(2, 2)
		rp4 = rp.append("dev")
		rp4.makedev('c', 4, 28)

		sp = rpath.RPath(Globals.local_connection, "testfiles/root_out2")
		if sp.lstat(): Myrm(sp.path)
		Run("cp -a %s %s" % (rp.path, sp.path))
		rp2 = sp.append("2")
		rp2.chown(2, 2)
		rp3 = sp.append("3")
		rp3.chown(1, 1)
		assert not CompareRecursive(rp, sp, compare_ownership = 1)

		return rp, sp

	def backup(self, input_rp, output_rp, time):
		backup_cmd = ("rdiff-backup --no-compare-inode "
					  "--current-time %s %s %s" %
					  (time, input_rp.path, output_rp.path))
		Run("su %s -c '%s'" % (self.user, backup_cmd))

	def restore(self, dest_rp, restore_rp, time = None):
		assert restore_rp.path == "testfiles/rest_out"
		Myrm(restore_rp.path)
		if time is None: time = "now"
		restore_cmd = "rdiff-backup -r %s %s %s" % (time, dest_rp.path,
													restore_rp.path,)
		Run(restore_cmd)		

	def test_non_root(self):
		"""Main non-root -> root test"""
		Myrm("testfiles/output")
		input_rp1, input_rp2 = self.make_root_dirs()
		Globals.change_ownership = 1
		output_rp = rpath.RPath(Globals.local_connection, "testfiles/output")
		restore_rp = rpath.RPath(Globals.local_connection,
								 "testfiles/rest_out")
		empty_rp = rpath.RPath(Globals.local_connection, "testfiles/empty")

		self.backup(input_rp1, output_rp, 1000000)
		self.restore(output_rp, restore_rp)
		assert CompareRecursive(input_rp1, restore_rp, compare_ownership = 1)

		self.backup(input_rp2, output_rp, 2000000)
		self.restore(output_rp, restore_rp)
		assert CompareRecursive(input_rp2, restore_rp, compare_ownership = 1)

		self.backup(empty_rp, output_rp, 3000000)
		self.restore(output_rp, restore_rp)
		assert CompareRecursive(empty_rp, restore_rp, compare_ownership = 1)

		self.restore(output_rp, restore_rp, 1000000)
		assert CompareRecursive(input_rp1, restore_rp, compare_ownership = 1)

		self.restore(output_rp, restore_rp, 2000000)
		assert CompareRecursive(input_rp2, restore_rp, compare_ownership = 1)


if __name__ == "__main__": unittest.main()
