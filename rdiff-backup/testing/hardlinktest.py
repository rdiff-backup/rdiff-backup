import os, unittest, time
from commontest import *
from rdiff_backup import Globals, Hardlink, selection, rpath

Log.setverbosity(3)

class HardlinkTest(unittest.TestCase):
	"""Test cases for Hard links"""
	outputrp = rpath.RPath(Globals.local_connection, "testfiles/output")
	hardlink_dir1 = rpath.RPath(Globals.local_connection,
								"testfiles/hardlinks/dir1")
	hardlink_dir1copy = rpath.RPath(Globals.local_connection,
									"testfiles/hardlinks/dir1copy")
	hardlink_dir2 = rpath.RPath(Globals.local_connection,
								"testfiles/hardlinks/dir2")
	hardlink_dir3 = rpath.RPath(Globals.local_connection,
								"testfiles/hardlinks/dir3")

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

	def testBuildingDict(self):
		"""See if the partial inode dictionary is correct"""
		Globals.preserve_hardlinks = 1
		reset_hardlink_dicts()
		for dsrp in selection.Select(self.hardlink_dir3).set_iter():
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
		for dsrp in selection.Select(self.hardlink_dir3).set_iter():
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
		for dsrp in selection.Select(self.hardlink_dir1).set_iter():
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
		for dsrp in selection.Select(self.hardlink_dir2).set_iter():
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

	def testInnerRestore(self):
		"""Restore part of a dir, see if hard links preserved"""
		MakeOutputDir()
		output = rpath.RPath(Globals.local_connection,
							 "testfiles/output")
		
		# Now set up directories out_hardlink1 and out_hardlink2
		hlout1 = rpath.RPath(Globals.local_connection,
							 "testfiles/out_hardlink1")
		if hlout1.lstat(): hlout1.delete()
		hlout1.mkdir()
		hlout1_sub = hlout1.append("subdir")
		hlout1_sub.mkdir()
		hl1_1 = hlout1_sub.append("hardlink1")
		hl1_2 = hlout1_sub.append("hardlink2")
		hl1_3 = hlout1_sub.append("hardlink3")
		hl1_4 = hlout1_sub.append("hardlink4")
		# 1 and 2 are hard linked, as are 3 and 4
		hl1_1.touch()
		hl1_2.hardlink(hl1_1.path)
		hl1_3.touch()
		hl1_4.hardlink(hl1_3.path)
		
		hlout2 = rpath.RPath(Globals.local_connection,
							 "testfiles/out_hardlink2")
		if hlout2.lstat(): hlout2.delete()
		assert not os.system("cp -a testfiles/out_hardlink1 "
							 "testfiles/out_hardlink2")
		hlout2_sub = hlout2.append("subdir")
		hl2_1 = hlout2_sub.append("hardlink1")
		hl2_2 = hlout2_sub.append("hardlink2")
		hl2_3 = hlout2_sub.append("hardlink3")
		hl2_4 = hlout2_sub.append("hardlink4")
		# Now 2 and 3 are hard linked, also 1 and 4
		rpath.copy_with_attribs(hl1_1, hl2_1)
		rpath.copy_with_attribs(hl1_2, hl2_2)
		hl2_3.delete()
		hl2_3.hardlink(hl2_2.path)
		hl2_4.delete()
		hl2_4.hardlink(hl2_1.path)
		rpath.copy_attribs(hlout1_sub, hlout2_sub)

		# Now try backing up twice, making sure hard links are preserved
		InternalBackup(1, 1, hlout1.path, output.path)
		out_subdir = output.append("subdir")
		assert out_subdir.append("hardlink1").getinode() == \
			   out_subdir.append("hardlink2").getinode()
		assert out_subdir.append("hardlink3").getinode() == \
			   out_subdir.append("hardlink4").getinode()
		assert out_subdir.append("hardlink1").getinode() != \
			   out_subdir.append("hardlink3").getinode()

		time.sleep(1)
		InternalBackup(1, 1, hlout2.path, output.path)
		out_subdir.setdata()
		assert out_subdir.append("hardlink1").getinode() == \
			   out_subdir.append("hardlink4").getinode()
		assert out_subdir.append("hardlink2").getinode() == \
			   out_subdir.append("hardlink3").getinode()
		assert out_subdir.append("hardlink1").getinode() != \
			   out_subdir.append("hardlink2").getinode()

		# Now try restoring, still checking hard links.
		out2 = rpath.RPath(Globals.local_connection, "testfiles/out2")
		hlout1 = out2.append("hardlink1")
		hlout2 = out2.append("hardlink2")
		hlout3 = out2.append("hardlink3")
		hlout4 = out2.append("hardlink4")

		if out2.lstat(): out2.delete()
		InternalRestore(1, 1, "testfiles/output/subdir", "testfiles/out2", 1)
		out2.setdata()
		for rp in [hlout1, hlout2, hlout3, hlout4]: rp.setdata()
		assert hlout1.getinode() == hlout2.getinode()
		assert hlout3.getinode() == hlout4.getinode()
		assert hlout1.getinode() != hlout3.getinode()
		
		if out2.lstat(): out2.delete()
		InternalRestore(1, 1, "testfiles/output/subdir", "testfiles/out2",
						int(time.time()))
		out2.setdata()
		for rp in [hlout1, hlout2, hlout3, hlout4]: rp.setdata()
		assert hlout1.getinode() == hlout4.getinode(), \
			   "%s %s" % (hlout1.path, hlout4.path)
		assert hlout2.getinode() == hlout3.getinode()
		assert hlout1.getinode() != hlout2.getinode()


if __name__ == "__main__": unittest.main()
