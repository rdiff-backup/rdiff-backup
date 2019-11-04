import unittest
import os
import io
import pwd
import grp
from rdiff_backup.eas_acls import AccessControlLists, metadata, ACLExtractor, \
    Record2ACL, ACL2Record, ExtendedAttributes, EAExtractor, EA2Record, Record2EA
from rdiff_backup import Globals, rpath, user_group
from commontest import rdiff_backup, abs_test_dir, abs_output_dir, abs_restore_dir, \
    BackupRestoreSeries, CompareRecursive

user_group.init_user_mapping()
user_group.init_group_mapping()
tempdir = rpath.RPath(Globals.local_connection, abs_output_dir)
restore_dir = rpath.RPath(Globals.local_connection, abs_restore_dir)


class EATest(unittest.TestCase):
    """Test extended attributes"""
    sample_ea = ExtendedAttributes(
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
    empty_ea = ExtendedAttributes(())
    ea1 = ExtendedAttributes(('e1', ), sample_ea.attr_dict.copy())
    ea1.delete(b'user.not_empty')
    ea2 = ExtendedAttributes(('e2', ), sample_ea.attr_dict.copy())
    ea2.set(b'user.third', b'Another random attribute')
    ea3 = ExtendedAttributes(('e3', ))
    ea4 = ExtendedAttributes(('e4', ),
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
        new_ea = ExtendedAttributes(())
        new_ea.read_from_rp(tempdir)
        # we ignore SELinux extended attributes for comparaison
        if new_ea.attr_dict:
            new_ea.attr_dict.pop(b'security.selinux', None)
        assert not new_ea.attr_dict, "The attributes of %s should have been empty: %s" % (
            tempdir, new_ea.attr_dict)
        assert not new_ea == self.sample_ea
        assert new_ea != self.sample_ea
        assert new_ea == self.empty_ea

        self.sample_ea.write_to_rp(tempdir)
        new_ea.read_from_rp(tempdir)
        if new_ea.attr_dict:
            new_ea.attr_dict.pop(b'security.selinux', None)
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
        extractor = EAExtractor(io.BytesIO(os.fsencode(record_list)))
        ea_iter = extractor.iterate_starting_with(())
        first = next(ea_iter)
        assert first.index == (b'0foo', ), first
        second = next(ea_iter)
        assert second.index == (b'1foo', b'bar', b'baz'), second
        third = next(ea_iter)  # Test quoted filenames
        assert third.index == (b'2foo', b'\n'), third.index
        try:
            next(ea_iter)
        except StopIteration:
            pass
        else:
            assert 0, "Too many elements in iterator"

        extractor = EAExtractor(io.BytesIO(os.fsencode(record_list)))
        ea_iter = extractor.iterate_starting_with((b'1foo', b'bar'))
        assert next(ea_iter).index == (b'1foo', b'bar', b'baz')
        try:
            next(ea_iter)
        except StopIteration:
            pass
        else:
            assert 0, "Too many elements in iterator"

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
        # we ignore SELinux extended attributes for comparaison
        if sample_ea_reread.attr_dict:
            sample_ea_reread.attr_dict.pop(b'security.selinux', None)
        assert sample_ea_reread == self.sample_ea, "Re-read EAs %s are different from %s" % \
            (sample_ea_reread.attr_dict, self.sample_ea.attr_dict)
        ea1_reread = next(ea_iter)
        if ea1_reread.attr_dict:
            ea1_reread.attr_dict.pop(b'security.selinux', None)
        assert ea1_reread == self.ea1, "Re-read EAs %s are different from %s" % \
            (ea1_reread.attr_dict, self.ea1.attr_dict)
        ea2_reread = next(ea_iter)
        if ea2_reread.attr_dict:
            ea2_reread.attr_dict.pop(b'security.selinux', None)
        assert ea2_reread == self.ea2, "Re-read EAs %s are different from %s" % \
            (ea2_reread.attr_dict, self.ea2.attr_dict)
        ea3_reread = next(ea_iter)
        if ea3_reread.attr_dict:
            ea3_reread.attr_dict.pop(b'security.selinux', None)
        assert ea3_reread == self.ea3, "Re-read EAs %s are different from %s" % \
            (ea3_reread.attr_dict, self.ea3.attr_dict)
        try:
            next(ea_iter)
        except StopIteration:
            pass
        else:
            assert 0, "Expected end to iterator"

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
        assert CompareRecursive(self.ea_test1_rpath, tempdir, compare_eas=1)

        rdiff_backup(1,
                     1,
                     self.ea_test2_rpath.path,
                     tempdir.path,
                     current_time=20000)
        assert CompareRecursive(self.ea_test2_rpath, tempdir, compare_eas=1)

        rdiff_backup(1,
                     1,
                     tempdir.path,
                     restore_dir.path,
                     extra_options=b'-r 10000')
        assert CompareRecursive(self.ea_test1_rpath,
                                restore_dir,
                                compare_eas=1)


class ACLTest(unittest.TestCase):
    """Test access control lists"""

    current_user = os.getenv('RDIFF_TEST_USER', pwd.getpwuid(os.getuid()).pw_name)
    current_group = os.getenv('RDIFF_TEST_GROUP', grp.getgrgid(os.getgid()).gr_name)

    sample_acl = AccessControlLists((), """user::rwx
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
    acl1 = AccessControlLists((b'a1', ), """user::r--
user:{0}:---
group::---
group:root:---
mask::---
other::---""".format(current_user))
    acl2 = AccessControlLists((b'a2', ), """user::rwx
group::r-x
group:{0}:rwx
mask::---
other::---""".format(current_group))
    acl3 = AccessControlLists((b'a3', ), """user::rwx
user:root:---
group::r-x
mask::---
other::---""")
    empty_acl = AccessControlLists((), "user::rwx\ngroup::---\nother::---")
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
        extractor = ACLExtractor(io.BytesIO(os.fsencode(record_list)))
        acl_iter = extractor.iterate_starting_with(())
        first = next(acl_iter)
        assert first.index == (b'0foo', ), first
        second = next(acl_iter)
        assert second.index == (b'1foo', b'bar', b'baz'), second
        third = next(acl_iter)  # Test quoted filenames
        assert third.index == (b'2foo', b'\n'), third.index
        try:
            next(acl_iter)
        except StopIteration:
            pass
        else:
            assert 0, "Too many elements in iterator"

        extractor = ACLExtractor(io.BytesIO(os.fsencode(record_list)))
        acl_iter = extractor.iterate_starting_with((b'1foo', b'bar'))
        assert next(acl_iter).index == (b'1foo', b'bar', b'baz')
        try:
            next(acl_iter)
        except StopIteration:
            pass
        else:
            assert 0, "Too many elements in iterator"

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
        try:
            extra = next(acl_iter)
        except StopIteration:
            pass
        else:
            assert 0, "Got unexpected object: " + repr(extra)

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
        assert CompareRecursive(self.acl_test1_rpath, tempdir, compare_acls=1)

        rdiff_backup(1,
                     1,
                     self.acl_test2_rpath.path,
                     tempdir.path,
                     current_time=20000)
        assert CompareRecursive(self.acl_test2_rpath, tempdir, compare_acls=1)

        rdiff_backup(1,
                     1,
                     tempdir.path,
                     restore_dir.path,
                     extra_options=b'-r 10000')
        assert CompareRecursive(self.acl_test1_rpath,
                                restore_dir,
                                compare_acls=1)

        restore_dir.delete()
        rdiff_backup(1,
                     1,
                     tempdir.path,
                     restore_dir.path,
                     extra_options=b'-r now')
        assert CompareRecursive(self.acl_test2_rpath,
                                restore_dir,
                                compare_acls=1)

    def test_acl_mapping(self):
        """Test mapping ACL names"""

        def make_dir(rootrp):
            if rootrp.lstat():
                rootrp.delete()
            rootrp.mkdir()
            rp = rootrp.append('a1')
            rp.touch()
            acl = AccessControlLists(('a1', ), """user::rwx
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

        def write_mapping_file(rootrp):
            map_rp = rootrp.append('mapping_file')
            map_rp.write_string("root:{1}\n{0}:bin\nbin:root".format(
                self.current_user, self.current_group))
            return map_rp

        def get_perms_of_user(acl, user):
            """Return the permissions of ACL_USER in acl, or None"""
            for typechar, owner_pair, perms in acl.entry_list:
                if typechar == "u" and owner_pair[1] == user:
                    return perms
            return None

        self.make_temp_out_dirs()
        rootrp = rpath.RPath(Globals.local_connection,
                             os.path.join(abs_test_dir, b'acl_map_test'))
        make_dir(rootrp)
        map_rp = write_mapping_file(rootrp)

        rdiff_backup(1,
                     1,
                     rootrp.path,
                     tempdir.path,
                     extra_options=b"--user-mapping-file %b" % (map_rp.path, ))

        out_rp = tempdir.append('a1')
        assert out_rp.isreg()
        out_acl = tempdir.append('a1').get_acl()
        assert get_perms_of_user(out_acl, 'root') == 4
        assert get_perms_of_user(out_acl, self.current_user) == 7
        assert get_perms_of_user(out_acl, 'bin') == 0

    def test_acl_dropping(self):
        """Test dropping of ACL names"""
        self.make_temp_out_dirs()
        rp = tempdir.append('a1')
        rp.touch()
        """ben uses a dvorak keyboard, and these sequences are
        analogous to asdfsjkd for a qwerty user... these
        users and groups are not expected to exist. -dean"""
        acl = AccessControlLists(('a1', ), """user::rwx
user:aoensutheu:r--
group::r-x
group:aeuai:r-x
group:enutohnh:-w-
other::---""")
        rp.write_acl(acl)
        rp2 = tempdir.append('a1')
        acl2 = AccessControlLists(('a1', ))
        acl2.read_from_rp(rp2)
        assert acl2.is_basic()
        Globals.never_drop_acls = 1
        try:
            rp.write_acl(acl)
        except SystemExit:
            pass
        else:
            assert 0, "Above should have exited with fatal error"
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
        assert incdir.isdir(), incdir
        assert not incdir.listdir(), incdir.listdir()


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
