"""
Test the quoting of characters in filenames with api version >= 201
"""
import os
import unittest

import commontest as comtst
import fileset


class LocationMapFilenamesTest(unittest.TestCase):
    """
    Test that rdiff-backup really restores what has been backed-up with quotes
    """

    def setUp(self):
        self.base_dir = os.path.join(comtst.abs_test_dir,
                                     b"location_map_filenames")
        self.from1_struct = {
            "from1": {"subs": {
                "fileABC": {"content": "initial"},
                "fileXYZ": {},
                "dirAbCXyZ": {"type": "dir"},
                "itemX": {"type": "dir"},
                "itemY": {"type": "file"},
                "longDiRnAm" * 25: {"type": "dir"},
                "longFiLnAm" * 25: {"content": "not so long content"},
            }}
        }
        self.from1_path = os.path.join(self.base_dir, b"from1")
        self.from2_struct = {
            "from2": {"subs": {
                "fileABC": {"content": "modified"},
                "fileXYZ": {},
                "diraBcXyZ": {"type": "dir"},
                "itemX": {"type": "file"},
                "itemY": {"type": "dir"},
                "longDiRnAm" * 25: {"type": "dir"},
                "longFiLnAm" * 25: {"content": "differently long"},
            }}
        }
        self.from2_path = os.path.join(self.base_dir, b"from2")
        fileset.create_fileset(self.base_dir, self.from1_struct)
        fileset.create_fileset(self.base_dir, self.from2_struct)
        fileset.remove_fileset(self.base_dir, {"bak": {"type": "dir"}})
        fileset.remove_fileset(self.base_dir, {"to1": {"type": "dir"}})
        fileset.remove_fileset(self.base_dir, {"to2": {"type": "dir"}})
        self.bak_path = os.path.join(self.base_dir, b"bak")
        self.to1_path = os.path.join(self.base_dir, b"to1")
        self.to2_path = os.path.join(self.base_dir, b"to2")
        self.success = False

    def test_location_map_filenames(self):
        """
        test the "backup" and "restore" actions with quoted filenames
        """
        # we backup twice to the same backup repository at different times
        self.assertEqual(comtst.rdiff_backup_action(
            False, False, self.from1_path, self.bak_path,
            ("--api-version", "201", "--current-time", "10000",
                "--chars-to-quote", "A-Z"),
            b"backup", ()), 0)
        self.assertEqual(comtst.rdiff_backup_action(
            False, True, self.from2_path, self.bak_path,
            ("--api-version", "201", "--current-time", "20000",
                "--chars-to-quote", "A-Z"),
            b"backup", ()), 0)

        # then we restore the increment and the last mirror to two directories
        self.assertEqual(comtst.rdiff_backup_action(
            True, False, self.bak_path, self.to1_path,
            ("--api-version", "201"),
            b"restore", ("--at", "1B")), 0)
        self.assertEqual(comtst.rdiff_backup_action(
            True, True, self.bak_path, self.to2_path,
            ("--api-version", "201"),
            b"restore", ()), 0)

        self.assertFalse(fileset.compare_paths(self.from1_path, self.to1_path))
        self.assertFalse(fileset.compare_paths(self.from2_path, self.to2_path))

        # all tests were successful
        self.success = True

    def test_location_map_filenames_change_quotes(self):
        """
        test the "backup" and "restore" actions with quoted filenames
        while changing the quoted characters, which isn't supported
        """
        # we backup twice to the same backup repository at different times
        self.assertEqual(comtst.rdiff_backup_action(
            False, False, self.from1_path, self.bak_path,
            ("--api-version", "201", "--current-time", "10000",
                "--chars-to-quote", "A-P"),
            b"backup", ()), 0)
        # we try the 2nd time to change the chars-to-quote, which fails
        self.assertNotEqual(comtst.rdiff_backup_action(
            False, True, self.from2_path, self.bak_path,
            ("--api-version", "201", "--current-time", "15000",
                "--chars-to-quote", "H-Z"),
            b"backup", ()), 0)
        self.assertNotEqual(comtst.rdiff_backup_action(
            False, True, self.from2_path, self.bak_path,
            ("--api-version", "201", "--current-time", "20000",
                "--chars-to-quote", "H-Z", "--force"),
            b"backup", ()), 0)

        # then we restore the last mirror to a directory without issue
        self.assertEqual(comtst.rdiff_backup_action(
            True, True, self.bak_path, self.to1_path,
            ("--api-version", "201"),
            b"restore", ()), 0)

        self.assertFalse(fileset.compare_paths(self.from1_path, self.to1_path))

        # all tests were successful
        self.success = True

    def tearDown(self):
        # we clean-up only if the test was successful
        if self.success:
            fileset.remove_fileset(self.base_dir, self.from1_struct)
            fileset.remove_fileset(self.base_dir, self.from2_struct)
            fileset.remove_fileset(self.base_dir, {"bak": {"type": "dir"}})
            fileset.remove_fileset(self.base_dir, {"to1": {"type": "dir"}})
            fileset.remove_fileset(self.base_dir, {"to2": {"type": "dir"}})


if __name__ == "__main__":
    unittest.main()
