import unittest
import os
import time
from commontest import abs_test_dir, Myrm
from rdiff_backup import Globals, rpath, fs_abilities


class FSAbilitiesTest(unittest.TestCase):
    """Test testing of file system abilities

    Some of these tests assume that the actual file system tested has
    the given abilities.  If the file system this is run on differs
    from the original test system, this test may/should fail. Change
    the expected values below.

    """
    # Describes standard linux file system without acls/eas
    dir_to_test = abs_test_dir
    eas = acls = 1
    chars_to_quote = ""
    extended_filenames = 1
    case_sensitive = 1
    ownership = (os.getuid() == 0)
    hardlinks = fsync_dirs = 1
    dir_inc_perms = 1
    resource_forks = 0
    carbonfile = 0
    high_perms = 1

    # Describes MS-Windows style file system
    # dir_to_test = "/mnt/fat"
    # eas = acls = 0
    # extended_filenames = 0
    # chars_to_quote = "^a-z0-9_ -"
    # ownership = hardlinks = 0
    # fsync_dirs = 1
    # dir_inc_perms = 0
    # resource_forks = 0
    # carbonfile = 0

    # A case insensitive directory (FIXME must currently be created by root)
    # mkdir build/testfiles/fs_insensitive
    # dd if=/dev/zero of=build/testfiles/fs_fatfile.dd bs=512 count=1024
    # mkfs.fat build/testfiles/fs_fatfile.dd
    # sudo mount -o loop,uid=$(id -u) build/testfiles/fs_fatfile.dd build/testfiles/fs_insensitive
    # touch build/testfiles/fs_fatfile.dd build/testfiles/fs_insensitive/some_File

    case_insensitive_path = os.path.join(abs_test_dir, b'fs_insensitive')

    def testReadOnly(self):
        """Test basic querying read only"""
        base_dir = rpath.RPath(Globals.local_connection, self.dir_to_test)
        fsa = fs_abilities.FSAbilities('read-only', base_dir, read_only=True)
        print(fsa)
        self.assertEqual(fsa.read_only, 1)
        self.assertEqual(fsa.eas, self.eas)
        self.assertEqual(fsa.acls, self.acls)
        self.assertEqual(fsa.resource_forks, self.resource_forks)
        self.assertEqual(fsa.carbonfile, self.carbonfile)
        self.assertEqual(fsa.case_sensitive, self.case_sensitive)

    def testReadWrite(self):
        """Test basic querying read/write"""
        base_dir = rpath.RPath(Globals.local_connection, self.dir_to_test)
        new_dir = base_dir.append("fs_abilitiestest")
        if new_dir.lstat():
            Myrm(new_dir.path)
        new_dir.setdata()
        new_dir.mkdir()
        t = time.time()
        fsa = fs_abilities.FSAbilities('read/write', new_dir)
        print("Time elapsed = ", time.time() - t)
        print(fsa)
        self.assertEqual(fsa.read_only, 0)
        self.assertEqual(fsa.eas, self.eas)
        self.assertEqual(fsa.acls, self.acls)
        self.assertEqual(fsa.ownership, self.ownership)
        self.assertEqual(fsa.hardlinks, self.hardlinks)
        self.assertEqual(fsa.fsync_dirs, self.fsync_dirs)
        self.assertEqual(fsa.dir_inc_perms, self.dir_inc_perms)
        self.assertEqual(fsa.resource_forks, self.resource_forks)
        self.assertEqual(fsa.carbonfile, self.carbonfile)
        self.assertEqual(fsa.high_perms, self.high_perms)
        self.assertEqual(fsa.extended_filenames, self.extended_filenames)

        new_dir.delete()

    @unittest.skipUnless(os.path.isdir(case_insensitive_path),
                         "Case insensitive directory %s does not exist" %
                         case_insensitive_path)
    def test_case_sensitive(self):
        """Test a read-only case-INsensitive directory"""
        rp = rpath.RPath(Globals.local_connection, self.case_insensitive_path)
        fsa = fs_abilities.FSAbilities('read-only', rp, read_only=True)
        fsa.set_case_sensitive_readonly(rp)
        self.assertEqual(fsa.case_sensitive, 0)


if __name__ == "__main__":
    unittest.main()
