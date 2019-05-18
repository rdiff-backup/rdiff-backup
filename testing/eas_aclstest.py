import unittest, os, time, io, posix1e, pwd, grp
from commontest import *
from rdiff_backup.eas_acls import *
from rdiff_backup import Globals, rpath, Time, user_group, log

user_group.init_user_mapping()
user_group.init_group_mapping()
tempdir = rpath.RPath(Globals.local_connection, abs_output_dir)
restore_dir = rpath.RPath(Globals.local_connection, abs_restore_dir)
log.Log.setverbosity(3)

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
	ea_test1_dir = os.path.join(abs_test_dir, 'ea_test1')
	ea_test1_rpath = rpath.RPath(Globals.local_connection, ea_test1_dir)
	ea_test2_dir = os.path.join(abs_test_dir, 'ea_test2')
	ea_test2_rpath = rpath.RPath(Globals.local_connection, ea_test2_dir)
	ea_empty_dir = os.path.join(abs_test_dir, 'ea_empty')
	ea_empty_rpath = rpath.RPath(Globals.local_connection, ea_empty_dir)

	def make_temp_out_dirs(self):
		"""Make temp output and restore directories empty"""
		if tempdir.lstat(): tempdir.delete()
		tempdir.mkdir()
		if restore_dir.lstat(): restore_dir.delete()

	def testBasic(self):
		"""Test basic writing and reading of extended attributes"""
		self.make_temp_out_dirs()
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
			new_list = list(new_ea.attr_dict.keys())
			sample_list = list(self.sample_ea.attr_dict.keys())
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
		extractor = EAExtractor(io.StringIO(record_list))
		ea_iter = extractor.iterate_starting_with(())
		first = next(ea_iter)
		assert first.index == ('0foo',), first
		second = next(ea_iter)
		assert second.index == ('1foo', 'bar', 'baz'), second
		third = next(ea_iter) # Test quoted filenames
		assert third.index == ('2foo', '\n'), third.index
		try: next(ea_iter)
		except StopIteration: pass
		else: assert 0, "Too many elements in iterator"

		extractor = EAExtractor(io.StringIO(record_list))
		ea_iter = extractor.iterate_starting_with(('1foo', 'bar'))
		assert next(ea_iter).index == ('1foo', 'bar', 'baz')
		try: next(ea_iter)
		except StopIteration: pass
		else: assert 0, "Too many elements in iterator"

	def make_backup_dirs(self):
		"""Create testfiles/ea_test[12] directories

		Goal is to set range of extended attributes, to give good test
		to extended attribute code.

		"""
		if self.ea_test1_rpath.lstat(): self.ea_test1_rpath.delete()
		if self.ea_test2_rpath.lstat(): self.ea_test2_rpath.delete()
		self.ea_test1_rpath.mkdir()
		rp1_1 = self.ea_test1_rpath.append('1')
		rp1_2 = self.ea_test1_rpath.append('2')
		rp1_3 = self.ea_test1_rpath.append('3')
		rp1_4 = self.ea_test1_rpath.append('4')
		list(map(rpath.RPath.touch, [rp1_1, rp1_2, rp1_3, rp1_4]))
		self.sample_ea.write_to_rp(self.ea_test1_rpath)
		self.ea1.write_to_rp(rp1_1)
		self.ea2.write_to_rp(rp1_2)
		self.ea4.write_to_rp(rp1_4)

		self.ea_test2_rpath.mkdir()
		rp2_1 = self.ea_test2_rpath.append('1')
		rp2_2 = self.ea_test2_rpath.append('2')
		rp2_3 = self.ea_test2_rpath.append('3')
		list(map(rpath.RPath.touch, [rp2_1, rp2_2, rp2_3]))
		self.ea3.write_to_rp(self.ea_test2_rpath)
		self.sample_ea.write_to_rp(rp2_1)
		self.ea1.write_to_rp(rp2_2)
		self.ea2.write_to_rp(rp2_3)

		# just create an empty dir for tests
		if self.ea_empty_rpath.lstat(): self.ea_empty_rpath.delete()
		self.ea_empty_rpath.mkdir()

	def testIterate(self):
		"""Test writing several records and then reading them back"""
		self.make_backup_dirs()
		rp1 = self.ea_test1_rpath.append('1')
		rp2 = self.ea_test1_rpath.append('2')
		rp3 = self.ea_test1_rpath.append('3')

		# Now write records corresponding to above rps into file
		Globals.rbdir = tempdir
		man = metadata.PatchDiffMan()
		writer = man.get_ea_writer('snapshot', 10000)
		for rp in [self.ea_test1_rpath, rp1, rp2, rp3]:
			ea = ExtendedAttributes(rp.index)
			ea.read_from_rp(rp)
			writer.write_object(ea)
		writer.close()

		# Read back records and compare
		ea_iter = man.get_eas_at_time(10000, None)
		assert ea_iter, "No extended_attributes.<time> file found"
		sample_ea_reread = next(ea_iter)
		assert sample_ea_reread == self.sample_ea
		ea1_reread = next(ea_iter)
		assert ea1_reread == self.ea1
		ea2_reread = next(ea_iter)
		assert ea2_reread == self.ea2
		ea3_reread = next(ea_iter)
		assert ea3_reread == self.ea3
		try: next(ea_iter)
		except StopIteration: pass
		else: assert 0, "Expected end to iterator"

	def testSeriesLocal(self):
		"""Test backing up and restoring directories with EAs locally"""
		self.make_backup_dirs()
		dirlist = [self.ea_test1_dir, self.ea_empty_dir,
				   self.ea_test2_dir, self.ea_test1_dir]
		BackupRestoreSeries(1, 1, dirlist, compare_eas = 1)

	def testSeriesRemote(self):
		"""Test backing up, restoring directories with EA remotely"""
		self.make_backup_dirs()
		dirlist = [self.ea_test1_dir, self.ea_test2_dir,
				   self.ea_empty_dir, self.ea_test1_dir]
		BackupRestoreSeries(None, None, dirlist, compare_eas = 1)

	def test_final_local(self):
		"""Test backing up and restoring using 'rdiff-backup' script"""
		self.make_backup_dirs()
		self.make_temp_out_dirs()
		rdiff_backup(1, 1, self.ea_test1_rpath.path, tempdir.path,
					 current_time = 10000)
		assert CompareRecursive(self.ea_test1_rpath, tempdir, compare_eas = 1)

		rdiff_backup(1, 1, self.ea_test2_rpath.path, tempdir.path,
					 current_time = 20000)
		assert CompareRecursive(self.ea_test2_rpath, tempdir, compare_eas = 1)

		rdiff_backup(1, 1, tempdir.path, restore_dir.path,
					 extra_options = '-r 10000')
		assert CompareRecursive(self.ea_test1_rpath, restore_dir, compare_eas = 1)


class ACLTest(unittest.TestCase):
	"""Test access control lists"""
	sample_acl = AccessControlLists((),"""user::rwx
user:root:rwx
group::r-x
group:root:r-x
mask::r-x
other::---""")
	dir_acl = AccessControlLists((), """user::rwx
user:root:rwx
group::r-x
group:root:r-x
mask::r-x
other::---
default:user::rwx
default:user:root:---
default:group::r-x
default:mask::r-x
default:other::---""")
	acl1 = AccessControlLists(('1',), """user::r--
user:ben:---
group::---
group:root:---
mask::---
other::---""")
	acl2 = AccessControlLists(('2',), """user::rwx
group::r-x
group:ben:rwx
mask::---
other::---""")
	acl3 = AccessControlLists(('3',), """user::rwx
user:root:---
group::r-x
mask::---
other::---""")
	empty_acl = AccessControlLists((), "user::rwx\ngroup::---\nother::---")
	acl_test1_dir = os.path.join(abs_test_dir, 'acl_test1')
	acl_test1_rpath = rpath.RPath(Globals.local_connection, acl_test1_dir)
	acl_test2_dir = os.path.join(abs_test_dir, 'acl_test2')
	acl_test2_rpath = rpath.RPath(Globals.local_connection, acl_test2_dir)
	acl_empty_dir = os.path.join(abs_test_dir, 'acl_empty')
	acl_empty_rpath = rpath.RPath(Globals.local_connection, acl_empty_dir)
	def make_temp_out_dirs(self):
		"""Make temp output and restore directories empty"""
		if tempdir.lstat(): tempdir.delete()
		tempdir.mkdir()
		if restore_dir.lstat(): restore_dir.delete()

	def testBasic(self):
		"""Test basic writing and reading of ACLs"""
		self.make_temp_out_dirs()
		new_acl = AccessControlLists(())
		tempdir.chmod(0o700)
		new_acl.read_from_rp(tempdir)
		assert new_acl.is_basic(), str(new_acl)
		assert not new_acl == self.sample_acl
		assert new_acl != self.sample_acl
		assert new_acl == self.empty_acl, \
			   (str(new_acl), str(self.empty_acl))

		self.sample_acl.write_to_rp(tempdir)
		new_acl.read_from_rp(tempdir)
		assert str(new_acl) == str(self.sample_acl), \
			   (str(new_acl), str(self.sample_acl))
		assert new_acl == self.sample_acl

	def testBasicDir(self):
		"""Test reading and writing of ACL w/ defaults to directory"""
		self.make_temp_out_dirs()
		new_acl = AccessControlLists(())
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
		if new_acl != self.sample_acl:
			print("New_acl", new_acl.entry_list)
			print("sample_acl", self.sample_acl.entry_list)
			print("New_acl text", str(new_acl))
			print("sample acl text", str(self.sample_acl))
			assert 0

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
		extractor = ACLExtractor(io.StringIO(record_list))
		acl_iter = extractor.iterate_starting_with(())
		first = next(acl_iter)
		assert first.index == ('0foo',), first
		second = next(acl_iter)
		assert second.index == ('1foo', 'bar', 'baz'), second
		third = next(acl_iter) # Test quoted filenames
		assert third.index == ('2foo', '\n'), third.index
		try: next(acl_iter)
		except StopIteration: pass
		else: assert 0, "Too many elements in iterator"

		extractor = ACLExtractor(io.StringIO(record_list))
		acl_iter = extractor.iterate_starting_with(('1foo', 'bar'))
		assert next(acl_iter).index == ('1foo', 'bar', 'baz')
		try: next(acl_iter)
		except StopIteration: pass
		else: assert 0, "Too many elements in iterator"

	def make_backup_dirs(self):
		"""Create testfiles/acl_test[12] directories"""
		if self.acl_test1_rpath.lstat(): self.acl_test1_rpath.delete()
		self.acl_test1_rpath.mkdir()
		rp1_1 = self.acl_test1_rpath.append('1')
		rp1_2 = self.acl_test1_rpath.append('2')
		rp1_3 = self.acl_test1_rpath.append('3')
		list(map(rpath.RPath.touch, [rp1_1, rp1_2, rp1_3]))
		self.dir_acl.write_to_rp(self.acl_test1_rpath)
		self.acl1.write_to_rp(rp1_1)
		self.acl2.write_to_rp(rp1_2)
		self.acl3.write_to_rp(rp1_3)

		if self.acl_test2_rpath.lstat(): self.acl_test2_rpath.delete()
		self.acl_test2_rpath.mkdir()
		rp2_1, rp2_2, rp2_3 = list(map(self.acl_test2_rpath.append, ('1', '2', '3')))
		list(map(rpath.RPath.touch, (rp2_1, rp2_2, rp2_3)))
		self.sample_acl.write_to_rp(self.acl_test2_rpath)
		self.acl3.write_to_rp(rp2_1)
		self.acl1.write_to_rp(rp2_2)
		self.acl2.write_to_rp(rp2_3)

		# just create an empty dir for tests
		if self.acl_empty_rpath.lstat(): self.acl_empty_rpath.delete()
		self.acl_empty_rpath.mkdir()

	def testIterate(self):
		"""Test writing several records and then reading them back"""
		self.make_backup_dirs()
		self.make_temp_out_dirs()
		rp1 = self.acl_test1_rpath.append('1')
		rp2 = self.acl_test1_rpath.append('2')
		rp3 = self.acl_test1_rpath.append('3')

		# Now write records corresponding to above rps into file
		Globals.rbdir = tempdir
		man = metadata.PatchDiffMan()
		writer = man.get_acl_writer('snapshot', 10000)
		for rp in [self.acl_test1_rpath, rp1, rp2, rp3]:
			acl = AccessControlLists(rp.index)
			acl.read_from_rp(rp)
			writer.write_object(acl)
		writer.close()

		# Read back records and compare
		acl_iter = man.get_acls_at_time(10000, None)
		assert acl_iter, "No acl file found"
		dir_acl_reread = next(acl_iter)
		assert dir_acl_reread == self.dir_acl
		acl1_reread = next(acl_iter)
		assert acl1_reread == self.acl1
		acl2_reread = next(acl_iter)
		assert acl2_reread == self.acl2
		acl3_reread = next(acl_iter)
		assert acl3_reread == self.acl3
		try: extra = next(acl_iter)
		except StopIteration: pass
		else: assert 0, "Got unexpected object: " + repr(extra)

	def testSeriesLocal(self):
		"""Test backing up and restoring directories with ACLs locally"""
		self.make_backup_dirs()
		dirlist = [self.acl_test1_dir, self.acl_empty_dir,
				   self.acl_test2_dir, self.acl_test1_dir]
		BackupRestoreSeries(1, 1, dirlist, compare_acls = 1)

	def testSeriesRemote(self):
		"""Test backing up, restoring directories with EA remotely"""
		self.make_backup_dirs()
		dirlist = [self.acl_test1_dir, self.acl_test2_dir,
				   self.acl_empty_dir, self.acl_test1_dir]
		BackupRestoreSeries(None, None, dirlist, compare_acls = 1)

	def test_final_local(self):
		"""Test backing up and restoring using 'rdiff-backup' script"""
		self.make_backup_dirs()
		self.make_temp_out_dirs()
		rdiff_backup(1, 1, self.acl_test1_rpath.path, tempdir.path,
					 current_time = 10000)
		assert CompareRecursive(self.acl_test1_rpath, tempdir, compare_acls = 1)

		rdiff_backup(1, 1, self.acl_test2_rpath.path, tempdir.path,
					 current_time = 20000)
		assert CompareRecursive(self.acl_test2_rpath, tempdir, compare_acls = 1)

		rdiff_backup(1, 1, tempdir.path, restore_dir.path,
					 extra_options = '-r 10000')
		assert CompareRecursive(self.acl_test1_rpath, restore_dir,
								compare_acls = 1)

		restore_dir.delete()
		rdiff_backup(1, 1, tempdir.path, restore_dir.path,
					 extra_options = '-r now')
		assert CompareRecursive(self.acl_test2_rpath, restore_dir,
								compare_acls = 1)

	def test_acl_mapping(self):
		"""Test mapping ACL names"""
		def make_dir(rootrp):
			if rootrp.lstat(): rootrp.delete()
			rootrp.mkdir()
			rp = rootrp.append('1')
			rp.touch()
			acl = AccessControlLists(('1',), """user::rwx
user:root:rwx
user:ben:---
user:bin:r--
group::r-x
group:root:r-x
group:ben:-w-
mask::r-x
other::---""")
			rp.write_acl(acl)
			return rp

		def write_mapping_file(rootrp):
			map_rp = rootrp.append('mapping_file')
			map_rp.write_string("root:ben\nben:bin\nbin:root")
			return map_rp

		def get_perms_of_user(acl, user):
			"""Return the permissions of ACL_USER in acl, or None"""
			for typechar, owner_pair, perms in acl.entry_list:
				if typechar == "u" and owner_pair[1] == user:
					return perms
			return None

		self.make_temp_out_dirs()
		rootrp = rpath.RPath(Globals.local_connection,
							os.path.join(abs_test_dir, 'acl_map_test'))
		rp = make_dir(rootrp)
		map_rp = write_mapping_file(rootrp)

		rdiff_backup(1, 1, rootrp.path, tempdir.path,
					 extra_options = "--user-mapping-file %s" % (map_rp.path,))

		out_rp = tempdir.append('1')
		assert out_rp.isreg()
		out_acl = tempdir.append('1').get_acl()
		assert get_perms_of_user(out_acl, 'root') == 4
		assert get_perms_of_user(out_acl, 'ben') == 7
		assert get_perms_of_user(out_acl, 'bin') == 0

	def test_acl_dropping(self):
		"""Test dropping of ACL names"""
		self.make_temp_out_dirs()
		rp = tempdir.append('1')
		rp.touch()
		"""ben uses a dvorak keyboard, and these sequences are
			analogous to asdfsjkd for a qwerty user... these
			users and groups are not expected to exist. -dean"""
		acl = AccessControlLists(('1',), """user::rwx
user:aoensutheu:r--
group::r-x
group:aeuai:r-x
group:enutohnh:-w-
other::---""")
		rp.write_acl(acl)
		rp2 = tempdir.append('1')
		acl2 = AccessControlLists(('1',))
		acl2.read_from_rp(rp2)
		assert acl2.is_basic()
		Globals.never_drop_acls = 1
		try: rp.write_acl(acl)
		except SystemExit: pass
		else: assert 0, "Above should have exited with fatal error"
		Globals.never_drop_acls = None

	def test_nochange(self):
		"""Make sure files with ACLs not unnecessarily flagged changed"""
		self.make_temp_out_dirs()
		self.make_backup_dirs()
		rdiff_backup(1, 1, self.acl_test1_rpath.path, tempdir.path,
					 current_time = 10000)
		rdiff_backup(1, 1, self.acl_test1_rpath.path, tempdir.path,
					 current_time = 20000)
		incdir = tempdir.append('rdiff-backup-data').append('increments')
		assert incdir.isdir(), incdir
		assert not incdir.listdir(), incdir.listdir()


class CombinedTest(unittest.TestCase):
	"""Test backing up and restoring directories with both EAs and ACLs"""
	combo_test1_dir = os.path.join(abs_test_dir, 'ea_acl_test1')
	combo_test1_rpath = rpath.RPath(Globals.local_connection, combo_test1_dir)
	combo_test2_dir = os.path.join(abs_test_dir, 'ea_acl_test2')
	combo_test2_rpath = rpath.RPath(Globals.local_connection, combo_test2_dir)
	combo_empty_dir = os.path.join(abs_test_dir, 'ea_acl_empty')
	combo_empty_rpath = rpath.RPath(Globals.local_connection, combo_empty_dir)

	def make_backup_dirs(self):
		"""Create testfiles/ea_acl_test[12] directories"""
		if self.combo_test1_rpath.lstat(): self.combo_test1_rpath.delete()
		if self.combo_test2_rpath.lstat(): self.combo_test2_rpath.delete()
		self.combo_test1_rpath.mkdir()
		rp1_1, rp1_2, rp1_3 = list(map(self.combo_test1_rpath.append, ('1', '2', '3')))
		list(map(rpath.RPath.touch, [rp1_1, rp1_2, rp1_3]))
		ACLTest.dir_acl.write_to_rp(self.combo_test1_rpath)
		EATest.sample_ea.write_to_rp(self.combo_test1_rpath)
		ACLTest.acl1.write_to_rp(rp1_1)
		EATest.ea2.write_to_rp(rp1_2)
		ACLTest.acl3.write_to_rp(rp1_3)
		EATest.ea3.write_to_rp(rp1_3)

		self.combo_test2_rpath.mkdir()
		rp2_1, rp2_2, rp2_3 = list(map(self.combo_test2_rpath.append, ('1', '2', '3')))
		list(map(rpath.RPath.touch, [rp2_1, rp2_2, rp2_3]))
		ACLTest.sample_acl.write_to_rp(self.combo_test2_rpath)
		EATest.ea1.write_to_rp(rp2_1)
		EATest.ea3.write_to_rp(rp2_2)
		ACLTest.acl2.write_to_rp(rp2_2)

		# just create an empty dir for tests
		if self.combo_empty_rpath.lstat(): self.combo_empty_rpath.delete()
		self.combo_empty_rpath.mkdir()

	def testSeriesLocal(self):
		"""Test backing up and restoring EAs/ACLs locally"""
		self.make_backup_dirs()
		dirlist = [self.combo_test1_dir, self.combo_test2_dir,
				   self.combo_empty_dir, self.combo_test1_dir]
		BackupRestoreSeries(1, 1, dirlist,
							compare_eas = 1, compare_acls = 1)

	def testSeriesRemote(self):
		"""Test backing up and restoring EAs/ACLs locally"""
		self.make_backup_dirs()
		dirlist = [self.combo_test1_dir, self.combo_empty_dir,
				   self.combo_test2_dir, self.combo_test1_dir]
		BackupRestoreSeries(None, None, dirlist,
							compare_eas = 1, compare_acls = 1)


if __name__ == "__main__": unittest.main()
