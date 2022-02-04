import unittest
import os
import io
import pwd
import grp
from rdiff_backup import Globals, rpath, user_group
from rdiffbackup import meta_mgr
from rdiffbackup.meta import acl_posix, ea
from commontest import rdiff_backup, abs_test_dir, abs_output_dir, \
    abs_restore_dir, BackupRestoreSeries, compare_recursive

user_group.init_user_mapping()
user_group.init_group_mapping()
tempdir = rpath.RPath(Globals.local_connection, abs_output_dir)
restore_dir = rpath.RPath(Globals.local_connection, abs_restore_dir)


class EATest(unittest.TestCase):
    """Test extended attributes"""
    sample_ea = ea.ExtendedAttributes(
        (), {
            b'user.empty':
            b'',
            b'user.not_empty':
            b'foobar',
            b'user.third':
            b'hello',
            b'user.binary':
            bytes((0, 1, 2, 140)) + b'/="',
            b'user.multiline':
            b"""This is a fairly long extended attribute.
                Encoding it will require several lines of
                base64.""" + bytes((177, ) * 300)
        })
    empty_ea = ea.ExtendedAttributes(())
    ea1 = ea.ExtendedAttributes(('e1', ), sample_ea.attr_dict.copy())
    ea1.delete(b'user.not_empty')
    ea2 = ea.ExtendedAttributes(('e2', ), sample_ea.attr_dict.copy())
    ea2.set(b'user.third', b'Another random attribute')
    ea3 = ea.ExtendedAttributes(('e3', ))
    ea4 = ea.ExtendedAttributes(('e4', ),
                                {b'user.deleted': b'File to be deleted'})
    ea_test1_dir = os.path.join(abs_test_dir, b'ea_test1')
    ea_test1_rpath = rpath.RPath(Globals.local_connection, ea_test1_dir)
    ea_test2_dir = os.path.join(abs_test_dir, b'ea_test2')
    ea_test2_rpath = rpath.RPath(Globals.local_connection, ea_test2_dir)
    ea_empty_dir = os.path.join(abs_test_dir, b'ea_empty')
    ea_empty_rpath = rpath.RPath(Globals.local_connection, ea_empty_dir)

    def make_temp_out_dirs(self):
        """Make temp output and restore directories empty"""
        tempdir.setdata()  # in case the file changed in-between
        if tempdir.lstat():
            tempdir.delete()
        tempdir.mkdir()
        restore_dir.setdata()
        if restore_dir.lstat():
            restore_dir.delete()

    def testBasic(self):
        """Test basic writing and reading of extended attributes"""
        self.make_temp_out_dirs()
        new_ea = ea.ExtendedAttributes(())
        new_ea.read_from_rp(tempdir)
        # we ignore SELinux extended attributes for comparison
        if new_ea.attr_dict:
            new_ea.attr_dict.pop(b'security.selinux', None)
        self.assertFalse(
            new_ea.attr_dict,
            "The attributes of {dir} should have been empty: {attr}".format(
                dir=tempdir, attr=new_ea.attr_dict))
        self.assertNotEqual(new_ea, self.sample_ea)
        self.assertEqual(new_ea, self.empty_ea)

        self.sample_ea.write_to_rp(tempdir)
        new_ea.read_from_rp(tempdir)
        if new_ea.attr_dict:
            new_ea.attr_dict.pop(b'security.selinux', None)
        self.assertEqual(new_ea.attr_dict, self.sample_ea.attr_dict)
        self.assertEqual(new_ea, self.sample_ea)

    def testRecord(self):
        """Test writing a record and reading it back"""
        record = ea.ExtendedAttributesFile._object_to_record(self.sample_ea)
        new_ea = ea.EAExtractor._record_to_object(record)
        if not new_ea == self.sample_ea:
            new_list = list(new_ea.attr_dict.keys())
            sample_list = list(self.sample_ea.attr_dict.keys())
            new_list.sort()
            sample_list.sort()
            self.assertEqual(new_list, sample_list)
            for name in new_list:
                self.assertEqual(self.sample_ea.get(name), new_ea.get(name))
            self.assertEqual(self.sample_ea.index, new_ea.index)
            self.assertFalse("We shouldn't have gotten this far")

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
        extractor = ea.EAExtractor(io.BytesIO(os.fsencode(record_list)))
        ea_iter = extractor._iterate_starting_with(())
        first = next(ea_iter)
        self.assertEqual(first.index, (b'0foo', ))
        second = next(ea_iter)
        self.assertEqual(second.index, (b'1foo', b'bar', b'baz'))
        third = next(ea_iter)  # Test quoted filenames
        self.assertEqual(third.index, (b'2foo', b'\n'))
        with self.assertRaises(StopIteration,
                               msg="Too many elements in iterator"):
            next(ea_iter)

        extractor = ea.EAExtractor(io.BytesIO(os.fsencode(record_list)))
        ea_iter = extractor._iterate_starting_with((b'1foo', b'bar'))
        self.assertEqual(next(ea_iter).index, (b'1foo', b'bar', b'baz'))
        with self.assertRaises(StopIteration,
                               msg="Too many elements in iterator"):
            next(ea_iter)

    def make_backup_dirs(self):
        """Create testfiles/ea_test[12] directories

        Goal is to set range of extended attributes, to give good test
        to extended attribute code.

        """
        if self.ea_test1_rpath.lstat():
            self.ea_test1_rpath.delete()
        if self.ea_test2_rpath.lstat():
            self.ea_test2_rpath.delete()
        self.ea_test1_rpath.mkdir()
        rp1_1 = self.ea_test1_rpath.append('e1')
        rp1_2 = self.ea_test1_rpath.append('e2')
        rp1_3 = self.ea_test1_rpath.append('e3')
        rp1_4 = self.ea_test1_rpath.append('e4')
        list(map(rpath.RPath.touch, [rp1_1, rp1_2, rp1_3, rp1_4]))
        self.sample_ea.write_to_rp(self.ea_test1_rpath)
        self.ea1.write_to_rp(rp1_1)
        self.ea2.write_to_rp(rp1_2)
        self.ea4.write_to_rp(rp1_4)

        self.ea_test2_rpath.mkdir()
        rp2_1 = self.ea_test2_rpath.append('e1')
        rp2_2 = self.ea_test2_rpath.append('e2')
        rp2_3 = self.ea_test2_rpath.append('e3')
        list(map(rpath.RPath.touch, [rp2_1, rp2_2, rp2_3]))
        self.ea3.write_to_rp(self.ea_test2_rpath)
        self.sample_ea.write_to_rp(rp2_1)
        self.ea1.write_to_rp(rp2_2)
        self.ea2.write_to_rp(rp2_3)

        # just create an empty dir for tests
        if self.ea_empty_rpath.lstat():
            self.ea_empty_rpath.delete()
        self.ea_empty_rpath.mkdir()

    def testIterate(self):
        """Test writing several records and then reading them back"""
        self.make_backup_dirs()
        rp1 = self.ea_test1_rpath.append('e1')
        rp2 = self.ea_test1_rpath.append('e2')
        rp3 = self.ea_test1_rpath.append('e3')

        # Now write records corresponding to above rps into file
        Globals.rbdir = tempdir
        man = meta_mgr.PatchDiffMan()
        writer = man._writer_helper('snapshot', 10000,
                                    ea.get_plugin_class(), force=True)
        for rp in [self.ea_test1_rpath, rp1, rp2, rp3]:
            # without enforcing, rp3 might have no EA and not be saved
            writer.write_object(rp, force_empty=True)
        writer.close()

        # Read back records and compare
        ea_iter = man._iter_helper(10000, None, ea.get_plugin_class())
        self.assertTrue(ea_iter, "No extended_attributes.<time> file found")
        sample_ea_reread = next(ea_iter)
        # we ignore SELinux extended attributes for comparison
        if sample_ea_reread.attr_dict:
            sample_ea_reread.attr_dict.pop(b'security.selinux', None)
        # Check if re-read EAs are different from sample ones
        self.assertEqual(sample_ea_reread, self.sample_ea)
        ea1_reread = next(ea_iter)
        if ea1_reread.attr_dict:
            ea1_reread.attr_dict.pop(b'security.selinux', None)
        self.assertEqual(ea1_reread, self.ea1)
        ea2_reread = next(ea_iter)
        if ea2_reread.attr_dict:
            ea2_reread.attr_dict.pop(b'security.selinux', None)
        self.assertEqual(ea2_reread, self.ea2)
        ea3_reread = next(ea_iter)
        if ea3_reread.attr_dict:
            ea3_reread.attr_dict.pop(b'security.selinux', None)
        self.assertEqual(ea3_reread, self.ea3)
        with self.assertRaises(StopIteration,
                               msg="Too many elements in iterator"):
            next(ea_iter)

    def testSeriesLocal(self):
        """Test backing up and restoring directories with EAs locally"""
        self.make_backup_dirs()
        dirlist = [
            self.ea_test1_dir, self.ea_empty_dir, self.ea_test2_dir,
            self.ea_test1_dir
        ]
        BackupRestoreSeries(1, 1, dirlist, compare_eas=1)

    def testSeriesRemote(self):
        """Test backing up, restoring directories with EA remotely"""
        self.make_backup_dirs()
        dirlist = [
            self.ea_test1_dir, self.ea_test2_dir, self.ea_empty_dir,
            self.ea_test1_dir
        ]
        BackupRestoreSeries(None, None, dirlist, compare_eas=1)

    def test_final_local(self):
        """Test backing up and restoring using 'rdiff-backup' script"""
        self.make_backup_dirs()
        self.make_temp_out_dirs()
        rdiff_backup(1,
                     1,
                     self.ea_test1_rpath.path,
                     tempdir.path,
                     current_time=10000)
        self.assertTrue(
            compare_recursive(self.ea_test1_rpath, tempdir, compare_eas=1))

        rdiff_backup(1,
                     1,
                     self.ea_test2_rpath.path,
                     tempdir.path,
                     current_time=20000)
        self.assertTrue(
            compare_recursive(self.ea_test2_rpath, tempdir, compare_eas=1))

        rdiff_backup(1,
                     1,
                     tempdir.path,
                     restore_dir.path,
                     extra_options=b'-r 10000')
        self.assertTrue(
            compare_recursive(self.ea_test1_rpath, restore_dir, compare_eas=1))


class ACLTest(unittest.TestCase):
    """Test access control lists"""

    current_user = os.getenv('RDIFF_TEST_USER', pwd.getpwuid(os.getuid()).pw_name)
    current_group = os.getenv('RDIFF_TEST_GROUP', grp.getgrgid(os.getgid()).gr_name)

    sample_acl = acl_posix.AccessControlLists((), """user::rwx
user:root:rwx
group::r-x
group:root:r-x
mask::r-x
other::---""")
    dir_acl = acl_posix.AccessControlLists((), """user::rwx
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
    acl1 = acl_posix.AccessControlLists((b'a1', ), """user::r--
user:{0}:---
group::---
group:root:---
mask::---
other::---""".format(current_user))
    acl2 = acl_posix.AccessControlLists((b'a2', ), """user::rwx
group::r-x
group:{0}:rwx
mask::---
other::---""".format(current_group))
    acl3 = acl_posix.AccessControlLists((b'a3', ), """user::rwx
user:root:---
group::r-x
mask::---
other::---""")
    empty_acl = acl_posix.AccessControlLists(
        (), "user::rwx\ngroup::---\nother::---")
    acl_test1_dir = os.path.join(abs_test_dir, b'acl_test1')
    acl_test1_rpath = rpath.RPath(Globals.local_connection, acl_test1_dir)
    acl_test2_dir = os.path.join(abs_test_dir, b'acl_test2')
    acl_test2_rpath = rpath.RPath(Globals.local_connection, acl_test2_dir)
    acl_empty_dir = os.path.join(abs_test_dir, b'acl_empty')
    acl_empty_rpath = rpath.RPath(Globals.local_connection, acl_empty_dir)

    def make_temp_out_dirs(self):
        """Make temp output and restore directories empty"""
        tempdir.setdata()  # in case the file changed in-between
        if tempdir.lstat():
            tempdir.delete()
        tempdir.mkdir()
        restore_dir.setdata()  # in case the file changed in-between
        if restore_dir.lstat():
            restore_dir.delete()

    def testBasic(self):
        """Test basic writing and reading of ACLs"""
        self.make_temp_out_dirs()
        new_acl = acl_posix.AccessControlLists(())
        tempdir.chmod(0o700)
        new_acl.read_from_rp(tempdir)
        self.assertTrue(new_acl.is_basic())
        self.assertNotEqual(new_acl, self.sample_acl)
        self.assertEqual(new_acl, self.empty_acl)

        self.sample_acl.write_to_rp(tempdir)
        new_acl.read_from_rp(tempdir)
        self.assertEqual(str(new_acl), str(self.sample_acl))
        self.assertEqual(new_acl, self.sample_acl)

    def testBasicDir(self):
        """Test reading and writing of ACL w/ defaults to directory"""
        self.make_temp_out_dirs()
        new_acl = acl_posix.AccessControlLists(())
        new_acl.read_from_rp(tempdir)
        self.assertTrue(new_acl.is_basic())
        self.assertNotEqual(new_acl, self.dir_acl)

        self.dir_acl.write_to_rp(tempdir)
        new_acl.read_from_rp(tempdir)
        self.assertFalse(new_acl.is_basic())
        if not new_acl == self.dir_acl:
            self.assertTrue(new_acl._eq_verbose(self.dir_acl))
            self.assertFalse("Shouldn't be here---eq != _eq_verbose?")

    def testRecord(self):
        """Test writing a record and reading it back"""
        record = acl_posix.AccessControlListFile._object_to_record(
            self.sample_acl)
        new_acl = acl_posix.ACLExtractor._record_to_object(record)
        self.assertEqual(new_acl, self.sample_acl,
                         "New_acl {new.entry_list}\n"
                         "sample_acl {sample.entry_list}\n"
                         "New_acl text {new!s}\n"
                         "Sample acl text {sample!s}".format(
                             new=new_acl, sample=self.sample_acl))

        record2 = acl_posix.AccessControlListFile._object_to_record(
            self.dir_acl)
        new_acl2 = acl_posix.ACLExtractor._record_to_object(record2)
        if not new_acl2 == self.dir_acl:
            self.assertTrue(new_acl2._eq_verbose(self.dir_acl))
            self.assertFalse("Shouldn't be here---eq != _eq_verbose?")

    def testExtractor(self):
        """Test seeking inside a record list"""
        record_list = """# file: 0foo
user::r--
user:{0}:---
group::---
group:root:---
mask::---
other::---
# file: 1foo/bar/baz
user::r--
user:{0}:---
group::---
group:root:---
mask::---
other::---
# file: 2foo/\\012
user::r--
user:{0}:---
group::---
group:root:---
mask::---
other::---
""".format(self.current_user)
        extractor = acl_posix.ACLExtractor(io.BytesIO(os.fsencode(record_list)))
        acl_iter = extractor._iterate_starting_with(())
        first = next(acl_iter)
        self.assertEqual(first.index, (b'0foo', ))
        second = next(acl_iter)
        self.assertEqual(second.index, (b'1foo', b'bar', b'baz'))
        third = next(acl_iter)  # Test quoted filenames
        self.assertEqual(third.index, (b'2foo', b'\n'))
        with self.assertRaises(StopIteration,
                               msg="Too many elements in iterator"):
            next(acl_iter)

        extractor = acl_posix.ACLExtractor(io.BytesIO(os.fsencode(record_list)))
        acl_iter = extractor._iterate_starting_with((b'1foo', b'bar'))
        self.assertEqual(next(acl_iter).index, (b'1foo', b'bar', b'baz'))
        with self.assertRaises(StopIteration,
                               msg="Too many elements in iterator"):
            next(acl_iter)

    def make_backup_dirs(self):
        """Create testfiles/acl_test[12] directories"""
        if self.acl_test1_rpath.lstat():
            self.acl_test1_rpath.delete()
        self.acl_test1_rpath.mkdir()
        rp1_1 = self.acl_test1_rpath.append('a1')
        rp1_2 = self.acl_test1_rpath.append('a2')
        rp1_3 = self.acl_test1_rpath.append('a3')
        list(map(rpath.RPath.touch, [rp1_1, rp1_2, rp1_3]))
        self.dir_acl.write_to_rp(self.acl_test1_rpath)
        self.acl1.write_to_rp(rp1_1)
        self.acl2.write_to_rp(rp1_2)
        self.acl3.write_to_rp(rp1_3)

        if self.acl_test2_rpath.lstat():
            self.acl_test2_rpath.delete()
        self.acl_test2_rpath.mkdir()
        rp2_1, rp2_2, rp2_3 = list(
            map(self.acl_test2_rpath.append, ('a1', 'a2', 'a3')))
        list(map(rpath.RPath.touch, (rp2_1, rp2_2, rp2_3)))
        self.sample_acl.write_to_rp(self.acl_test2_rpath)
        self.acl3.write_to_rp(rp2_1)
        self.acl1.write_to_rp(rp2_2)
        self.acl2.write_to_rp(rp2_3)

        # just create an empty dir for tests
        if self.acl_empty_rpath.lstat():
            self.acl_empty_rpath.delete()
        self.acl_empty_rpath.mkdir()

    def testIterate(self):
        """Test writing several records and then reading them back"""
        self.make_backup_dirs()
        self.make_temp_out_dirs()
        rp1 = self.acl_test1_rpath.append('a1')
        rp2 = self.acl_test1_rpath.append('a2')
        rp3 = self.acl_test1_rpath.append('a3')

        # Now write records corresponding to above rps into file
        Globals.rbdir = tempdir
        man = meta_mgr.PatchDiffMan()
        writer = man._writer_helper('snapshot', 10000,
                                    acl_posix.get_plugin_class(), force=True)
        for rp in [self.acl_test1_rpath, rp1, rp2, rp3]:
            writer.write_object(rp)
        writer.close()

        # Read back records and compare
        acl_iter = man._iter_helper(10000, None, acl_posix.get_plugin_class())
        self.assertTrue(acl_iter, "No acl file found")
        dir_acl_reread = next(acl_iter)
        self.assertEqual(dir_acl_reread, self.dir_acl)
        acl1_reread = next(acl_iter)
        self.assertEqual(acl1_reread, self.acl1)
        acl2_reread = next(acl_iter)
        self.assertEqual(acl2_reread, self.acl2)
        acl3_reread = next(acl_iter)
        self.assertEqual(acl3_reread, self.acl3)
        with self.assertRaises(StopIteration,
                               msg="Too many elements in iterator"):
            next(acl_iter)

    def testSeriesLocal(self):
        """Test backing up and restoring directories with ACLs locally"""
        self.make_backup_dirs()
        dirlist = [
            self.acl_test1_dir, self.acl_empty_dir, self.acl_test2_dir,
            self.acl_test1_dir
        ]
        BackupRestoreSeries(1, 1, dirlist, compare_acls=1)

    def testSeriesRemote(self):
        """Test backing up, restoring directories with EA remotely"""
        self.make_backup_dirs()
        dirlist = [
            self.acl_test1_dir, self.acl_test2_dir, self.acl_empty_dir,
            self.acl_test1_dir
        ]
        BackupRestoreSeries(None, None, dirlist, compare_acls=1)

    def test_final_local(self):
        """Test backing up and restoring using 'rdiff-backup' script"""
        self.make_backup_dirs()
        self.make_temp_out_dirs()
        rdiff_backup(1,
                     1,
                     self.acl_test1_rpath.path,
                     tempdir.path,
                     current_time=10000)
        self.assertTrue(
            compare_recursive(self.acl_test1_rpath, tempdir, compare_acls=1))

        rdiff_backup(1,
                     1,
                     self.acl_test2_rpath.path,
                     tempdir.path,
                     current_time=20000)
        self.assertTrue(
            compare_recursive(self.acl_test2_rpath, tempdir, compare_acls=1))

        rdiff_backup(1,
                     1,
                     tempdir.path,
                     restore_dir.path,
                     extra_options=b'-r 10000')
        self.assertTrue(
            compare_recursive(self.acl_test1_rpath, restore_dir,
                              compare_acls=1))

        restore_dir.delete()
        rdiff_backup(1,
                     1,
                     tempdir.path,
                     restore_dir.path,
                     extra_options=b'-r now')
        self.assertTrue(
            compare_recursive(self.acl_test2_rpath, restore_dir,
                              compare_acls=1))

    def test_acl_mapping(self):
        """Test mapping ACL names"""

        def make_dir(rootrp):
            if rootrp.lstat():
                rootrp.delete()
            rootrp.mkdir()
            rp = rootrp.append('a1')
            rp.touch()
            acl = acl_posix.AccessControlLists(('a1', ), """user::rwx
user:root:rwx
user:{0}:---
user:bin:r--
group::r-x
group:root:r-x
group:{1}:-w-
mask::r-x
other::---""".format(self.current_user, self.current_group))
            rp.write_acl(acl)
            return rp

        def write_mapping_files(rootrp):
            users_map_rp = rootrp.append('users_map_file')
            users_map_rp.write_string("root:{u}\n{u}:bin\nbin:root".format(
                u=self.current_user))
            groups_map_rp = rootrp.append('groups_map_file')
            groups_map_rp.write_string("root:{g}\n{g}:bin\nbin:root".format(
                g=self.current_group))
            return (users_map_rp, groups_map_rp)

        def get_perms(acl, owner, owner_type):
            """Return the permissions of ACL_USER in acl, or None"""
            for typechar, owner_pair, perms in acl.entry_list:
                if typechar == owner_type and owner_pair[1] == owner:
                    return perms
            return None

        self.make_temp_out_dirs()
        rootrp = rpath.RPath(Globals.local_connection,
                             os.path.join(abs_test_dir, b'acl_map_test'))
        make_dir(rootrp)
        (users_map_rp, groups_map_rp) = write_mapping_files(rootrp)

        rdiff_backup(
            1, 1, rootrp.path, tempdir.path,
            extra_options=b"--user-mapping-file %b --group-mapping-file %b" % (
                users_map_rp.path, groups_map_rp.path))

        out_rp = tempdir.append('a1')
        self.assertTrue(out_rp.isreg())
        out_acl = tempdir.append('a1').get_acl()
        self.assertEqual(get_perms(out_acl, 'root', 'u'), 4)
        self.assertEqual(get_perms(out_acl, self.current_user, 'u'), 7)
        self.assertEqual(get_perms(out_acl, 'bin', 'u'), 0)
        self.assertEqual(get_perms(out_acl, 'root', 'g'), None)
        self.assertEqual(get_perms(out_acl, self.current_group, 'g'), 5)
        self.assertEqual(get_perms(out_acl, 'bin', 'g'), 2)

    def test_acl_dropping(self):
        """Test dropping of ACL names"""
        self.make_temp_out_dirs()
        rp = tempdir.append('a1')
        rp.touch()
        """ben uses a dvorak keyboard, and these sequences are
        analogous to asdfsjkd for a qwerty user... these
        users and groups are not expected to exist. -dean"""
        acl = acl_posix.AccessControlLists(('a1', ), """user::rwx
user:aoensutheu:r--
group::r-x
group:aeuai:r-x
group:enutohnh:-w-
other::---""")
        rp.write_acl(acl)
        rp2 = tempdir.append('a1')
        acl2 = acl_posix.AccessControlLists(('a1', ))
        acl2.read_from_rp(rp2)
        self.assertTrue(acl2.is_basic())
        Globals.never_drop_acls = 1
        with self.assertRaises(SystemExit):
            rp.write_acl(acl)
        Globals.never_drop_acls = None

    def test_nochange(self):
        """Make sure files with ACLs not unnecessarily flagged changed"""
        self.make_temp_out_dirs()
        self.make_backup_dirs()
        rdiff_backup(1,
                     1,
                     self.acl_test1_rpath.path,
                     tempdir.path,
                     current_time=10000)
        rdiff_backup(1,
                     1,
                     self.acl_test1_rpath.path,
                     tempdir.path,
                     current_time=20000)
        incdir = tempdir.append('rdiff-backup-data', 'increments')
        self.assertTrue(incdir.isdir())
        self.assertFalse(incdir.listdir())


class CombinedTest(unittest.TestCase):
    """Test backing up and restoring directories with both EAs and ACLs"""
    combo_test1_dir = os.path.join(abs_test_dir, b'ea_acl_test1')
    combo_test1_rpath = rpath.RPath(Globals.local_connection, combo_test1_dir)
    combo_test2_dir = os.path.join(abs_test_dir, b'ea_acl_test2')
    combo_test2_rpath = rpath.RPath(Globals.local_connection, combo_test2_dir)
    combo_empty_dir = os.path.join(abs_test_dir, b'ea_acl_empty')
    combo_empty_rpath = rpath.RPath(Globals.local_connection, combo_empty_dir)

    def make_backup_dirs(self):
        """Create testfiles/ea_acl_test[12] directories"""
        if self.combo_test1_rpath.lstat():
            self.combo_test1_rpath.delete()
        if self.combo_test2_rpath.lstat():
            self.combo_test2_rpath.delete()
        self.combo_test1_rpath.mkdir()
        rp1_1, rp1_2, rp1_3 = list(
            map(self.combo_test1_rpath.append, ('c1', 'c2', 'c3')))
        list(map(rpath.RPath.touch, [rp1_1, rp1_2, rp1_3]))
        ACLTest.dir_acl.write_to_rp(self.combo_test1_rpath)
        EATest.sample_ea.write_to_rp(self.combo_test1_rpath)
        ACLTest.acl1.write_to_rp(rp1_1)
        EATest.ea2.write_to_rp(rp1_2)
        ACLTest.acl3.write_to_rp(rp1_3)
        EATest.ea3.write_to_rp(rp1_3)

        self.combo_test2_rpath.mkdir()
        rp2_1, rp2_2, rp2_3 = list(
            map(self.combo_test2_rpath.append, ('c1', 'c2', 'c3')))
        list(map(rpath.RPath.touch, [rp2_1, rp2_2, rp2_3]))
        ACLTest.sample_acl.write_to_rp(self.combo_test2_rpath)
        EATest.ea1.write_to_rp(rp2_1)
        EATest.ea3.write_to_rp(rp2_2)
        ACLTest.acl2.write_to_rp(rp2_2)

        # just create an empty dir for tests
        if self.combo_empty_rpath.lstat():
            self.combo_empty_rpath.delete()
        self.combo_empty_rpath.mkdir()

    def testSeriesLocal(self):
        """Test backing up and restoring EAs/ACLs locally"""
        self.make_backup_dirs()
        dirlist = [
            self.combo_test1_dir, self.combo_test2_dir, self.combo_empty_dir,
            self.combo_test1_dir
        ]
        BackupRestoreSeries(1, 1, dirlist, compare_eas=1, compare_acls=1)

    def testSeriesRemote(self):
        """Test backing up and restoring EAs/ACLs locally"""
        self.make_backup_dirs()
        dirlist = [
            self.combo_test1_dir, self.combo_empty_dir, self.combo_test2_dir,
            self.combo_test1_dir
        ]
        BackupRestoreSeries(None, None, dirlist, compare_eas=1, compare_acls=1)


if __name__ == "__main__":
    unittest.main()
