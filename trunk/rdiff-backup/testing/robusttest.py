
import os, unittest
from commontest import *
from rdiff_backup import rpath, robust, TempFile, Globals
		

class TempFileTest(unittest.TestCase):
	"""Test creation and management of tempfiles in TempFile module"""
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

class RobustTest(unittest.TestCase):
	"""Test robust module"""
	def test_check_common_error(self):
		"""Test capturing errors"""
		def cause_catchable_error(a):
			os.lstat("aoenuthaoeu/aosutnhcg.4fpr,38p")
		def cause_uncatchable_error():
			ansoethusaotneuhsaotneuhsaontehuaou
		result = robust.check_common_error(None, cause_catchable_error, [1])
		assert result is None, result
		try: robust.check_common_error(None, cause_uncatchable_error)
		except NameError: pass
		else: assert 0, "Key error not raised"
		

if __name__ == '__main__': unittest.main()
