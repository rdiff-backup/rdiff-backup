import os, unittest
from commontest import *
from rdiff_backup import rpath, robust, TempFile, Globals


class TestRobustAction(unittest.TestCase):
	"""Test some robust actions"""
	def testCopyWithAttribs(self):
		"""Test copy with attribs action"""
		rpin = rpath.RPath(Globals.local_connection, "./testfiles/robust/in")
		fp = open("./testfiles/robust/in", "wb")
		fp.write("hello there")
		fp.close()
		os.chmod("./testfiles/robust/in", 0604)
		rpin.setdata()
		assert rpin.isreg() and rpin.getperms() % 01000 == 0604

		rpout = rpath.RPath(Globals.local_connection, "./testfiles/robust/out")
		robust.copy_with_attribs_action(rpin, rpout).execute()
		if not rpout == rpin:
			print rpout, rpin
			assert 0

		rpout.delete()
		rpin.delete()
		

class TempFileTest(unittest.TestCase):
	"""Test creation and management of tempfiles"""
	rp_base = rpath.RPath(Globals.local_connection,
						  "./testfiles/robust/testfile_base")
	def testBasic(self):
		"""Make a temp file, write to it, and then delete it

		Also test tempfile accounting and file name prefixing.

		"""
		assert not TempFile._tempfiles
		tf = TempFile.new(self.rp_base)
		assert TempFile._tempfiles == [tf]
		assert tf.dirsplit()[0] == "testfiles/robust", tf.dirsplit()[0]
		assert not tf.lstat()
		fp = tf.open("w")
		fp.write("hello")
		assert not fp.close()
		fp = tf.open("r")
		assert fp.read() == "hello"
		assert not fp.close()
		tf.delete()
		assert not TempFile._tempfiles

	def testRename(self):
		"""Test renaming of tempfile"""
		tf = TempFile.new(self.rp_base)
		assert TempFile._tempfiles
		tf.touch()
		destination = rpath.RPath(Globals.local_connection,
								  "./testfiles/robust/testfile_dest")
		tf.rename(destination)
		assert not TempFile._tempfiles
		assert destination.lstat()
		destination.delete()


class SaveStateTest(unittest.TestCase):
	"""Test SaveState class"""
	data_dir = rpath.RPath(Globals.local_connection, "testfiles/robust")
	def testSymlinking(self):
		"""Test recording last file with symlink"""
		last_rorp = rpath.RORPath(('usr', 'local', 'bin', 'ls'))
		Globals.rbdir = self.data_dir
		Time.setcurtime()
		SetConnections.BackupInitConnections(Globals.local_connection,
											 Globals.local_connection)
		robust.SaveState.init_filenames()
		robust.SaveState.record_last_file_action(last_rorp).execute()

		sym_rp = rpath.RPath(Globals.local_connection,
							 "testfiles/robust/last-file-incremented.%s.data" %
							 Time.curtimestr)
		assert sym_rp.issym()
		assert sym_rp.readlink() == "increments/usr/local/bin/ls"
		sym_rp.delete()


if __name__ == '__main__': unittest.main()
