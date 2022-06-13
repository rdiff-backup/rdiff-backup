"""
Test the handling of hardlinks with api version >= 201
"""
import os
import unittest

import commontest as comtst
import fileset


class LocationMapHardlinksTest(unittest.TestCase):
    """
    Test that rdiff-backup properly handles hardlinks
    """

    def setUp(self):
        self.base_dir = os.path.join(comtst.abs_test_dir,
                                     b"location_map_hardlinks")
        self.from1_struct = {
            "from1": {"subs": {
                "hardlink1": {"content": "initial"},
                "hardlink2": {"link": "hardlink1"},
                "hardlink3": {"link": "hardlink1"},
            }}
        }
        self.from1_path = os.path.join(self.base_dir, b"from1")
        fileset.create_fileset(self.base_dir, self.from1_struct)
        fileset.remove_fileset(self.base_dir, {"bak": {"type": "dir"}})
        fileset.remove_fileset(self.base_dir, {"to1": {"type": "dir"}})
        self.bak_path = os.path.join(self.base_dir, b"bak")
        self.to1_path = os.path.join(self.base_dir, b"to1")
        self.success = False

    def test_location_map_hardlinks_rotate(self):
        """
        verify that hardlinked files can be rotated, see issue #272
        i.e. first one removed and new one added.
        """
        # backup a 1st time
        self.assertEqual(comtst.rdiff_backup_action(
            True, True, self.from1_path, self.bak_path,
            ("--api-version", "201", "--current-time", "10000"),
            b"backup", ()), 0)

        # kind of rotate the hard linked file
        os.remove(os.path.join(self.from1_path, b'hardlink1'))
        os.link(os.path.join(self.from1_path, b'hardlink3'),
                os.path.join(self.from1_path, b'hardlink4'))

        # backup a 2nd time
        self.assertEqual(comtst.rdiff_backup_action(
            True, True, self.from1_path, self.bak_path,
            ("--api-version", "201", "--current-time", "20000"),
            b"backup", ()), 0)

        # verify that the files still have the same inode in the repo
        self.assertEqual(
            os.lstat(os.path.join(self.bak_path, b'hardlink2')).st_ino,
            os.lstat(os.path.join(self.bak_path, b'hardlink3')).st_ino)
        self.assertEqual(
            os.lstat(os.path.join(self.bak_path, b'hardlink3')).st_ino,
            os.lstat(os.path.join(self.bak_path, b'hardlink4')).st_ino)

        # restore the hardlinked files
        self.assertEqual(comtst.rdiff_backup_action(
            True, True, self.bak_path, self.to1_path,
            ("--api-version", "201"), b"restore", ()), 0)

        # verify that the files have been properly restored with same inodes
        self.assertEqual(
            os.lstat(os.path.join(self.to1_path, b'hardlink2')).st_ino,
            os.lstat(os.path.join(self.to1_path, b'hardlink3')).st_ino)
        self.assertEqual(
            os.lstat(os.path.join(self.to1_path, b'hardlink3')).st_ino,
            os.lstat(os.path.join(self.to1_path, b'hardlink4')).st_ino)

        # all tests were successful
        self.success = True

    def tearDown(self):
        # we clean-up only if the test was successful
        if self.success:
            fileset.remove_fileset(self.base_dir, self.from1_struct)
            fileset.remove_fileset(self.base_dir, {"bak": {"type": "dir"}})
            fileset.remove_fileset(self.base_dir, {"to1": {"type": "dir"}})


if __name__ == "__main__":
    unittest.main()
