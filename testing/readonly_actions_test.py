"""
Test the ability to regress/remove read-only paths with api version >= 201
"""
import os
import unittest

import commontest as comtst
import fileset


class ActionReadOnlyTest(unittest.TestCase):
    """
    Test that rdiff-backup can properly handle read-only paths
    """

    def setUp(self):
        self.base_dir = os.path.join(comtst.abs_test_dir,
                                     b"readonly_actions")
        self.from1_struct = {
            "from1": {"contents": {
                "dirA": {"contents": {"fileA": {"content": "initial"}}},
                "fileB": {"content": "something"}
            }}}
        self.from1_path = os.path.join(self.base_dir, b"from1")
        self.from2_struct = {
            "from2": {"contents": {
                "dirA": {"contents": {"fileA": {"content": "afterwards"}}},
                "fileB": {"content": "now else"}
            }}}
        self.from2_path = os.path.join(self.base_dir, b"from2")
        fileset.create_fileset(self.base_dir, self.from1_struct)
        fileset.create_fileset(self.base_dir, self.from2_struct)
        fileset.remove_fileset(self.base_dir, {"bak": {"type": "dir"}})
        self.bak_path = os.path.join(self.base_dir, b"bak")

        # we backup twice to the same backup repository at different times
        self.assertEqual(comtst.rdiff_backup_action(
            False, False, self.from1_path, self.bak_path,
            ("--api-version", "201", "--current-time", "10000"),
            b"backup", ()), 0)
        self.assertEqual(comtst.rdiff_backup_action(
            False, True, self.from2_path, self.bak_path,
            ("--api-version", "201", "--current-time", "20000"),
            b"backup", ()), 0)

        self.success = False

    def test_readonly_regress(self):
        """test the "regress" action on a read-only repository"""

        # then we regress forcefully
        self.assertEqual(comtst.rdiff_backup_action(
            False, None, self.bak_path, None,
            ("--api-version", "201", "--force"),
            b"regress", ()), 0)

        # all tests were successful
        self.success = True

    def test_readonly_remove(self):
        """test the "remove" action on a read-only repository"""

        # then we regress forcefully
        self.assertEqual(comtst.rdiff_backup_action(
            True, None, self.bak_path, None,
            ("--api-version", "201", "--force"),
            b"remove", ("increments", "--older-than", "0B")), 0)

        # all tests were successful
        self.success = True

    def tearDown(self):
        # we clean-up only if the test was successful
        if self.success:
            fileset.remove_fileset(self.base_dir, self.from1_struct)
            fileset.remove_fileset(self.base_dir, self.from2_struct)
            fileset.remove_fileset(self.base_dir, {"bak": {"type": "dir"}})


if __name__ == "__main__":
    unittest.main()
