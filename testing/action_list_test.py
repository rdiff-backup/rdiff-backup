"""
Test the list action with api version >= 201
"""

import os
import unittest

import commontest as comtst
import fileset

TEST_BASE_DIR = comtst.get_test_base_dir(__file__)


class ActionListTest(unittest.TestCase):
    """
    Test that rdiff-backup properly lists files and increments
    """

    def setUp(self):
        self.base_dir = os.path.join(TEST_BASE_DIR, b"action_list")
        self.from1_struct = {
            "from1": {
                "contents": {
                    "fileChanged": {"content": "initial"},
                    "fileOld": {},
                    "fileUnchanged": {"content": "unchanged"},
                }
            }
        }
        self.from1_path = os.path.join(self.base_dir, b"from1")
        self.from2_struct = {
            "from2": {
                "contents": {
                    "fileChanged": {"content": "modified"},
                    "fileNew": {},
                    "fileUnchanged": {"content": "unchanged"},
                }
            }
        }
        self.from2_path = os.path.join(self.base_dir, b"from2")
        fileset.create_fileset(self.base_dir, self.from1_struct)
        fileset.create_fileset(self.base_dir, self.from2_struct)
        fileset.remove_fileset(self.base_dir, {"bak": {"type": "dir"}})
        self.bak_path = os.path.join(self.base_dir, b"bak")
        self.success = False
        # we backup twice to the same backup repository at different times
        comtst.rdiff_backup_action(
            True,
            True,
            self.from1_path,
            self.bak_path,
            ("--api-version", "201", "--current-time", "111111"),
            b"backup",
            (),
        )
        comtst.rdiff_backup_action(
            True,
            True,
            self.from2_path,
            self.bak_path,
            ("--api-version", "201", "--current-time", "222222"),
            b"backup",
            (),
        )

    def test_action_listfilesattime(self):
        """test the list files at time action"""
        # we list the files at different times
        self.assertEqual(
            comtst.rdiff_backup_action(
                False,
                None,
                self.bak_path,
                None,
                ("--api-version", "201"),
                b"list",
                ("files",),
                return_stdout=True,
            ),
            b""".
fileChanged
fileNew
fileUnchanged
""",
        )
        self.assertEqual(
            comtst.rdiff_backup_action(
                True,
                None,
                self.bak_path,
                None,
                ("--api-version", "201"),
                b"list",
                ("files", "--at", "111111"),
                return_stdout=True,
            ),
            b""".
fileChanged
fileOld
fileUnchanged
""",
        )
        self.assertEqual(
            comtst.rdiff_backup_action(
                True,
                None,
                self.bak_path,
                None,
                ("--api-version", "201"),
                b"list",
                ("files", "--at", "15000"),
                return_stdout=True,
            ),
            b""".
fileChanged
fileOld
fileUnchanged
""",
        )
        self.assertEqual(
            comtst.rdiff_backup_action(
                True,
                None,
                self.bak_path,
                None,
                ("--api-version", "201"),
                b"list",
                ("files", "--at", "1B"),
                return_stdout=True,
            ),
            b""".
fileChanged
fileOld
fileUnchanged
""",
        )

        # all tests were successful
        self.success = True

    def test_action_listfileschangedsince(self):
        """test the list files at time action"""
        # we list the files at different times
        self.assertEqual(
            comtst.rdiff_backup_action(
                False,
                None,
                self.bak_path,
                None,
                ("--api-version", "201"),
                b"list",
                ("files", "--changed-since", "now"),
                return_stdout=True,
            ),
            b"""""",
        )
        self.assertEqual(
            comtst.rdiff_backup_action(
                True,
                None,
                self.bak_path,
                None,
                ("--api-version", "201"),
                b"list",
                ("files", "--changed-since", "111111"),
                return_stdout=True,
            ),
            b"""changed fileChanged
new     fileNew
deleted fileOld
""",
        )
        self.assertEqual(
            comtst.rdiff_backup_action(
                True,
                None,
                self.bak_path,
                None,
                ("--api-version", "201"),
                b"list",
                ("files", "--changed-since", "15000"),
                return_stdout=True,
            ),
            b"""changed fileChanged
new     fileNew
deleted fileOld
""",
        )
        self.assertEqual(
            comtst.rdiff_backup_action(
                True,
                None,
                self.bak_path,
                None,
                ("--api-version", "201"),
                b"list",
                ("files", "--changed-since", "1B"),
                return_stdout=True,
            ),
            b"""changed fileChanged
new     fileNew
deleted fileOld
""",
        )

        # all tests were successful
        self.success = True

    def test_action_listincrements(self):
        """test the list increments action, without and with size"""
        # we need to use a regex for different timezones
        self.assertRegex(
            comtst.rdiff_backup_action(
                False,
                None,
                self.bak_path,
                None,
                ("--api-version", "201", "--parsable"),
                b"list",
                ("increments",),
                return_stdout=True,
            ),
            b"""---
- base: increments.1970-01-0[12]T[0-9][0-9][:-][25]1[:-]51.*.dir
  time: 111111
  type: directory
- base: bak
  time: 222222
  type: directory
...

""",
        )
        # we need to use a regex for different filesystem types
        # especially directories can have any kind of size
        self.assertRegex(
            comtst.rdiff_backup_action(
                False,
                None,
                self.bak_path,
                None,
                ("--api-version", "201", "--parsable"),
                b"list",
                ("increments", "--size"),
                return_stdout=True,
            ),
            b"""---
- size: [0-9]+
  time: 111111
  total_size: [0-9]+
- size: [0-9]+
  time: 222222
  total_size: [0-9]+
...

""",
        )

        # all tests were successful
        self.success = True

    def test_action_listfiles_nonutf8(self):
        # Given a repository with non-utf8
        repo = os.path.join(comtst.old_test_dir, b"restoretest5")
        # When calling rdiff-backup list files
        output = (
            comtst.rdiff_backup_action(
                False,
                None,
                repo,
                None,
                (
                    "--api-version",
                    "201",
                ),
                b"list",
                ("files",),
                return_stdout=True,
            ),
        )
        output_lines = output[0].split(b"\n")
        # Then the output make use of surogate escape.
        self.assertIn(
            b"\xd8\xab\\xb1Wb\\xae\\xc5]\\x8a\\xbb\x15v*\\xf4\x0f!\\xf9>\\xe2Y\\x86\\xbb\\xab\\xdbp\\xb0\\x84\x13k\x1d\\xc2\\xf1\\xf5e\\xa5U\\x82\\x9aUV\\xa0\\xf4\\xdf4\\xba\\xfdX\x03\\x82\x07s\xce\x9e\\x8b\\xb34\x04\\x9f\x17 \\xf4\\x8f\\xa6\\xfa\\x97\\xab\xd8\xac\xda\x85\\xdcKvC\\xfa#\\x94\\x92\\x9e\xc9\xb7\\xc3_\x0f\\x84g\\x9aB\x11<=^\\xdbM\x13\\x96c\\x8b\\xa7|*\"\\'^$@#!(){}?+ ~` ",
            output_lines,
        )

    def tearDown(self):
        # we clean-up only if the test was successful
        if self.success:
            fileset.remove_fileset(self.base_dir, self.from1_struct)
            fileset.remove_fileset(self.base_dir, self.from2_struct)
            fileset.remove_fileset(self.base_dir, {"bak": {"type": "dir"}})


if __name__ == "__main__":
    unittest.main()
