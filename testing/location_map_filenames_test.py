"""
Test the quoting of characters in filenames with api version >= 201
"""
import os
import unittest

import commontest as comtst
import fileset
from rdiff_backup import Globals


class LocationMapFilenamesTest(unittest.TestCase):
    """
    Test that rdiff-backup really restores what has been backed-up with quotes
    """

    def setUp(self):
        self.base_dir = os.path.join(comtst.abs_test_dir,
                                     b"location_map_filenames")
        # Windows can't handle too long filenames
        long_multi = 5 if os.name == "nt" else 25
        self.from1_struct = {
            "from1": {"subs": {
                "fileABC": {"content": "initial"},
                "fileXYZ": {},
                "dirAbCXyZ": {"type": "dir"},
                "itemX": {"type": "dir"},
                "itemY": {"type": "file"},
                "longDiRnAm" * long_multi: {"type": "dir"},
                "longFiLnAm" * long_multi: {"content": "not so long content"},
                # it should be aux.123 but it can't be created under Windows
                # and isn't special under Linux
                "aux123": {"content": "looks like DOS file"},
                "ends_in_blank ": {"content": "looks like DOS file"},
            }}
        }
        self.from1_path = os.path.join(self.base_dir, b"from1")
        self.from2_struct = {
            "from2": {"subs": {
                "fileABC": {"content": "modified"},
                "fileXYZ": {},
                "diraBcXyZ": {"type": "dir"},
                "itemX": {"type": "file"},
                "itemY": {"type": "dir"},
                "longDiRnAm" * long_multi: {"type": "dir"},
                "longFiLnAm" * long_multi: {"content": "differently long"},
                # it should be aux.123 but it can't be created under Windows
                # and isn't special under Linux
                "aux123": {"content": "still looks like DOS file"},
                "ends_in_blank ": {"content": "still looks like DOS file"},
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

    def test_location_map_filenames(self):
        """
        test the "backup" and "restore" actions with quoted filenames
        """
        # we backup twice to the same backup repository at different times
        self.assertEqual(comtst.rdiff_backup_action(
            False, False, self.from1_path, self.bak_path,
            ("--api-version", "201", "--current-time", "10000",
             "--chars-to-quote", "A-Z:"),
            b"backup", ()), 0)
        self.assertEqual(comtst.rdiff_backup_action(
            False, True, self.from2_path, self.bak_path,
            ("--api-version", "201", "--current-time", "20000",
             "--chars-to-quote", "A-Z:"),
            b"backup", ()), 0)

        # then we restore the increment and the last mirror to two directories
        self.assertEqual(comtst.rdiff_backup_action(
            True, False, self.bak_path, self.to1_path,
            ("--api-version", "201"),
            b"restore", ("--at", "1B")), 0)
        self.assertEqual(comtst.rdiff_backup_action(
            True, True, self.bak_path, self.to2_path,
            ("--api-version", "201"),
            b"restore", ()), 0)

        self.assertFalse(fileset.compare_paths(self.from1_path, self.to1_path))
        self.assertFalse(fileset.compare_paths(self.from2_path, self.to2_path))

        # all tests were successful
        self.success = True

    def test_location_map_filenames_change_quotes(self):
        """
        test the "backup" and "restore" actions with quoted filenames
        while changing the quoted characters, which isn't supported
        """
        # we backup twice to the same backup repository at different times
        self.assertEqual(comtst.rdiff_backup_action(
            False, False, self.from1_path, self.bak_path,
            ("--api-version", "201", "--current-time", "10000",
             "--chars-to-quote", "A-P:"),
            b"backup", ()), 0)
        # we try the 2nd time to change the chars-to-quote, which fails
        self.assertNotEqual(comtst.rdiff_backup_action(
            False, True, self.from2_path, self.bak_path,
            ("--api-version", "201", "--current-time", "15000",
             "--chars-to-quote", "H-Z:"),
            b"backup", ()), 0)
        self.assertNotEqual(comtst.rdiff_backup_action(
            False, True, self.from2_path, self.bak_path,
            ("--api-version", "201", "--current-time", "20000",
             "--chars-to-quote", "H-Z:", "--force"),
            b"backup", ()), 0)

        # then we restore the last mirror to a directory without issue
        self.assertEqual(comtst.rdiff_backup_action(
            True, True, self.bak_path, self.to1_path,
            ("--api-version", "201"),
            b"restore", ()), 0)

        self.assertFalse(fileset.compare_paths(self.from1_path, self.to1_path))

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


class LocationMapFilenamesUnitTest(unittest.TestCase):
    """
    Test specific aspects of locations.map.filenames to increase coverage
    """

    def test_location_map_filenames_dos_quotes(self):
        """
        Check that DOS filenames are properly quoted
        """
        Globals.escape_dos_devices = True
        Globals.escape_trailing_spaces = True
        from rdiffbackup.locations.map import filenames as map_filenames

        chars_to_quote = b"A-Z"
        regexp, unregexp = map_filenames.get_quoting_regexps(
            chars_to_quote, Globals.quoting_char)
        Globals.set_all("chars_to_quote", chars_to_quote)
        Globals.set_all('chars_to_quote_regexp', regexp)
        Globals.set_all('chars_to_quote_unregexp', unregexp)

        self.assertEqual(map_filenames.quote(b'aux.123'), b";097ux.123")
        self.assertEqual(map_filenames.quote(b'ends in space '),
                         b"ends in space;032")


if __name__ == "__main__":
    unittest.main()
