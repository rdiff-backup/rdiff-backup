"""
Test the remove action
"""

import os
import unittest

import commontest as comtst
import fileset

from rdiffbackup.singletons import consts

TEST_BASE_DIR = comtst.get_test_base_dir(__file__)


class ActionRemoveTest(unittest.TestCase):
    """
    Basis class to define one setUp method
    """

    base_dir = os.path.join(TEST_BASE_DIR, b"action_remove")

    def setUp(self):
        self.from1_struct = {
            "from1": {
                "contents": {
                    "fileChanged": {"content": "initial"},
                    "fileOld": {},
                    "fileUnchanged": {"content": "unchanged"},
                    "file": {"content": "whatever1"},
                    "file.d": {"contents": {"file": {}}},
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
                    "file": {"content": "whatever11"},
                    "file.d": {"contents": {"file": {}}},
                }
            }
        }
        self.from2_path = os.path.join(self.base_dir, b"from2")
        self.from3_struct = {
            "from3": {
                "contents": {
                    "fileChanged": {"content": "modified again"},
                    "fileNew": {},
                    "fileUnchanged": {"content": "unchanged"},
                    "file": {"content": "whatever111"},
                    "file.d": {"contents": {"file": {}}},
                }
            }
        }
        self.from3_path = os.path.join(self.base_dir, b"from3")
        self.from4_struct = {
            "from4": {
                "contents": {
                    "fileChanged": {"content": "modified again"},
                    "fileEvenNewer": {},
                    "fileUnchanged": {"content": "unchanged"},
                    "file": {"content": "whatever1111"},
                    "file.d": {"contents": {"file": {}}},
                }
            }
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
            True,
            True,
            self.from1_path,
            self.bak_path,
            ("--current-time", "10000"),
            b"backup",
            (),
        )
        comtst.rdiff_backup_action(
            True,
            True,
            self.from2_path,
            self.bak_path,
            ("--current-time", "20000"),
            b"backup",
            (),
        )
        comtst.rdiff_backup_action(
            True,
            True,
            self.from3_path,
            self.bak_path,
            ("--current-time", "30000"),
            b"backup",
            (),
        )
        comtst.rdiff_backup_action(
            True,
            True,
            self.from4_path,
            self.bak_path,
            ("--current-time", "40000"),
            b"backup",
            (),
        )

    def tearDown(self):
        # we clean-up only if the test was successful
        if self.success:
            fileset.remove_fileset(self.base_dir, self.from1_struct)
            fileset.remove_fileset(self.base_dir, self.from2_struct)
            fileset.remove_fileset(self.base_dir, self.from3_struct)
            fileset.remove_fileset(self.base_dir, self.from4_struct)
            fileset.remove_fileset(self.base_dir, {"bak": {"type": "dir"}})


class ActionRemoveIncsTest(ActionRemoveTest):
    """
    Test that rdiff-backup properly removes increments
    """

    base_dir = os.path.join(TEST_BASE_DIR, b"remove_incs")

    def test_action_removeincsolderthan(self):
        """test different ways of removing increments"""
        # removing multiple increments fails without --force
        self.assertNotEqual(
            comtst.rdiff_backup_action(
                False,
                None,
                self.bak_path,
                None,
                (),
                b"remove",
                ("increments", "--older-than", "1B"),
            ),
            consts.RET_CODE_OK,
        )
        # you can't remove a partial increment
        self.assertEqual(
            comtst.rdiff_backup_action(
                False,
                None,
                os.path.join(self.bak_path, b"whatever"),
                None,
                (),
                b"remove",
                ("increments",),
            ),
            consts.RET_CODE_ERR,
        )
        self.assertEqual(
            comtst.rdiff_backup_action(
                False,
                None,
                self.bak_path,
                None,
                ("--force",),  # now forcing!
                b"remove",
                ("increments", "--older-than", "1B"),
            ),
            consts.RET_CODE_OK,
        )
        # then check that only one increment and mirror remain
        self.assertRegex(
            comtst.rdiff_backup_action(
                False,
                None,
                self.bak_path,
                None,
                ("--parsable",),
                b"list",
                ("increments",),
                return_stdout=True,
            ),
            b"""---
- base: increments.1970-01-0[12]T[0-9][0-9][:-][25]0[:-]00.*.dir
  time: 30000
  type: directory
- base: bak
  time: 40000
  type: directory
...

""",
        )

        # check that nothing happens if no increment is old enough issue #616
        self.assertEqual(
            comtst.rdiff_backup_action(
                False,
                None,
                self.bak_path,
                None,
                ("--force",),
                b"remove",
                ("increments", "--older-than", "30000"),
            ),
            consts.RET_CODE_WARN,
        )
        self.assertRegex(
            comtst.rdiff_backup_action(
                False,
                None,
                self.bak_path,
                None,
                ("--parsable",),
                b"list",
                ("increments",),
                return_stdout=True,
            ),
            b"""---
- base: increments.1970-01-0[12]T[0-9][0-9][:-][25]0[:-]00.*.dir
  time: 30000
  type: directory
- base: bak
  time: 40000
  type: directory
...

""",
        )
        # then remove the last increment
        self.assertEqual(
            comtst.rdiff_backup_action(
                False,
                None,
                self.bak_path,
                None,
                (),
                b"remove",
                ("increments", "--older-than", "30001", "--size"),
            ),
            consts.RET_CODE_OK,
        )
        # and check that only the mirror is left
        self.assertEqual(
            comtst.rdiff_backup_action(
                False,
                None,
                self.bak_path,
                None,
                ("--parsable",),
                b"list",
                ("increments",),
                return_stdout=True,
            ),
            b"""---
- base: bak
  time: 40000
  type: directory
...

""",
        )
        # then try to remove the mirror
        self.assertEqual(
            comtst.rdiff_backup_action(
                False,
                None,
                self.bak_path,
                None,
                (),
                b"remove",
                ("increments", "--older-than", "now"),
            ),
            consts.RET_CODE_WARN,
        )
        # and check that it is still there
        self.assertEqual(
            comtst.rdiff_backup_action(
                False,
                None,
                self.bak_path,
                None,
                ("--parsable",),
                b"list",
                ("increments",),
                return_stdout=True,
            ),
            b"""---
- base: bak
  time: 40000
  type: directory
...

""",
        )

        # all tests were successful
        self.success = True


class ActionRemoveFileTest(ActionRemoveTest):
    """
    Test that rdiff-backup properly removes individual files
    """

    base_dir = os.path.join(TEST_BASE_DIR, b"remove_file")

    def test_action_removefile_allornothing(self):
        """test removing files never or always present"""
        self.assertEqual(
            comtst.rdiff_backup_action(
                False,
                None,
                os.path.join(self.bak_path, b"file-does-not-exist"),
                None,
                (),
                b"remove",
                ("file",),
            ),
            consts.RET_CODE_WARN,
        )
        # you can't remove the whole backup repository
        self.assertEqual(
            comtst.rdiff_backup_action(
                False,
                None,
                self.bak_path,
                None,
                (),
                b"remove",
                ("file",),
            ),
            consts.RET_CODE_ERR,
        )
        # you can't remove rdiff-backup-data
        self.assertEqual(
            comtst.rdiff_backup_action(
                False,
                None,
                os.path.join(self.bak_path, b"rdiff-backup-data", b"file.d"),
                None,
                (),
                b"remove",
                ("file",),
            ),
            consts.RET_CODE_ERR,
        )
        self.assertEqual(
            comtst.rdiff_backup_action(
                False,
                None,
                os.path.join(self.bak_path, b"file"),
                None,
                (),
                b"remove",
                ("file",),
            ),
            consts.RET_CODE_OK,
        )
        self.assertEqual(
            comtst.rdiff_backup_action(
                False,
                None,
                self.bak_path,
                None,
                (),
                b"list",
                ("files",),
                return_stdout=True,
            ),
            b""".
file.d
file.d/file
fileChanged
fileEvenNewer
fileUnchanged
""",
        )
        self.assertEqual(
            comtst.rdiff_backup_action(
                False,
                None,
                self.bak_path,
                None,
                (),
                b"list",
                ("files", "--at", "10000"),
                return_stdout=True,
            ),
            b""".
file.d
file.d/file
fileChanged
fileOld
fileUnchanged
""",
        )
        self.assertEqual(
            comtst.rdiff_backup_action(
                False,
                None,
                self.bak_path,
                None,
                (),
                b"list",
                ("files", "--at", "20000"),
                return_stdout=True,
            ),
            b""".
file.d
file.d/file
fileChanged
fileNew
fileUnchanged
""",
        )
        for at_time in ("100000", "200000", "30000", "40000"):
            self.assertEqual(
                comtst.rdiff_backup_action(
                    True,
                    None,
                    self.bak_path,
                    None,
                    (),
                    b"verify",
                    ("--at", at_time),
                ),
                consts.RET_CODE_OK,
            )

        # all tests were successful
        self.success = True

    def test_action_removedirectory(self):
        """test removing directory"""
        self.assertEqual(
            comtst.rdiff_backup_action(
                False,
                None,
                os.path.join(self.bak_path, b"file.d"),
                None,
                (),
                b"remove",
                ("file",),
            ),
            consts.RET_CODE_OK,
        )
        self.assertEqual(
            comtst.rdiff_backup_action(
                False,
                None,
                self.bak_path,
                None,
                (),
                b"list",
                ("files",),
                return_stdout=True,
            ),
            b""".
file
fileChanged
fileEvenNewer
fileUnchanged
""",
        )
        self.assertEqual(
            comtst.rdiff_backup_action(
                False,
                None,
                self.bak_path,
                None,
                (),
                b"list",
                ("files", "--at", "10000"),
                return_stdout=True,
            ),
            b""".
file
fileChanged
fileOld
fileUnchanged
""",
        )
        self.assertEqual(
            comtst.rdiff_backup_action(
                False,
                None,
                self.bak_path,
                None,
                (),
                b"list",
                ("files", "--at", "20000"),
                return_stdout=True,
            ),
            b""".
file
fileChanged
fileNew
fileUnchanged
""",
        )
        for at_time in ("100000", "200000", "30000", "40000"):
            self.assertEqual(
                comtst.rdiff_backup_action(
                    True,
                    None,
                    self.bak_path,
                    None,
                    (),
                    b"verify",
                    ("--at", at_time),
                ),
                consts.RET_CODE_OK,
            )

        # all tests were successful
        self.success = True

    def test_action_removefile(self):
        """test removing file only present partially"""
        self.assertEqual(
            comtst.rdiff_backup_action(
                False,
                None,
                os.path.join(self.bak_path, b"fileNew"),
                None,
                (),
                b"remove",
                ("file",),
            ),
            consts.RET_CODE_OK,
        )
        self.assertEqual(
            comtst.rdiff_backup_action(
                False,
                None,
                os.path.join(self.bak_path, b"fileOld"),
                None,
                (),
                b"remove",
                ("file",),
            ),
            consts.RET_CODE_OK,
        )
        # old and new files removed, result is the same at both times
        for at_time in ("10000", "20000"):
            self.assertEqual(
                comtst.rdiff_backup_action(
                    False,
                    None,
                    self.bak_path,
                    None,
                    (),
                    b"list",
                    ("files", "--at", at_time),
                    return_stdout=True,
                ),
                b""".
file
file.d
file.d/file
fileChanged
fileUnchanged
""",
            )
        for at_time in ("10000", "20000", "30000", "40000"):
            self.assertEqual(
                comtst.rdiff_backup_action(
                    True,
                    None,
                    self.bak_path,
                    None,
                    (),
                    b"verify",
                    ("--at", at_time),
                ),
                consts.RET_CODE_OK,
            )

        # all tests were successful
        self.success = True

    def test_action_removefile_dryrun(self):
        """test not really removing files"""
        self.assertEqual(
            comtst.rdiff_backup_action(
                False,
                None,
                os.path.join(self.bak_path, b"file-does-not-exist"),
                None,
                (),
                b"remove",
                ("file", "--dry-run"),
            ),
            consts.RET_CODE_WARN,
        )
        self.assertEqual(
            comtst.rdiff_backup_action(
                False,
                None,
                os.path.join(self.bak_path, b"file"),
                None,
                (),
                b"remove",
                ("file", "--dry-run"),
            ),
            consts.RET_CODE_OK,
        )
        self.assertEqual(
            comtst.rdiff_backup_action(
                False,
                None,
                self.bak_path,
                None,
                (),
                b"list",
                ("files",),
                return_stdout=True,
            ),
            b""".
file
file.d
file.d/file
fileChanged
fileEvenNewer
fileUnchanged
""",
        )
        self.assertEqual(
            comtst.rdiff_backup_action(
                False,
                None,
                self.bak_path,
                None,
                (),
                b"list",
                ("files", "--at", "10000"),
                return_stdout=True,
            ),
            b""".
file
file.d
file.d/file
fileChanged
fileOld
fileUnchanged
""",
        )
        self.assertEqual(
            comtst.rdiff_backup_action(
                False,
                None,
                self.bak_path,
                None,
                (),
                b"list",
                ("files", "--at", "20000"),
                return_stdout=True,
            ),
            b""".
file
file.d
file.d/file
fileChanged
fileNew
fileUnchanged
""",
        )
        for at_time in ("100000", "200000", "30000", "40000"):
            self.assertEqual(
                comtst.rdiff_backup_action(
                    True,
                    None,
                    self.bak_path,
                    None,
                    (),
                    b"verify",
                    ("--at", at_time),
                ),
                consts.RET_CODE_OK,
            )

        # all tests were successful
        self.success = True


if __name__ == "__main__":
    unittest.main()
