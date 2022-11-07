"""
Test the remove action with api version >= 201
"""
import os
import unittest

import commontest as comtst
import fileset
from rdiff_backup import Globals


class ActionRemoveTest(unittest.TestCase):
    """
    Test that rdiff-backup properly removes increments
    """

    def setUp(self):
        self.base_dir = os.path.join(comtst.abs_test_dir, b"action_remove")
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
                "fileChanged": {"content": "modified again"},
                "fileNew": {},
                "fileUnchanged": {"content": "unchanged"},
            }}
        }
        self.from3_path = os.path.join(self.base_dir, b"from3")
        self.from4_struct = {
            "from4": {"subs": {
                "fileChanged": {"content": "modified again"},
                "fileEvenNewer": {},
                "fileUnchanged": {"content": "unchanged"},
            }}
        }
        self.from4_path = os.path.join(self.base_dir, b"from4")
        fileset.create_fileset(self.base_dir, self.from1_struct)
        fileset.create_fileset(self.base_dir, self.from2_struct)
        fileset.create_fileset(self.base_dir, self.from3_struct)
        fileset.create_fileset(self.base_dir, self.from4_struct)
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
        comtst.rdiff_backup_action(
            True, True, self.from3_path, self.bak_path,
            ("--api-version", "201", "--current-time", "30000"),
            b"backup", ())
        comtst.rdiff_backup_action(
            True, True, self.from4_path, self.bak_path,
            ("--api-version", "201", "--current-time", "40000"),
            b"backup", ())

    def test_action_removeincsolderthan(self):
        """test different ways of removing increments"""
        # removing multiple increments fails without --force
        self.assertNotEqual(comtst.rdiff_backup_action(
            False, None, self.bak_path, None,
            ("--api-version", "201"),
            b"remove", ("increments", "--older-than", "1B")),
            Globals.RET_CODE_OK)
        self.assertEqual(comtst.rdiff_backup_action(
            False, None, self.bak_path, None,
            ("--api-version", "201", "--force"),  # now forcing!
            b"remove", ("increments", "--older-than", "1B")),
            Globals.RET_CODE_OK)
        # then check that only one increment and mirror remain
        self.assertRegex(comtst.rdiff_backup_action(
            False, None, self.bak_path, None,
            ("--api-version", "201", "--parsable"),
            b"list", ("increments", ), return_stdout=True),
            b"""---
- base: increments.1970-01-0[12]T[0-9][0-9][:-][25]0[:-]00.*.dir
  time: 30000
  type: directory
- base: bak
  time: 40000
  type: directory
...

""")

        # check that nothing happens if no increment is old enough issue #616
        self.assertEqual(comtst.rdiff_backup_action(
            False, None, self.bak_path, None,
            ("--api-version", "201", "--force"),
            b"remove", ("increments", "--older-than", "30000")),
            Globals.RET_CODE_WARN)
        self.assertRegex(comtst.rdiff_backup_action(
            False, None, self.bak_path, None,
            ("--api-version", "201", "--parsable"),
            b"list", ("increments", ), return_stdout=True),
            b"""---
- base: increments.1970-01-0[12]T[0-9][0-9][:-][25]0[:-]00.*.dir
  time: 30000
  type: directory
- base: bak
  time: 40000
  type: directory
...

""")
        # then remove the last increment
        self.assertEqual(comtst.rdiff_backup_action(
            False, None, self.bak_path, None,
            ("--api-version", "201", ),
            b"remove", ("increments", "--older-than", "30001")),
            Globals.RET_CODE_OK)
        # and check that only the mirror is left
        self.assertEqual(comtst.rdiff_backup_action(
            False, None, self.bak_path, None,
            ("--api-version", "201", "--parsable"),
            b"list", ("increments", ), return_stdout=True),
            b"""---
- base: bak
  time: 40000
  type: directory
...

""")
        # then try to remove the mirror
        self.assertEqual(comtst.rdiff_backup_action(
            False, None, self.bak_path, None,
            ("--api-version", "201", ),
            b"remove", ("increments", "--older-than", "now")),
            Globals.RET_CODE_WARN)
        # and check that it is still there
        self.assertEqual(comtst.rdiff_backup_action(
            False, None, self.bak_path, None,
            ("--api-version", "201", "--parsable"),
            b"list", ("increments", ), return_stdout=True),
            b"""---
- base: bak
  time: 40000
  type: directory
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
            fileset.remove_fileset(self.base_dir, self.from4_struct)
            fileset.remove_fileset(self.base_dir, {"bak": {"type": "dir"}})


if __name__ == "__main__":
    unittest.main()
