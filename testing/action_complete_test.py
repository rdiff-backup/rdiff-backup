"""
Test the complete action with api version >= 201
"""

import os
import unittest

import commontest as comtst

from rdiff_backup import Globals

TEST_BASE_DIR = comtst.get_test_base_dir(__file__)


class ActionCompleteTest(unittest.TestCase):
    """
    Test that rdiff-backup completes properly
    """

    def test_action_complete(self):
        """test different ways of comparing directories"""

        # test the error cases
        self.assertEqual(
            comtst.rdiff_backup_action(
                True, True, None, None, ("--api-version", "201"), b"complete", ()
            ),
            Globals.RET_CODE_ERR,
        )
        self.assertEqual(
            comtst.rdiff_backup_action(
                True,
                True,
                None,
                None,
                ("--api-version", "201"),
                b"complete",
                ("--cword", "1", "--", "rdiff-backup"),
            ),
            Globals.RET_CODE_ERR,
        )

        # then try different combinations of verbosity
        self.assertEqual(
            comtst.rdiff_backup_action(
                True,
                True,
                None,
                None,
                ("--api-version", "201"),
                b"complete",
                ("--cword", "1", "--", "rdiff-backup", "--verb"),
                return_stdout=True,
            ),
            b"""--verbosity
""",
        )
        self.assertEqual(
            comtst.rdiff_backup_action(
                True,
                True,
                None,
                None,
                ("--api-version", "201"),
                b"complete",
                ("--cword", "2", "--", "rdiff-backup", "--verbosity", ""),
                return_stdout=True,
            ),
            os.fsencode("\n".join(map(str, range(0, 10)))) + b"\n",
        )
        self.assertEqual(
            comtst.rdiff_backup_action(
                True,
                True,
                None,
                None,
                ("--api-version", "201"),
                b"complete",
                ("--cword", "1", "--", "rdiff-backup", "--verbosity", "5"),
                return_stdout=True,
            ),
            b"""--verbosity
""",
        )

        # then check what happens with files
        self.assertEqual(
            comtst.rdiff_backup_action(
                True,
                True,
                None,
                None,
                ("--api-version", "201"),
                b"complete",
                ("--cword", "2", "--", "rdiff-backup", "backup", "D"),
                return_stdout=True,
            ),
            b"""::file::
""",
        )
        full_output = comtst.rdiff_backup_action(
            True,
            True,
            None,
            None,
            ("--api-version", "201"),
            b"complete",
            ("--cword", "2", "--", "rdiff-backup", "backup", ""),
            return_stdout=True,
        )
        self.assertTrue(full_output.startswith(b"--"))
        self.assertTrue(full_output.endswith(b"::file::\n"))

        full_output = comtst.rdiff_backup_action(
            True,
            True,
            None,
            None,
            ("--api-version", "201"),
            b"complete",
            ("--cword", "1", "--", "rdiff-backup", ""),
            return_stdout=True,
        )
        self.assertTrue(full_output.startswith(b"-V"))  # fragile!
        self.assertTrue(full_output.endswith(b"--version\n"))
        self.assertIn(b"complete\n", full_output)
        self.assertIn(b"backup\n", full_output)

        # if the action is already given, none should be listed again
        full_output = comtst.rdiff_backup_action(
            True,
            True,
            None,
            None,
            ("--api-version", "201"),
            b"complete",
            ("--cword", "1", "--", "rdiff-backup", "", "complete"),
            return_stdout=True,
        )
        self.assertTrue(full_output.startswith(b"-V"))  # fragile!
        self.assertTrue(full_output.endswith(b"--version\n"))
        self.assertNotIn(b"complete\n", full_output)
        self.assertNotIn(b"backup\n", full_output)

        self.assertEqual(
            comtst.rdiff_backup_action(
                True,
                True,
                None,
                None,
                ("--api-version", "201"),
                b"complete",
                (
                    "--cword",
                    "3",
                    "--",
                    "rdiff-backup",
                    "backup",
                    "--user-mapping-file",
                    "",
                ),
                return_stdout=True,
            ),
            b"""::file::
""",
        )


if __name__ == "__main__":
    unittest.main()
