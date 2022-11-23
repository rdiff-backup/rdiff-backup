"""
Test the list action with api version >= 201
"""
import os
import unittest

import commontest as comtst
import fileset


class ActionListTest(unittest.TestCase):
    """
    Test that rdiff-backup properly lists files and increments
    """

    def setUp(self):
        self.base_dir = os.path.join(comtst.abs_test_dir, b"action_list")
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
        # we backup twice to the same backup repository at different times
        comtst.rdiff_backup_action(
            True, True, self.from1_path, self.bak_path,
            ("--api-version", "201", "--current-time", "10000"),
            b"backup", ())
        comtst.rdiff_backup_action(
            True, True, self.from2_path, self.bak_path,
            ("--api-version", "201", "--current-time", "20000"),
            b"backup", ())

    def test_action_listfilesattime(self):
        """test the list files at time action"""
        # we list the files at different times
        self.assertEqual(comtst.rdiff_backup_action(
            False, None, self.bak_path, None,
            ("--api-version", "201"),
            b"list", ("files",), return_stdout=True),
            b""".
fileChanged
fileNew
fileUnchanged
""")
        self.assertEqual(comtst.rdiff_backup_action(
            True, None, self.bak_path, None,
            ("--api-version", "201"),
            b"list", ("files", "--at", "10000"), return_stdout=True),
            b""".
fileChanged
fileOld
fileUnchanged
""")
        self.assertEqual(comtst.rdiff_backup_action(
            True, None, self.bak_path, None,
            ("--api-version", "201"),
            b"list", ("files", "--at", "15000"), return_stdout=True),
            b""".
fileChanged
fileOld
fileUnchanged
""")
        self.assertEqual(comtst.rdiff_backup_action(
            True, None, self.bak_path, None,
            ("--api-version", "201"),
            b"list", ("files", "--at", "1B"), return_stdout=True),
            b""".
fileChanged
fileOld
fileUnchanged
""")

        # all tests were successful
        self.success = True

    def test_action_listfileschangedsince(self):
        """test the list files at time action"""
        # we list the files at different times
        self.assertEqual(comtst.rdiff_backup_action(
            False, None, self.bak_path, None,
            ("--api-version", "201"),
            b"list", ("files", "--changed-since", "now"), return_stdout=True),
            b"""""")
        self.assertEqual(comtst.rdiff_backup_action(
            True, None, self.bak_path, None,
            ("--api-version", "201"),
            b"list", ("files", "--changed-since", "10000"), return_stdout=True),
            b"""changed fileChanged
new     fileNew
deleted fileOld
""")
        self.assertEqual(comtst.rdiff_backup_action(
            True, None, self.bak_path, None,
            ("--api-version", "201"),
            b"list", ("files", "--changed-since", "15000"), return_stdout=True),
            b"""changed fileChanged
new     fileNew
deleted fileOld
""")
        self.assertEqual(comtst.rdiff_backup_action(
            True, None, self.bak_path, None,
            ("--api-version", "201"),
            b"list", ("files", "--changed-since", "1B"), return_stdout=True),
            b"""changed fileChanged
new     fileNew
deleted fileOld
""")

        # all tests were successful
        self.success = True

    def test_action_listincrements(self):
        """test the list increments action, without and with size"""
        # we need to use a regex for different timezones
        self.assertRegex(comtst.rdiff_backup_action(
            False, None, self.bak_path, None,
            ("--api-version", "201", "--parsable"),
            b"list", ("increments", ), return_stdout=True),
            b"""---
- base: increments.1970-01-0[12]T[0-9][0-9][:-][14]6[:-]40.*.dir
  time: 10000
  type: directory
- base: bak
  time: 20000
  type: directory
...

""")
        # we need to use a regex for different filesystem types
        # especially directories can have any kind of size
        self.assertRegex(comtst.rdiff_backup_action(
            False, None, self.bak_path, None,
            ("--api-version", "201", "--parsable"),
            b"list", ("increments", "--size"), return_stdout=True),
            b"""---
- size: [0-9]+
  time: 10000
  total_size: [0-9]+
- size: [0-9]+
  time: 20000
  total_size: [0-9]+
...

""")

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
