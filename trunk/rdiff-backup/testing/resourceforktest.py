import unittest
from commontest import *
from rdiff_backup import rpath
from rdiff_backup import metadata

"""***NOTE***

None of these tests should work unless your system supports resource
forks.  So basically these tests should only be run on Mac OS X.

"""

Globals.read_resource_forks = Globals.write_resource_forks = 1

class ResourceForkTest(unittest.TestCase):
	"""Test dealing with Mac OS X style resource forks"""
	tempdir = rpath.RPath(Globals.local_connection,
						  'testfiles/resource_fork_test')
	def make_temp(self):
		"""Make temp directory testfiles/resource_fork_test"""
		if self.tempdir.lstat(): self.tempdir.delete()
		self.tempdir.mkdir()

	def testBasic(self):
		"""Test basic reading and writing of resource forks"""
		self.make_temp()
		rp = self.tempdir.append('test')
		rp.touch()
		assert rp.get_resource_fork() == '', rp.get_resource_fork()

		s = 'new resource fork data'
		rp.write_resource_fork(s)
		assert rp.get_resource_fork() == s, rp.get_resource_fork()

		rp2 = self.tempdir.append('test')
		assert rp2.isreg()
		assert rp2.get_resource_fork() == s, rp2.get_resource_fork()

	def testRecord(self):
		"""Test reading, writing, and comparing of records with rforks"""
		self.make_temp()
		rp = self.tempdir.append('test')
		rp.touch()
		rp.set_resource_fork('hello')

		record = metadata.RORP2Record(rp)
		#print record
		rorp_out = metadata.Record2RORP(record)
		assert rorp_out == rp, (rorp_out, rp)
		assert rorp_out.get_resource_fork() == 'hello'


if __name__ == "__main__": unittest.main()
