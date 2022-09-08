"""
Test the basic backup and restore actions with api version >= 201
"""
import os
import unittest

import commontest as comtst
import fileset


class ActionBackupRestoreTest(unittest.TestCase):
    """
    Test that rdiff-backup really restores what has been backed-up
    """

    def setUp(self):
        self.base_dir = os.path.join(comtst.abs_test_dir,
                                     b"action_backuprestore")
        self.from1_struct = {
            "from1": {"subs": {
                "fileA": {"content": "initial"},
                "fileB": {},
                "dirOld": {"type": "dir"},
                "itemX": {"type": "dir"},
                "itemY": {"type": "file"},
                "longdirnam" * 25: {"type": "dir"},
                "longfilnam" * 25: {"content": "not so long content"},
                "somehardlink": {"link": "fileA"},
            }}
        }
        self.from1_path = os.path.join(self.base_dir, b"from1")
        self.from2_struct = {
            "from2": {"subs": {
                "fileA": {"content": "modified"},
                "fileC": {},
                "dirNew": {"type": "dir"},
                "itemX": {"type": "file"},
                "itemY": {"type": "dir"},
                "longdirnam" * 25: {"type": "dir"},
                "longfilnam" * 25: {"content": "differently long"},
                "somehardlink": {"link": "fileA"},
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

    def test_action_backuprestore(self):
        """test the "backup" and "restore" actions"""
        # we backup twice to the same backup repository at different times
        self.assertEqual(comtst.rdiff_backup_action(
            False, False, self.from1_path, self.bak_path,
            ("--api-version", "201", "--current-time", "10000"),
            b"backup", ()), 0)
        self.assertEqual(comtst.rdiff_backup_action(
            False, True, self.from2_path, self.bak_path,
            ("--api-version", "201", "--current-time", "20000"),
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

    def test_action_backuprestore_quoted(self):
        """
        test the backup and restore actions with quoted repository
        """
        # we backup using a specific chars-to-quote
        self.assertEqual(comtst.rdiff_backup_action(
            False, False, self.from1_path, self.bak_path,
            ("--api-version", "201", "--current-time", "10000",
             "--chars-to-quote", "A"),
            b"backup", ()), 0)

        # then we restore once the full repo, once a sub-path
        self.assertEqual(comtst.rdiff_backup_action(
            True, False, os.path.join(self.bak_path, b"itemX"), self.to1_path,
            ("--api-version", "201"),
            b"restore", ()), 0)
        self.assertEqual(comtst.rdiff_backup_action(
            True, True, self.bak_path, self.to2_path,
            ("--api-version", "201"),
            b"restore", ()), 0)

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
