import unittest, os
from commontest import *
from rdiff_backup import Globals, log

"""Root tests

This is mainly a copy of regressiontest.py, but contains the two tests
that are meant to be run as root.
"""

Globals.set('change_source_perms', None)
Globals.counter = 0
log.Log.setverbosity(4)

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
	def make_root_dir(self):
		"""Make directory createable only by root"""
		rp = rpath.RPath(Globals.local_connection, "testfiles/root_out")
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
		return rp

	def test_non_root(self):
		"""Main non-root -> root test"""
		Myrm("testfiles/output")
		input_rp = self.make_root_dir()
		Globals.change_ownership = 1
		output_rp = rpath.RPath(Globals.local_connection, "testfiles/output")
		restore_rp = rpath.RPath(Globals.local_connection,
								 "testfiles/rest_out")
		empty_rp = rpath.RPath(Globals.local_connection, "testfiles/empty")

		backup_cmd = "rdiff-backup %s %s" % (input_rp.path, output_rp.path)
		Run("su %s -c '%s'" % (self.user, backup_cmd))

		Myrm("testfiles/rest_out")
		restore_cmd = "rdiff-backup -r now %s %s" % (output_rp.path,
													 restore_rp.path,)
		Run(restore_cmd)
		assert CompareRecursive(input_rp, restore_rp)

		backup_cmd = "rdiff-backup %s %s" % (empty_rp.path, output_rp.path)
		Run("su %s -c '%s'" % (self.user, backup_cmd))

		Myrm("testfiles/rest_out")
		Run(restore_cmd)
		assert CompareRecursive(empty_rp, restore_rp)

		Myrm("testfiles/rest_out")
		restore_cmd = "rdiff-backup -r 1 %s %s" % (output_rp.path,
												   restore_rp.path,)
		Run(restore_cmd)
		assert CompareRecursive(input_rp, restore_rp)
		

if __name__ == "__main__": unittest.main()
