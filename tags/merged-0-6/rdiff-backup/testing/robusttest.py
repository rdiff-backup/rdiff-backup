import os, unittest

execfile("commontest.py")
rbexec("setconnections.py")

class TestRobustAction(unittest.TestCase):
	"""Test some robust actions"""
	def testCopyWithAttribs(self):
		"""Test copy with attribs action"""
		rpin = RPath(Globals.local_connection, "./testfiles/robust/in")
		fp = open("./testfiles/robust/in", "wb")
		fp.write("hello there")
		fp.close()
		os.chmod("./testfiles/robust/in", 0604)
		rpin.setdata()
		assert rpin.isreg() and rpin.getperms() % 01000 == 0604

		rpout = RPath(Globals.local_connection, "./testfiles/robust/out")
		Robust.copy_with_attribs_action(rpin, rpout).execute()
		if not rpout == rpin:
			print rpout, rpin
			assert 0

		rpout.delete()
		rpin.delete()
		

class TempFileTest(unittest.TestCase):
	"""Test creation and management of tempfiles"""
	rp_base = RPath(Globals.local_connection,
					"./testfiles/robust/testfile_base")
	def testBasic(self):
		"""Make a temp file, write to it, and then delete it

		Also test tempfile accounting and file name prefixing.

		"""
		assert not TempFileManager._tempfiles
		tf = TempFileManager.new(self.rp_base)
		assert TempFileManager._tempfiles == [tf]
		assert tf.dirsplit()[0] == "testfiles/robust", tf.dirsplit()[0]
		assert not tf.lstat()
		fp = tf.open("w")
		fp.write("hello")
		assert not fp.close()
		fp = tf.open("r")
		assert fp.read() == "hello"
		assert not fp.close()
		tf.delete()
		assert not TempFileManager._tempfiles

	def testRename(self):
		"""Test renaming of tempfile"""
		tf = TempFileManager.new(self.rp_base)
		assert TempFileManager._tempfiles
		tf.touch()
		destination = RPath(Globals.local_connection,
							"./testfiles/robust/testfile_dest")
		tf.rename(destination)
		assert not TempFileManager._tempfiles
		assert destination.lstat()
		destination.delete()


class SaveStateTest(unittest.TestCase):
	"""Test SaveState class"""
	data_dir = RPath(Globals.local_connection, "testfiles/robust")
	def testSymlinking(self):
		"""Test recording last file with symlink"""
		last_rorp = RORPath(('usr', 'local', 'bin', 'ls'))
		Globals.rbdir = self.data_dir
		Time.setcurtime()
		SetConnections.BackupInitConnections(Globals.local_connection,
											 Globals.local_connection)
		SaveState.init_filenames(None)
		SaveState.record_last_file_action(last_rorp).execute()

		sym_rp = RPath(Globals.local_connection,
					   "testfiles/robust/last-file-mirrored.%s.snapshot" %
					   Time.curtimestr)
		assert sym_rp.issym()
		assert sym_rp.readlink() == "increments/usr/local/bin/ls"
		sym_rp.delete()


if __name__ == '__main__': unittest.main()
