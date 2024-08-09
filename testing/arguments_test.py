"""
Test handling of of rdiff-backup CLI arguments
"""

import subprocess
import unittest

import commontest as comtst

from rdiffbackup import arguments, actions_mgr
from rdiffbackup.singletons import consts


class ArgumentsTest(unittest.TestCase):
    """
    Test how the function 'parse' is parsing arguments, using the new interface.
    """

    def test_new_help(self):
        """
        - make sure that the new help is shown either at top level by using an action
        """
        output = subprocess.run([comtst.RBBin, b"--help"], capture_output=True)
        self.assertIn(b"possible actions:", output.stdout)
        self.assertEqual(0, output.returncode)

        output = subprocess.run([comtst.RBBin, b"info", b"--help"], capture_output=True)
        self.assertIn(b"Output information", output.stdout)
        self.assertEqual(consts.RET_CODE_OK, output.returncode)

    def test_error_return_code(self):
        """
        - verify that a wrong arguments returns 1 instead of the standard 2
        """
        output = subprocess.run(
            [comtst.RBBin, b"--thisdoesntexist"], capture_output=True
        )
        self.assertIn(b"the following arguments are required:", output.stderr)
        self.assertEqual(consts.RET_CODE_ERR, output.returncode)

    def test_parse_function(self):
        """
        - verify that the --version option exits and make a few more smoke tests of the parse option
        """
        disc_actions = actions_mgr.get_actions_dict()

        # verify that the --version option exits the program
        with self.assertRaises(SystemExit):
            values = arguments.parse(
                ["--version"],
                "testing 0.0.1",
                actions_mgr.get_generic_parsers(),
                disc_actions,
            )

        # positive test of the parsing
        values = arguments.parse(
            ["list", "increments", "dummy_test_repo"],
            "testing 0.0.2",
            actions_mgr.get_generic_parsers(),
            disc_actions,
        )
        self.assertEqual("list", values["action"])
        self.assertEqual("increments", values["entity"])
        self.assertIn("dummy_test_repo", values["locations"])

        # negative test of the parsing due to too many or wrong arguments
        with self.assertRaises(SystemExit):
            values = arguments.parse(
                ["backup", "from", "to", "toomuch"],
                "testing 0.0.3",
                actions_mgr.get_generic_parsers(),
                disc_actions,
            )
        with self.assertRaises(SystemExit):
            values = arguments.parse(
                ["restore", "--no-such-thing", "from", "to"],
                "testing 0.0.4",
                actions_mgr.get_generic_parsers(),
                disc_actions,
            )


if __name__ == "__main__":
    unittest.main()
