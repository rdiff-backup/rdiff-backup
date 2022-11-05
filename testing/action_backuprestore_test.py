"""
Test the basic backup and restore actions with api version >= 201
"""
import glob
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
        fileset.remove_fileset(self.base_dir, {"to3": {"type": "dir"}})
        fileset.create_fileset(self.base_dir, {"to4": {"type": "file"}})
        self.bak_path = os.path.join(self.base_dir, b"bak")
        self.to1_path = os.path.join(self.base_dir, b"to1")
        self.to2_path = os.path.join(self.base_dir, b"to2")
        self.to3_path = os.path.join(self.base_dir, b"to3")
        self.to4_path = os.path.join(self.base_dir, b"to4")
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
            ("--api-version", "201", "--no-ssh-compression"),
            b"restore", ("--at", "1B")), 0)
        self.assertEqual(comtst.rdiff_backup_action(
            True, True, self.bak_path, self.to2_path,
            ("--api-version", "201", "--remote-tempdir", self.base_dir),
            b"restore", ()), 0)
        dir_old_inc = glob.glob(
            os.path.join(self.bak_path,
                         b'rdiff-backup-data', b'increments', b'dirOld.*'))[0]
        self.assertEqual(comtst.rdiff_backup_action(
            True, True, dir_old_inc, self.to3_path,
            ("--api-version", "201"),
            b"restore", ()), 0)

        self.assertFalse(fileset.compare_paths(self.from1_path, self.to1_path))
        self.assertFalse(fileset.compare_paths(self.from2_path, self.to2_path))

        # all tests were successful
        self.success = True

    def test_action_backup_errorcases(self):
        """test the "backup" actions in error cases"""
        # we backup twice to the same backup repository at different times
        self.assertEqual(comtst.rdiff_backup_action(
            False, False, self.from1_path, self.bak_path,
            ("--api-version", "201", "--current-time", "10000"),
            b"backup", ()), 0)
        self.assertNotEqual(comtst.rdiff_backup_action(
            False, True, self.from2_path, self.bak_path,
            ("--api-version", "201", "--current-time", "10000"),
            b"backup", ()), 0)  # can't backup at same time
        self.assertNotEqual(comtst.rdiff_backup_action(
            False, True, self.from2_path, self.bak_path,
            ("--api-version", "201", "--current-time", "20000"),
            b"backup", ("--exclude", "not-in-from")), 0)  # can't match
        self.assertNotEqual(comtst.rdiff_backup_action(
            False, True, self.from2_path, self.bak_path,
            ("--api-version", "201", "--current-time", "20001"),
            b"backup", ("--include", "**")), 0)  # redundant inclusion

    def test_action_restore_errorcases(self):
        """test the "restore" actions in error cases"""
        # we backup twice to the same backup repository at different times
        self.assertEqual(comtst.rdiff_backup_action(
            False, False, self.from1_path, self.bak_path,
            ("--api-version", "201", "--current-time", "10000"),
            b"backup", ()), 0)
        self.assertEqual(comtst.rdiff_backup_action(
            False, True, self.from2_path, self.bak_path,
            ("--api-version", "201", "--current-time", "20000"),
            b"backup", ()), 0)

        # then we generate some error cases while restoring
        self.assertNotEqual(comtst.rdiff_backup_action(
            True, False, self.bak_path, self.to1_path,
            ("--api-version", "201"),
            b"restore", ("--at", "xyz")), 0)  # bad time string
        self.assertNotEqual(comtst.rdiff_backup_action(
            True, True, self.bak_path, self.to4_path,  # can't write to file
            ("--api-version", "201"),
            b"restore", ()), 0)
        self.assertEqual(comtst.rdiff_backup_action(
            True, True, self.bak_path, self.to4_path,  # force write to file
            ("--api-version", "201", "--force"),
            b"restore", ()), 0)
        self.assertNotEqual(comtst.rdiff_backup_action(
            True, False, self.bak_path, self.to1_path,
            ("--api-version", "201"),
            b"restore", ("--at", "1B", "--increment")), 0)  # both not allowed
        self.assertNotEqual(comtst.rdiff_backup_action(
            True, True, self.bak_path, self.to2_path,
            ("--api-version", "201"),
            b"restore", ("--increment",)), 0)  # not an increment!
        self.assertNotEqual(comtst.rdiff_backup_action(
            True, False, b"/does-not-exist", self.to1_path,
            ("--api-version", "201"),
            b"restore", ()), 0)  # restoring from non-existing repository
        self.assertNotEqual(comtst.rdiff_backup_action(
            True, False, self.to4_path, self.to1_path,
            ("--api-version", "201"),
            b"restore", ()), 0)  # restoring from non-repository directory
        # can't combine increment restore and file selection
        dir_old_inc = glob.glob(
            os.path.join(self.bak_path,
                         b'rdiff-backup-data', b'increments', b'dirOld.*'))[0]
        self.assertNotEqual(comtst.rdiff_backup_action(
            True, True, dir_old_inc, self.to3_path,
            ("--api-version", "201"),
            b"restore", ("--exclude-regexp", "*.forbidden")), 0)

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
             "--chars-to-quote", "A:"),  # colon for Windows compatibility
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
            fileset.remove_fileset(self.base_dir, {"to3": {"type": "dir"}})
            fileset.remove_fileset(self.base_dir, {"to4": {"type": "dir"}})


class PreQuotingTest(unittest.TestCase):
    """
    Test rdiff-backup's quoting mechanisms cf. #275
    """

    def setUp(self):
        self.base_dir = os.path.join(comtst.abs_test_dir,
                                     b"action_backuprestore")
        self.from1_struct = {
            "from1": {"subs": {  # CODE.txt pre-quoted
                ";067;079;068;069.txt": {"content": "initial"},
            }}
        }
        self.from1_path = os.path.join(self.base_dir, b"from1")
        self.from2_struct = {
            "from2": {"subs": {  # CODE.txt pre-quoted and non-quoted
                ";067;079;068;069.txt": {"content": "modified"},
                "CODE.txt": {"content": "whatever"},
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

    def test_pre_quoted_files(self):
        # we backup using a specific chars-to-quote
        self.assertEqual(comtst.rdiff_backup_action(
            False, False, self.from1_path, self.bak_path,
            ("--api-version", "201", "--current-time", "10000",
             "--chars-to-quote", "A-Z:"),  # colon for Windows compatibility
            b"backup", ()), 0)
        self.assertEqual(comtst.rdiff_backup_action(
            True, True, self.from2_path, self.bak_path,
            ("--api-version", "201", "--current-time", "20000",
             "--chars-to-quote", "A-Z:"),  # colon for Windows compatibility
            b"backup", ()), 0)

        # then we restore once the full repo, once a sub-path
        self.assertEqual(comtst.rdiff_backup_action(
            True, False, self.bak_path, self.to1_path,
            ("--api-version", "201"),
            b"restore", ("--at", "10000")), 0)
        self.assertEqual(comtst.rdiff_backup_action(
            True, True, self.bak_path, self.to2_path,
            ("--api-version", "201"),
            b"restore", ("--at", "20000")), 0)
        # use sets to avoid issues with directory ordering
        self.assertEqual(set(os.listdir(self.to1_path)),
                         {b';067;079;068;069.txt'})
        self.assertEqual(set(os.listdir(self.to2_path)),
                         {b';067;079;068;069.txt', b'CODE.txt'})
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
