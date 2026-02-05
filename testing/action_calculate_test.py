"""
Test the calculate action with api version >= 201
"""

import glob
import os
import unittest

from rdiffbackup.singletons import consts

import commontest as comtst
import fileset

TEST_BASE_DIR = comtst.get_test_base_dir(__file__)


class ActionCalculateTest(unittest.TestCase):
    """
    Test that rdiff-backup properly calculates statistics
    """

    def setUp(self):
        self.base_dir = os.path.join(TEST_BASE_DIR, b"action_calculate")
        # Windows can't handle too long filenames
        long_multi = 10 if os.name == "nt" else 25
        self.from1_struct = {
            "from1": {
                "contents": {
                    "fileA": {"content": "initial", "inode": "fileA"},
                    "fileB": {},
                    "dirOld": {"type": "dir"},
                    "itemX": {"type": "dir"},
                    "itemY": {"type": "file"},
                    "longdirnam" * long_multi: {"type": "dir"},
                    "longfilnam" * long_multi: {"content": "not so long content"},
                    # "somehardlink": {"inode": "fileA"},
                }
            }
        }
        self.from1_path = os.path.join(self.base_dir, b"from1")
        self.from2_struct = {
            "from2": {
                "contents": {
                    "fileA": {"content": "modified", "inode": "fileA"},
                    "fileC": {},
                    "dirNew": {"type": "dir"},
                    "itemX": {"type": "file"},
                    "itemY": {"type": "dir"},
                    "longdirnam" * long_multi: {"type": "dir"},
                    "longfilnam" * long_multi: {"content": "differently long"},
                    # "somehardlink": {"inode": "fileA"},
                }
            }
        }
        self.from2_path = os.path.join(self.base_dir, b"from2")
        if os.name != "nt":
            # rdiff-backup can't handle (yet) hardlinks under Windows
            self.from1_struct["from1"]["contents"]["somehardlink"] = {"inode": "fileA"}
            self.from2_struct["from2"]["contents"]["somehardlink"] = {"inode": "fileA"}
        fileset.create_fileset(self.base_dir, self.from1_struct)
        fileset.create_fileset(self.base_dir, self.from2_struct)
        fileset.remove_fileset(self.base_dir, {"bak": {"type": "dir"}})
        fileset.remove_fileset(self.base_dir, {"to1": {"type": "dir"}})
        fileset.remove_fileset(self.base_dir, {"to2": {"type": "dir"}})
        self.bak_path = os.path.join(self.base_dir, b"bak")
        self.to1_path = os.path.join(self.base_dir, b"to1")
        self.to2_path = os.path.join(self.base_dir, b"to2")
        self.success = False

    def test_action_calculate(self):
        """test the "calculate" action"""
        # we backup twice to the same backup repository at different times
        self.assertEqual(
            comtst.rdiff_backup_action(
                False,
                False,
                self.from1_path,
                self.bak_path,
                (
                    "--api-version",
                    "201",
                    "--current-time",
                    "10000",
                    "--use-compatible-timestamps",
                ),
                b"backup",
                (),
            ),
            0,
        )
        self.assertEqual(
            comtst.rdiff_backup_action(
                False,
                True,
                self.from2_path,
                self.bak_path,
                (
                    "--api-version",
                    "201",
                    "--current-time",
                    "20000",
                    "--use-compatible-timestamps",
                ),
                b"backup",
                (),
            ),
            0,
        )

        # then we calculate states across both sessions
        session_stats = glob.glob(
            os.path.join(self.bak_path, b"rdiff-backup-data", b"session_statistics.*")
        )
        output = comtst.rdiff_backup_action(
            True,
            True,
            *session_stats,
            ("--api-version", "201"),
            b"calculate",
            ("average",),
            return_stdout=True,
        )
        self.assertRegex(output, rb"^-*\[ Average of 2 stat files ")
        self.assertRegex(output, rb"Errors 0")

        output = comtst.rdiff_backup_action(
            True,
            True,
            self.bak_path,
            None,
            ("--api-version", "201"),
            b"calculate",
            ("statistics",),
            return_stdout=True,
        )
        self.assertRegex(output, rb"^-*\[ Average of 2 stat files ")
        self.assertRegex(output, rb"Errors 0")
        self.assertEqual(output.count(b"Top directories by"), 3)

        self.assertEqual(
            comtst.rdiff_backup_action(
                True,
                True,
                self.bak_path,
                None,
                ("--api-version", "201"),
                b"calculate",
                ("statistics", "--minimum-ratio", "1.1"),
            ),
            consts.RET_CODE_ERR,
        )

        self.assertEqual(
            comtst.rdiff_backup_action(
                True,
                True,
                self.bak_path,
                None,
                ("--api-version", "201"),
                b"calculate",
                ("statistics", "--begin", "that ain't a time"),
            ),
            consts.RET_CODE_ERR,
        )

        output = comtst.rdiff_backup_action(
            True,
            True,
            self.bak_path,
            None,
            ("--api-version", "201"),
            b"calculate",
            ("statistics", "--begin", "10000", "--end", "20000"),
            return_stdout=True,
        )
        self.assertRegex(output, rb"^-*\[ Average of 2 stat files ")
        self.assertRegex(output, rb"Errors 0")
        self.assertEqual(output.count(b"Top directories by"), 3)

        output = comtst.rdiff_backup_action(
            True,
            True,
            self.bak_path,
            None,
            ("--api-version", "201"),
            b"calculate",
            ("statistics", "--begin", "11000", "--end", "19000"),
            return_stderr=True,
        )
        self.assertRegex(
            output, rb"No statistics could be gathered within the given range"
        )

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
