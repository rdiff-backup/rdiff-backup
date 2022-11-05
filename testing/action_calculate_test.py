"""
Test the basic backup and restore actions with api version >= 201
"""
import glob
import os
import shutil
import subprocess
import unittest

import commontest as comtst
import fileset


class ActionCalculateTest(unittest.TestCase):
    """
    Test that rdiff-backup properly calculates statistics
    """

    def setUp(self):
        self.base_dir = os.path.join(comtst.abs_test_dir,
                                     b"action_calculate")
        # Windows can't handle too long filenames
        long_multi = 10 if os.name == "nt" else 25
        self.from1_struct = {
            "from1": {"subs": {
                "fileA": {"content": "initial"},
                "fileB": {},
                "dirOld": {"type": "dir"},
                "itemX": {"type": "dir"},
                "itemY": {"type": "file"},
                "longdirnam" * long_multi: {"type": "dir"},
                "longfilnam" * long_multi: {"content": "not so long content"},
                # "somehardlink": {"link": "fileA"},
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
                "longdirnam" * long_multi: {"type": "dir"},
                "longfilnam" * long_multi: {"content": "differently long"},
                # "somehardlink": {"link": "fileA"},
            }}
        }
        self.from2_path = os.path.join(self.base_dir, b"from2")
        if os.name != "nt":
            # rdiff-backup can't handle (yet) hardlinks under Windows
            self.from1_struct["from1"]["subs"]["somehardlink"] = {
                "link": "fileA"}
            self.from2_struct["from2"]["subs"]["somehardlink"] = {
                "link": "fileA"}
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
        self.assertEqual(comtst.rdiff_backup_action(
            False, False, self.from1_path, self.bak_path,
            ("--api-version", "201", "--current-time", "10000",
             "--use-compatible-timestamps"),
            b"backup", ()), 0)
        self.assertEqual(comtst.rdiff_backup_action(
            False, True, self.from2_path, self.bak_path,
            ("--api-version", "201", "--current-time", "20000",
             "--use-compatible-timestamps"),
            b"backup", ()), 0)

        # then we calculate states across both sessions
        session_stats = glob.glob(os.path.join(self.bak_path,
                                               b"rdiff-backup-data",
                                               b"session_statistics.*"))
        self.assertRegex(
            comtst.rdiff_backup_action(
                True, True, *session_stats,
                ("--api-version", "201"),
                b"calculate", (), return_stdout=True),
            rb"^-*\[ Average of 2 stat files ")
        # there is only one method (average) so the result is the same actually
        self.assertRegex(
            comtst.rdiff_backup_action(
                True, True, *session_stats,
                ("--api-version", "201"),
                b"calculate", ("--method", "average"), return_stdout=True),
            rb"Errors 0")

        # try also rdiff-backup-statistics until we merge functionality into
        # the calculate plug-in (see #772)
        rd_stats_bin = os.fsencode(shutil.which("rdiff-backup-statistics")
                                   or "rdiff-backup-statistics")
        self.assertRegex(
            subprocess.check_output([rd_stats_bin, self.bak_path]),
            b"^Processing statistics from")

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
