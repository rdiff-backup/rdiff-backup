import unittest, os, time
from commontest import *
from rdiff_backup.eas_acls import *
from rdiff_backup import Globals, rpath, Time

tempdir = rpath.RPath(Globals.local_connection, "testfiles/output")

class EATest(unittest.TestCase):
	"""Test extended attributes"""
	sample_ea = ExtendedAttributes(
		(), {'user.empty':'', 'user.not_empty':'foobar', 'user.third':'hello',
			 'user.binary':chr(0)+chr(1)+chr(2)+chr(140)+'/="',
			 'user.multiline':"""This is a fairly long extended attribute.
			 Encoding it will require several lines of
			 base64.""" + chr(177)*300})
	empty_ea = ExtendedAttributes(())
	ea1 = ExtendedAttributes(('1',), sample_ea.attr_dict.copy())
	ea1.delete('user.not_empty')
	ea2 = ExtendedAttributes(('2',), sample_ea.attr_dict.copy())
	ea2.set('user.third', 'Another random attribute')
	ea3 = ExtendedAttributes(('3',))
	ea4 = ExtendedAttributes(('4',), {'user.deleted': 'File to be deleted'})
	ea_testdir1 = rpath.RPath(Globals.local_connection, "testfiles/ea_test1")
	ea_testdir2 = rpath.RPath(Globals.local_connection, "testfiles/ea_test2")

	def make_temp(self):
		"""Make temp directory testfiles/output"""
		if tempdir.lstat(): tempdir.delete()
		tempdir.mkdir()

	def testBasic(self):
		"""Test basic writing and reading of extended attributes"""
		self.make_temp()
		new_ea = ExtendedAttributes(())
		new_ea.read_from_rp(tempdir)
		assert not new_ea.attr_dict
		assert not new_ea == self.sample_ea
		assert new_ea != self.sample_ea
		assert new_ea == self.empty_ea

		self.sample_ea.write_to_rp(tempdir)
		new_ea.read_from_rp(tempdir)
		assert new_ea.attr_dict == self.sample_ea.attr_dict, \
			   (new_ea.attr_dict, self.sample_ea.attr_dict)
		assert new_ea == self.sample_ea

	def testRecord(self):
		"""Test writing a record and reading it back"""
		record = EA2Record(self.sample_ea)
		new_ea = Record2EA(record)
		if not new_ea == self.sample_ea:
			new_list = new_ea.attr_dict.keys()
			sample_list = self.sample_ea.attr_dict.keys()
			new_list.sort()
			sample_list.sort()
			assert new_list == sample_list, (new_list, sample_list)
			for name in new_list:
				assert self.sample_ea.get(name) == new_ea.get(name), \
					   (self.sample_ea.get(name), new_ea.get(name))
			assert self.sample_ea.index == new_ea.index, \
				   (self.sample_ea.index, new_ea.index)
			assert 0, "We shouldn't have gotten this far"

	def make_backup_dirs(self):
		"""Create testfiles/ea_test[12] directories"""
		if self.ea_testdir1.lstat(): self.ea_testdir1.delete()
		if self.ea_testdir2.lstat(): self.ea_testdir2.delete()
		self.ea_testdir1.mkdir()
		rp1_1 = self.ea_testdir1.append('1')
		rp1_2 = self.ea_testdir1.append('2')
		rp1_3 = self.ea_testdir1.append('3')
		rp1_4 = self.ea_testdir1.append('4')
		map(rpath.RPath.touch, [rp1_1, rp1_2, rp1_3, rp1_4])
		self.sample_ea.write_to_rp(self.ea_testdir1)
		self.ea1.write_to_rp(rp1_1)
		self.ea2.write_to_rp(rp1_2)
		self.ea4.write_to_rp(rp1_4)

		self.ea_testdir2.mkdir()
		rp2_1 = self.ea_testdir2.append('1')
		rp2_2 = self.ea_testdir2.append('2')
		rp2_3 = self.ea_testdir2.append('3')
		map(rpath.RPath.touch, [rp2_1, rp2_2, rp2_3])
		self.ea3.write_to_rp(self.ea_testdir2)
		self.sample_ea.write_to_rp(rp2_1)
		self.ea1.write_to_rp(rp2_2)
		self.ea2.write_to_rp(rp2_3)

	def testIterate(self):
		"""Test writing several records and then reading them back"""
		self.make_backup_dirs()
		rp1 = self.ea_testdir1.append('1')
		rp2 = self.ea_testdir1.append('2')
		rp3 = self.ea_testdir1.append('3')

		# Now write records corresponding to above rps into file
		Globals.rbdir = tempdir
		Time.setcurtime(10000)
		ExtendedAttributesFile.open_file()
		for rp in [self.ea_testdir1, rp1, rp2, rp3]:
			ea = ExtendedAttributes(rp.index)
			ea.read_from_rp(rp)
			ExtendedAttributesFile.write_object(ea)
		ExtendedAttributesFile.close_file()

		# Read back records and compare
		ea_iter = ExtendedAttributesFile.get_objects_at_time(tempdir, 10000)
		assert ea_iter, "No extended_attributes.<time> file found"
		sample_ea_reread = ea_iter.next()
		assert sample_ea_reread == self.sample_ea
		ea1_reread = ea_iter.next()
		assert ea1_reread == self.ea1
		ea2_reread = ea_iter.next()
		assert ea2_reread == self.ea2
		ea3_reread = ea_iter.next()
		assert ea3_reread == self.ea3
		try: ea_iter.next()
		except StopIteration: pass
		else: assert 0, "Expected end to iterator"

	def testSeriesLocal(self):
		"""Test backing up and restoring directories with EAs locally"""
		self.make_backup_dirs()
		dirlist = ['testfiles/ea_test1', 'testfiles/empty',
				   'testfiles/ea_test2', 'testfiles/ea_test1']
		BackupRestoreSeries(1, 1, dirlist, compare_eas = 1)

	def testSeriesRemote(self):
		"""Test backing up, restoring directories with EA remotely"""
		self.make_backup_dirs()
		dirlist = ['testfiles/ea_test1', 'testfiles/ea_test2',
				   'testfiles/empty', 'testfiles/ea_test1']
		BackupRestoreSeries(None, None, dirlist, compare_eas = 1)

if __name__ == "__main__": unittest.main()
