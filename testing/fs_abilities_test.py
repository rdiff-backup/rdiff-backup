"""
Test file system abilities gathering
"""

import os
import time
import unittest

import commontest as comtst

from rdiff_backup import Globals, rpath
from rdiffbackup.locations import fs_abilities

# we don't need all these imports but we use them to decide which type will
# have the corresponding attributes
try:
    import posix1e  # noqa F401

    acl_posix_type = bool
except ImportError:
    acl_posix_type = type(None)

try:
    import xattr.pyxattr_compat as xattr  # noqa F401

    ea_type = bool
except ImportError:
    try:
        import xattr  # noqa F401

        ea_type = bool
    except ImportError:
        ea_type = type(None)

try:
    import win32security  # noqa F401
    import pywintypes  # noqa F401

    acl_win_type = bool
except ImportError:
    acl_win_type = type(None)

try:
    import Carbon.File  # noqa F401

    carbon_type = bool
except (ImportError, AttributeError):
    carbon_type = type(None)

if os.name == "nt":  # because we ignore hardlinks under Windows
    hardlinks_type = type(None)
else:
    hardlinks_type = bool


TEST_BASE_DIR = comtst.get_test_base_dir(__file__)


class FSAbilitiesTest(unittest.TestCase):
    """
    Test testing of file system abilities

    Some of these tests assume that the actual file system tested has
    the given abilities.  If the file system this is run on differs
    from the original test system, this test may/should fail. Change
    the expected values below.
    """

    # A case insensitive directory (FIXME must currently be created by root)
    # mkdir build/testfiles/fs_insensitive
    # dd if=/dev/zero of=build/testfiles/fs_fatfile.dd bs=512 count=1024
    # mkfs.fat build/testfiles/fs_fatfile.dd
    # sudo mount -o loop,uid=$(id -u) build/testfiles/fs_fatfile.dd build/testfiles/fs_insensitive
    # touch build/testfiles/fs_fatfile.dd build/testfiles/fs_insensitive/some_File

    case_insensitive_path = os.path.join(TEST_BASE_DIR, b"fs_insensitive")

    def setUp(self):
        comtst.reset_connections()

    def testReadOnly(self):
        """Test basic querying read only"""
        base_dir = rpath.RPath(specifics.local_connection, TEST_BASE_DIR)
        t = time.time()
        fsa = fs_abilities.detect_fs_abilities(base_dir, writable=False)
        print("Time elapsed = ", time.time() - t)
        print(fsa)
        self.assertFalse(fsa.writable)
        self.assertIsInstance(fsa.eas, ea_type)
        self.assertIsInstance(fsa.acls, acl_posix_type)
        self.assertIsInstance(fsa.win_acls, acl_win_type)
        self.assertIsInstance(fsa.resource_forks, bool)  # doesn't require module
        self.assertIsInstance(fsa.carbonfile, carbon_type)
        self.assertIsInstance(fsa.case_sensitive, bool)

    def testReadWrite(self):
        """Test basic querying read/write"""
        base_dir = rpath.RPath(specifics.local_connection, TEST_BASE_DIR)
        new_dir = base_dir.append("fs_abilitiestest")
        if new_dir.lstat():
            comtst.remove_dir(new_dir.path)
        new_dir.setdata()
        new_dir.mkdir()
        t = time.time()
        fsa = fs_abilities.detect_fs_abilities(new_dir)
        print("Time elapsed = ", time.time() - t)
        print(fsa)
        self.assertTrue(fsa.writable)
        self.assertIsInstance(fsa.ownership, bool)
        self.assertIsInstance(fsa.hardlinks, hardlinks_type)
        self.assertIsInstance(fsa.fsync_dirs, bool)
        self.assertIsInstance(fsa.dir_inc_perms, bool)
        self.assertIsInstance(fsa.high_perms, bool)
        self.assertIsInstance(fsa.extended_filenames, bool)
        self.assertIsInstance(fsa.eas, ea_type)
        self.assertIsInstance(fsa.acls, acl_posix_type)
        self.assertIsInstance(fsa.win_acls, acl_win_type)
        self.assertIsInstance(fsa.resource_forks, bool)  # doesn't require module
        self.assertIsInstance(fsa.carbonfile, carbon_type)
        self.assertIsInstance(fsa.case_sensitive, bool)

        new_dir.delete()

    @unittest.skipUnless(
        os.path.isdir(case_insensitive_path),
        "Case insensitive directory %s does not exist" % case_insensitive_path,
    )
    def test_case_sensitive(self):
        """Test a read-only case-INsensitive directory"""
        rp = rpath.RPath(specifics.local_connection, self.case_insensitive_path)
        fsa = fs_abilities.detect_fs_abilities(rp, writable=False)
        fsa._detect_case_sensitive_readonly(rp)
        self.assertEqual(fsa.case_sensitive, 0)


if __name__ == "__main__":
    unittest.main()
