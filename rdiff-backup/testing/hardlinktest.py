import os, unittest
from commontest import *
from rdiff_backup.rpath import *
from rdiff_backup import Globals, Hardlink

Log.setverbosity(7)

class HardlinkTest(unittest.TestCase):
	"""Test cases for Hard links"""
	outputrp = RPath(Globals.local_connection, "testfiles/output")
	hardlink_dir1 = RPath(Globals.local_connection, "testfiles/hardlinks/dir1")
	hardlink_dir1copy = \
		RPath(Globals.local_connection, "testfiles/hardlinks/dir1copy")
	hardlink_dir2 = RPath(Globals.local_connection, "testfiles/hardlinks/dir2")
	hardlink_dir3 = RPath(Globals.local_connection, "testfiles/hardlinks/dir3")

	def reset_output(self):
		"""Erase and recreate testfiles/output directory"""
		os.system(MiscDir+'/myrm testfiles/output')
		self.outputrp.mkdir()

	def testEquality(self):
		"""Test rorp_eq function in conjunction with CompareRecursive"""
		assert CompareRecursive(self.hardlink_dir1, self.hardlink_dir1copy)
		assert CompareRecursive(self.hardlink_dir1, self.hardlink_dir2,
								compare_hardlinks = None)
		assert not CompareRecursive(self.hardlink_dir1, self.hardlink_dir2,
								compare_hardlinks = 1)

	def testCheckpointing(self):
		"""Test saving and recovering of various dictionaries"""
		d1 = {1:1}
		d2 = {2:2}
		d3 = {3:3}
		d4 = {}

		Hardlink._src_inode_indicies = d1
		Hardlink._src_index_indicies = d2
		Hardlink._dest_inode_indicies = d3
		Hardlink._dest_index_indicies = d4

		self.reset_output()
		Time.setcurtime(12345)
		Globals.isbackup_writer = 1
		Hardlink.final_checkpoint(self.outputrp)

		reset_hardlink_dicts()
		assert Hardlink.retrieve_checkpoint(self.outputrp, 12345)
		assert Hardlink._src_inode_indicies == d1, \
			   Hardlink._src_inode_indicies
		assert Hardlink._src_index_indicies == d2, \
			   Hardlink._src_index_indicies
		assert Hardlink._dest_inode_indicies == d3, \
			   Hardlink._dest_inode_indicies
		assert Hardlink._dest_index_indicies == d4, \
			   Hardlink._dest_index_indicies

	def testFinalwrite(self):
		"""Test writing of the final database"""
		Globals.isbackup_writer = 1
		Time.setcurtime(123456)
		Globals.rbdir = self.outputrp
		finald = Hardlink._src_index_indicies = {'hello':'world'}
		
		self.reset_output()
		Hardlink.final_writedata()

		Hardlink._src_index_indicies = None
		assert Hardlink.retrieve_final(123456)
		assert Hardlink._src_index_indicies == finald

	def testBuildingDict(self):
		"""See if the partial inode dictionary is correct"""
		Globals.preserve_hardlinks = 1
		reset_hardlink_dicts()
		for dsrp in Select(DSRPath(1, self.hardlink_dir3)).set_iter():
			Hardlink.add_rorp(dsrp, 1)
		
		assert len(Hardlink._src_inode_indicies.keys()) == 3, \
			   Hardlink._src_inode_indicies
		assert len(Hardlink._src_index_indicies.keys()) == 3, \
			   Hardlink._src_index_indicies
		vals1 = Hardlink._src_inode_indicies.values()
		vals2 = Hardlink._src_index_indicies.values()
		vals1.sort()
		vals2.sort()
		assert vals1 == vals2

	def testBuildingDict2(self):
		"""Same as testBuildingDict but test destination building"""
		Globals.preserve_hardlinks = 1
		reset_hardlink_dicts()
		for dsrp in Select(DSRPath(None, self.hardlink_dir3)).set_iter():
			Hardlink.add_rorp(dsrp, None)
		
		assert len(Hardlink._dest_inode_indicies.keys()) == 3, \
			   Hardlink._dest_inode_indicies
		assert len(Hardlink._dest_index_indicies.keys()) == 3, \
			   Hardlink._dest_index_indicies
		vals1 = Hardlink._dest_inode_indicies.values()
		vals2 = Hardlink._dest_index_indicies.values()
		vals1.sort()
		vals2.sort()
		assert vals1 == vals2

	def testCompletedDict(self):
		"""See if the hardlink dictionaries are built correctly"""
		reset_hardlink_dicts()
		for dsrp in Select(DSRPath(1, self.hardlink_dir1)).set_iter():
			Hardlink.add_rorp(dsrp, 1)
		assert Hardlink._src_inode_indicies == {}, \
			   Hardlink._src_inode_indicies

		hll1 = [('file1',), ('file2',), ('file3',)]
		hll2 = [('file4',), ('file5',), ('file6',)]
		dict = {}
		for index in hll1: dict[index] = hll1
		for index in hll2: dict[index] = hll2
		assert Hardlink._src_index_indicies == dict

		reset_hardlink_dicts()
		for dsrp in Select(DSRPath(1, self.hardlink_dir2)).set_iter():
			Hardlink.add_rorp(dsrp, 1)
		assert Hardlink._src_inode_indicies == {}, \
			   Hardlink._src_inode_indicies

		hll1 = [('file1',), ('file3',), ('file4',)]
		hll2 = [('file2',), ('file5',), ('file6',)]
		dict = {}
		for index in hll1: dict[index] = hll1
		for index in hll2: dict[index] = hll2
		assert Hardlink._src_index_indicies == dict

	def testSeries(self):
		"""Test hardlink system by backing up and restoring a few dirs"""
		dirlist = ['testfiles/hardlinks/dir1',
				   'testfiles/hardlinks/dir2',
				   'testfiles/hardlinks/dir3',
				   'testfiles/various_file_types']
		BackupRestoreSeries(None, None, dirlist, compare_hardlinks=1)
		BackupRestoreSeries(1, 1, dirlist, compare_hardlinks=1)



if __name__ == "__main__": unittest.main()
