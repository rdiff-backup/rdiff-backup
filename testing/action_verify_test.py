"""
Test the verify action with api version >= 201
"""
import os
import unittest

import commontest as comtst
import fileset


class ActionVerifyTest(unittest.TestCase):
    """
    Test that rdiff-backup properly verifies repositories
    """

    def setUp(self):
        self.base_dir = os.path.join(comtst.abs_test_dir, b"action_verify")
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
        fileset.create_fileset(self.base_dir, self.from1_struct)
        fileset.create_fileset(self.base_dir, self.from2_struct)
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

    def test_action_verify(self):
        """test different ways of verifying"""
        # removing multiple increments fails without --force
        self.assertEqual(comtst.rdiff_backup_action(
            False, None, self.bak_path, None,
            ("--api-version", "201"),
            b"verify", ()), 0)
        self.assertEqual(comtst.rdiff_backup_action(
            True, None, self.bak_path, None,
            ("--api-version", "201", "--force"),  # now forcing!
            b"verify", ("--at", "1B")), 0)

        # corrupt the backup repository
        with open(os.path.join(self.bak_path, b"fileNew"), "w") as fd:
            fd.write("corrupt data")
        self.assertNotEqual(comtst.rdiff_backup_action(
            False, None, self.bak_path, None,
            ("--api-version", "201"),
            b"verify", ("--at", "now")), 0)

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
