import unittest, os
from commontest import *
from rdiff_backup import Globals, log

"""Root tests - contain tests which need to be run as root.

Some of the quoting here may not work with csh (works on bash).  Also,
if you aren't me, check out the 'user' global variable.

"""

Globals.set('change_source_perms', None)
Globals.counter = 0
verbosity = 3
log.Log.setverbosity(verbosity)
user = 'ben' # Non-root user to su to
assert os.getuid() == 0, "Run this test as root!"

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

class HalfRoot(unittest.TestCase):
	"""Backing up files where origin is root and destination is non-root"""
	def make_dirs(self):
		"""Make source directories, return rpaths

		These make a directory with a changing file that is not
		self-readable.  (Caused problems earlier.)

		"""
		rp1 = rpath.RPath(Globals.local_connection, "testfiles/root_half1")
		if rp1.lstat(): Myrm(rp1.path)
		rp1.mkdir()
		rp1_1 = rp1.append('foo')
		rp1_1.write_string('hello')
		rp1_1.chmod(0)
		rp1_2 = rp1.append('to be deleted')
		rp1_2.write_string('aosetuhaosetnuhontu')
		rp1_2.chmod(0)

		rp2 = rpath.RPath(Globals.local_connection, "testfiles/root_half2")
		if rp2.lstat(): Myrm(rp2.path)
		rp2.mkdir()
		rp2_1 = rp2.append('foo')
		rp2_1.write_string('goodbye')
		rp2_1.chmod(0)
		return rp1, rp2

	def test_backup(self):
		"""Right now just test backing up"""
		in_rp1, in_rp2 = self.make_dirs()
		outrp = rpath.RPath(Globals.local_connection, "testfiles/output")
		if outrp.lstat(): outrp.delete()
		remote_schema = 'su -c "rdiff-backup --server" %s' % (user,)
		cmd_schema = ("rdiff-backup -v" + str(verbosity) +
					  " --current-time %s --remote-schema '%%s' %s '%s'::%s")

		cmd1 = cmd_schema % (10000, in_rp1.path, remote_schema, outrp.path)
		print "Executing: ", cmd1
		assert not os.system(cmd1)
		in_rp1.setdata()
		outrp.setdata()
		assert CompareRecursive(in_rp1, outrp)

		cmd2 = cmd_schema % (20000, in_rp2.path, remote_schema, outrp.path)
		print "Executing: ", cmd2
		assert not os.system(cmd2)
		in_rp2.setdata()
		outrp.setdata()
		assert CompareRecursive(in_rp2, outrp)

class NonRoot(unittest.TestCase):
	"""Test backing up as non-root user

	Test backing up a directory with files of different userids and
	with device files in it, as a non-root user.  When restoring as
	root, everything should be restored normally.

	"""
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
		global user
		backup_cmd = ("rdiff-backup --no-compare-inode "
					  "--current-time %s %s %s" %
					  (time, input_rp.path, output_rp.path))
		Run("su %s -c '%s'" % (user, backup_cmd))

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
