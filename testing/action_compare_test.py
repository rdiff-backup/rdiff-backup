"""
Test the compare action with api version >= 201
"""
import os
import unittest

import commontest as comtst
import fileset

from rdiff_backup import Globals


class ActionCompareTest(unittest.TestCase):
    """
    Test that rdiff-backup compares properly
    """

    def setUp(self):
        self.base_dir = os.path.join(comtst.abs_test_dir, b"action_compare")
        self.from1_struct = {
            "from1": {"subs": {
                "fileChanged": {"content": "initial"},
                "fileOld": {},
                "fileUnchanged": {"content": "unchanged"},
            }}
        }
        self.from1_path = os.path.join(self.base_dir, b"from1")
        self.from2_struct = {
            "from2": {"subs": {
                "fileChanged": {"content": "modified"},
                "fileNew": {},
                "fileUnchanged": {"content": "unchanged"},
            }}
        }
        self.from2_path = os.path.join(self.base_dir, b"from2")
        self.from3_struct = {
            "from3": {"subs": {
                "fileChanged": {"content": "samesize"},
                "fileNew": {},
                "fileUnchanged": {"content": "unchanged"},
            }}
        }
        self.from3_path = os.path.join(self.base_dir, b"from3")
        fileset.create_fileset(self.base_dir, self.from1_struct)
        fileset.create_fileset(self.base_dir, self.from2_struct)
        fileset.create_fileset(self.base_dir, self.from3_struct)
        fileset.remove_fileset(self.base_dir, {"bak": {"type": "dir"}})
        self.bak_path = os.path.join(self.base_dir, b"bak")
        self.success = False
        # we backup to the same backup repository at different times
        comtst.rdiff_backup_action(
            True, True, self.from1_path, self.bak_path,
            ("--api-version", "201", "--current-time", "10000"),
            b"backup", ())
        comtst.rdiff_backup_action(
            True, True, self.from2_path, self.bak_path,
            ("--api-version", "201", "--current-time", "20000"),
            b"backup", ())

    def test_action_compare(self):
        """test different ways of comparing directories"""
        # first try without date
        self.assertEqual(comtst.rdiff_backup_action(
            False, True, self.from1_path, self.bak_path,
            ("--api-version", "201"),
            b"compare", ("--method", "meta")), Globals.RET_CODE_FILE_WARN)
        self.assertEqual(comtst.rdiff_backup_action(
            True, False, self.from2_path, self.bak_path,
            ("--api-version", "201"),
            b"compare", ("--method", "meta")), 0)
        # Note that the meta method doesn't recognize the differences
        # between from2 and from3 because only the hash differentiates them

        # then with date
        self.assertEqual(comtst.rdiff_backup_action(
            False, True, self.from1_path, self.bak_path,
            ("--api-version", "201"),
            b"compare", ("--at", "10000")), 0)
        self.assertEqual(comtst.rdiff_backup_action(
            True, False, self.from2_path, self.bak_path,
            ("--api-version", "201"),
            b"compare", ("--at", "15000")), Globals.RET_CODE_FILE_WARN)

        # then try to compare with hashes
        self.assertEqual(comtst.rdiff_backup_action(
            False, True, self.from1_path, self.bak_path,
            ("--api-version", "201"),
            b"compare", ("--method", "hash")), Globals.RET_CODE_FILE_WARN)
        self.assertEqual(comtst.rdiff_backup_action(
            True, False, self.from2_path, self.bak_path,
            ("--api-version", "201"),
            b"compare", ("--at", "now", "--method", "hash")), 0)
        # reduce verbosity to avoid file system quoting notes under Windows
        self.assertEqual(comtst.rdiff_backup_action(
            False, False, self.from3_path, self.bak_path,
            ("--api-version", "201", "--parsable", "-v2"),
            b"compare", ("--method", "hash"), return_stdout=True),
            b"""---
- path: fileChanged
  reason: metadata the same, data changed
...

""")

        # then try to compare full
        self.assertEqual(comtst.rdiff_backup_action(
            False, True, self.from1_path, self.bak_path,
            ("--api-version", "201"),
            b"compare", ("--method", "full")), Globals.RET_CODE_FILE_WARN)
        self.assertEqual(comtst.rdiff_backup_action(
            True, False, self.from1_path, self.bak_path,
            ("--api-version", "201"),
            b"compare", ("--at", "1B", "--method", "full")), 0)
        # reduce verbosity to avoid file system quoting notes under Windows
        self.assertEqual(comtst.rdiff_backup_action(
            True, True, self.from3_path, self.bak_path,
            ("--api-version", "201", "--parsable", "-v2"),
            b"compare", ("--method", "full"), return_stdout=True),
            b"""---
- path: fileChanged
  reason: metadata the same, data changed
...

""")

        # all tests were successful
        self.success = True

    def tearDown(self):
        # we clean-up only if the test was successful
        if self.success:
            fileset.remove_fileset(self.base_dir, self.from1_struct)
            fileset.remove_fileset(self.base_dir, self.from2_struct)
            fileset.remove_fileset(self.base_dir, self.from3_struct)
            fileset.remove_fileset(self.base_dir, {"bak": {"type": "dir"}})


if __name__ == "__main__":
    unittest.main()
