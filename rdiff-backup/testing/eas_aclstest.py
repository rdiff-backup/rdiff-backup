import unittest, os, time, cStringIO
from commontest import *
from rdiff_backup.eas_acls import *
from rdiff_backup import Globals, rpath, Time

tempdir = rpath.RPath(Globals.local_connection, "testfiles/output")
restore_dir = rpath.RPath(Globals.local_connection,
						  "testfiles/restore_out")

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
		if restore_dir.lstat(): restore_dir.delete()

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

	def testExtractor(self):
		"""Test seeking inside a record list"""
		record_list = """# file: 0foo
user.multiline=0sVGhpcyBpcyBhIGZhaXJseSBsb25nIGV4dGVuZGVkIGF0dHJpYnV0ZS4KCQkJIEVuY29kaW5nIGl0IHdpbGwgcmVxdWlyZSBzZXZlcmFsIGxpbmVzIG9mCgkJCSBiYXNlNjQusbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGx
user.third=0saGVsbG8=
user.not_empty=0sZm9vYmFy
user.binary=0sAAECjC89Ig==
user.empty
# file: 1foo/bar/baz
user.multiline=0sVGhpcyBpcyBhIGZhaXJseSBsb25nIGV4dGVuZGVkIGF0dHJpYnV0ZS4KCQkJIEVuY29kaW5nIGl0IHdpbGwgcmVxdWlyZSBzZXZlcmFsIGxpbmVzIG9mCgkJCSBiYXNlNjQusbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGx
user.third=0saGVsbG8=
user.binary=0sAAECjC89Ig==
user.empty
# file: 2foo/\\012
user.empty
"""
		extractor = EAExtractor(cStringIO.StringIO(record_list))
		ea_iter = extractor.iterate_starting_with(())
		first = ea_iter.next()
		assert first.index == ('0foo',), first
		second = ea_iter.next()
		assert second.index == ('1foo', 'bar', 'baz'), second
		third = ea_iter.next() # Test quoted filenames
		assert third.index == ('2foo', '\n'), third.index
		try: ea_iter.next()
		except StopIteration: pass
		else: assert 0, "Too many elements in iterator"

		extractor = EAExtractor(cStringIO.StringIO(record_list))
		ea_iter = extractor.iterate_starting_with(('1foo', 'bar'))
		assert ea_iter.next().index == ('1foo', 'bar', 'baz')
		try: ea_iter.next()
		except StopIteration: pass
		else: assert 0, "Too many elements in iterator"

	def make_backup_dirs(self):
		"""Create testfiles/ea_test[12] directories

		Goal is to set range of extended attributes, to give good test
		to extended attribute code.

		"""
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

	def test_final_local(self):
		"""Test backing up and restoring using 'rdiff-backup' script"""
		self.make_backup_dirs()
		self.make_temp()
		rdiff_backup(1, 1, self.ea_testdir1.path, tempdir.path,
					 current_time = 10000)
		assert CompareRecursive(self.ea_testdir1, tempdir, compare_eas = 1)

		rdiff_backup(1, 1, self.ea_testdir2.path, tempdir.path,
					 current_time = 20000)
		assert CompareRecursive(self.ea_testdir2, tempdir, compare_eas = 1)

		rdiff_backup(1, 1, tempdir.path, restore_dir.path,
					 extra_options = '-r 10000')
		assert CompareRecursive(self.ea_testdir1, restore_dir, compare_eas = 1)


class ACLTest(unittest.TestCase):
	"""Test access control lists"""
	sample_acl = AccessControlList((),"""user::rwx
user:root:rwx
group::r-x
group:root:r-x
mask::r-x
other::---""")
	dir_acl = AccessControlList((), """user::rwx
user:root:rwx
group::r-x
group:root:r-x
mask::r-x
other::---""",
								"""user::rwx
user:root:---
group::r-x
mask::r-x
other::---""")
	acl1 = AccessControlList(('1',), """user::r--
user:ben:---
group::---
group:root:---
mask::---
other::---""")
	acl2 = AccessControlList(('2',), """user::rwx
group::r-x
group:ben:rwx
mask::---
other::---""")
	acl3 = AccessControlList(('3',), """user::rwx
user:root:---
group::r-x
mask::---
other::---""")
	empty_acl = AccessControlList((), "user::rwx\ngroup::---\nother::---")
	acl_testdir1 = rpath.RPath(Globals.local_connection, 'testfiles/acl_test1')
	acl_testdir2 = rpath.RPath(Globals.local_connection, 'testfiles/acl_test2')
	def make_temp(self):
		"""Make temp directory testfile/output"""
		if tempdir.lstat(): tempdir.delete()
		tempdir.mkdir()
		if restore_dir.lstat(): restore_dir.delete()

	def testBasic(self):
		"""Test basic writing and reading of ACLs"""
		self.make_temp()
		new_acl = AccessControlList(())
		tempdir.chmod(0700)
		new_acl.read_from_rp(tempdir)
		assert new_acl.is_basic(), new_acl.acl_text
		assert not new_acl == self.sample_acl
		assert new_acl != self.sample_acl
		assert new_acl == self.empty_acl, \
			   (new_acl.acl_text, self.empty_acl.acl_text)

		self.sample_acl.write_to_rp(tempdir)
		new_acl.read_from_rp(tempdir)
		assert new_acl.acl_text == self.sample_acl.acl_text, \
			   (new_acl.acl_text, self.sample_acl.acl_text)
		assert new_acl == self.sample_acl
		
	def testBasicDir(self):
		"""Test reading and writing of ACL w/ defaults to directory"""
		self.make_temp()
		new_acl = AccessControlList(())
		new_acl.read_from_rp(tempdir)
		assert new_acl.is_basic()
		assert new_acl != self.dir_acl

		self.dir_acl.write_to_rp(tempdir)
		new_acl.read_from_rp(tempdir)
		assert not new_acl.is_basic()
		if not new_acl == self.dir_acl:
			assert new_acl.eq_verbose(self.dir_acl)
			assert 0, "Shouldn't be here---eq != eq_verbose?"

	def testRecord(self):
		"""Test writing a record and reading it back"""
		record = ACL2Record(self.sample_acl)
		new_acl = Record2ACL(record)
		assert new_acl == self.sample_acl

		record2 = ACL2Record(self.dir_acl)
		new_acl2 = Record2ACL(record2)
		if not new_acl2 == self.dir_acl:
			assert new_acl2.eq_verbose(self.dir_acl)
			assert 0

	def testExtractor(self):
		"""Test seeking inside a record list"""
		record_list = """# file: 0foo
user::r--
user:ben:---
group::---
group:root:---
mask::---
other::---
# file: 1foo/bar/baz
user::r--
user:ben:---
group::---
group:root:---
mask::---
other::---
# file: 2foo/\\012
user::r--
user:ben:---
group::---
group:root:---
mask::---
other::---
"""
		extractor = ACLExtractor(cStringIO.StringIO(record_list))
		acl_iter = extractor.iterate_starting_with(())
		first = acl_iter.next()
		assert first.index == ('0foo',), first
		second = acl_iter.next()
		assert second.index == ('1foo', 'bar', 'baz'), second
		third = acl_iter.next() # Test quoted filenames
		assert third.index == ('2foo', '\n'), third.index
		try: acl_iter.next()
		except StopIteration: pass
		else: assert 0, "Too many elements in iterator"

		extractor = ACLExtractor(cStringIO.StringIO(record_list))
		acl_iter = extractor.iterate_starting_with(('1foo', 'bar'))
		assert acl_iter.next().index == ('1foo', 'bar', 'baz')
		try: acl_iter.next()
		except StopIteration: pass
		else: assert 0, "Too many elements in iterator"

	def make_backup_dirs(self):
		"""Create testfiles/acl_test[12] directories"""
		if self.acl_testdir1.lstat(): self.acl_testdir1.delete()
		if self.acl_testdir2.lstat(): self.acl_testdir2.delete()
		self.acl_testdir1.mkdir()
		rp1_1 = self.acl_testdir1.append('1')
		rp1_2 = self.acl_testdir1.append('2')
		rp1_3 = self.acl_testdir1.append('3')
		map(rpath.RPath.touch, [rp1_1, rp1_2, rp1_3])
		self.dir_acl.write_to_rp(self.acl_testdir1)
		self.acl1.write_to_rp(rp1_1)
		self.acl2.write_to_rp(rp1_2)
		self.acl3.write_to_rp(rp1_3)

		self.acl_testdir2.mkdir()
		rp2_1, rp2_2, rp2_3 = map(self.acl_testdir2.append, ('1', '2', '3'))
		map(rpath.RPath.touch, (rp2_1, rp2_2, rp2_3))
		self.sample_acl.write_to_rp(self.acl_testdir2)
		self.acl3.write_to_rp(rp2_1)
		self.acl1.write_to_rp(rp2_2)
		self.acl2.write_to_rp(rp2_3)
		
	def testIterate(self):
		"""Test writing several records and then reading them back"""
		self.make_backup_dirs()
		rp1 = self.acl_testdir1.append('1')
		rp2 = self.acl_testdir1.append('2')
		rp3 = self.acl_testdir1.append('3')

		# Now write records corresponding to above rps into file
		Globals.rbdir = tempdir
		Time.setcurtime(10000)
		AccessControlListFile.open_file()
		for rp in [self.acl_testdir1, rp1, rp2, rp3]:
			acl = AccessControlList(rp.index)
			acl.read_from_rp(rp)
			AccessControlListFile.write_object(acl)
		AccessControlListFile.close_file()

		# Read back records and compare
		acl_iter = AccessControlListFile.get_objects_at_time(tempdir, 10000)
		assert acl_iter, "No acl file found"
		dir_acl_reread = acl_iter.next()
		assert dir_acl_reread == self.dir_acl
		acl1_reread = acl_iter.next()
		assert acl1_reread == self.acl1
		acl2_reread = acl_iter.next()
		assert acl2_reread == self.acl2
		acl3_reread = acl_iter.next()
		assert acl3_reread == self.acl3
		try: extra = acl_iter.next()
		except StopIteration: pass
		else: assert 0, "Got unexpected object: " + repr(extra)

	def testSeriesLocal(self):
		"""Test backing up and restoring directories with ACLs locally"""
		self.make_backup_dirs()
		dirlist = ['testfiles/acl_test1', 'testfiles/empty',
				   'testfiles/acl_test2', 'testfiles/acl_test1']
		BackupRestoreSeries(1, 1, dirlist, compare_acls = 1)

	def testSeriesRemote(self):
		"""Test backing up, restoring directories with EA remotely"""
		self.make_backup_dirs()
		dirlist = ['testfiles/acl_test1', 'testfiles/acl_test2',
				   'testfiles/empty', 'testfiles/acl_test1']
		BackupRestoreSeries(None, None, dirlist, compare_acls = 1)

	def test_final_local(self):
		"""Test backing up and restoring using 'rdiff-backup' script"""
		self.make_backup_dirs()
		self.make_temp()
		rdiff_backup(1, 1, self.acl_testdir1.path, tempdir.path,
					 current_time = 10000)
		assert CompareRecursive(self.acl_testdir1, tempdir, compare_acls = 1)

		rdiff_backup(1, 1, self.acl_testdir2.path, tempdir.path,
					 current_time = 20000)
		assert CompareRecursive(self.acl_testdir2, tempdir, compare_acls = 1)

		rdiff_backup(1, 1, tempdir.path, restore_dir.path,
					 extra_options = '-r 10000')
		assert CompareRecursive(self.acl_testdir1, restore_dir,
								compare_acls = 1)

		restore_dir.delete()
		rdiff_backup(1, 1, tempdir.path, restore_dir.path,
					 extra_options = '-r now')
		assert CompareRecursive(self.acl_testdir2, restore_dir,
								compare_acls = 1)


class CombinedTest(unittest.TestCase):
	"""Test backing up and restoring directories with both EAs and ACLs"""
	combo_testdir1 = rpath.RPath(Globals.local_connection,
								 'testfiles/ea_acl_test1')
	combo_testdir2 = rpath.RPath(Globals.local_connection,
								 'testfiles/ea_acl_test2')
	def make_backup_dirs(self):
		"""Create testfiles/ea_acl_test[12] directories"""
		if self.combo_testdir1.lstat(): self.combo_testdir1.delete()
		if self.combo_testdir2.lstat(): self.combo_testdir2.delete()
		self.combo_testdir1.mkdir()
		rp1_1, rp1_2, rp1_3 = map(self.combo_testdir1.append, ('1', '2', '3'))
		map(rpath.RPath.touch, [rp1_1, rp1_2, rp1_3])
		ACLTest.dir_acl.write_to_rp(self.combo_testdir1)
		EATest.sample_ea.write_to_rp(self.combo_testdir1)
		ACLTest.acl1.write_to_rp(rp1_1)
		EATest.ea2.write_to_rp(rp1_2)
		ACLTest.acl3.write_to_rp(rp1_3)
		EATest.ea3.write_to_rp(rp1_3)

		self.combo_testdir2.mkdir()
		rp2_1, rp2_2, rp2_3 = map(self.combo_testdir2.append, ('1', '2', '3'))
		map(rpath.RPath.touch, [rp2_1, rp2_2, rp2_3])
		ACLTest.sample_acl.write_to_rp(self.combo_testdir2)
		EATest.ea1.write_to_rp(rp2_1)
		EATest.ea3.write_to_rp(rp2_2)
		ACLTest.acl2.write_to_rp(rp2_2)

	def testSeriesLocal(self):
		"""Test backing up and restoring EAs/ACLs locally"""
		self.make_backup_dirs()
		dirlist = ['testfiles/ea_acl_test1', 'testfiles/ea_acl_test2',
				   'testfiles/empty', 'testfiles/ea_acl_test1']
		BackupRestoreSeries(1, 1, dirlist,
							compare_eas = 1, compare_acls = 1)

	def testSeriesRemote(self):
		"""Test backing up and restoring EAs/ACLs locally"""
		self.make_backup_dirs()
		dirlist = ['testfiles/ea_acl_test1', 'testfiles/empty',
				   'testfiles/ea_acl_test2', 'testfiles/ea_acl_test1']
		BackupRestoreSeries(None, None, dirlist,
							compare_eas = 1, compare_acls = 1)


if __name__ == "__main__": unittest.main()
