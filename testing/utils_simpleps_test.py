"""
Test the simpleps alternative implementation
"""

import os
import unittest
import sys

from rdiffbackup.utils import simpleps

BINARIES = ("python", "python3", "coverage", "pytest")

class UtilsPsutilTest(unittest.TestCase):
    """
    Test the simpleps module
    """

    def test_utils_simpleps(self):
        """
        Check the utility module simpleps
        """
        # the split is meant to get rid of `.exe` under Windows
        self.assertIn(
            simpleps.get_pid_name(os.getpid()).split(".")[0], BINARIES
        )

        # max unicode doesn't make a lot of sense but it works under Linux
        # and Windows, and it should be seldom enough to not break the pipeline
        self.assertIsNone(simpleps.get_pid_name(sys.maxunicode))

        # we repeat the same tests with the internal version to improve code
        # coverage (assuming psutil might be installed)
        self.assertIn(
            simpleps._get_pid_name_ps(os.getpid()).split(".")[0], BINARIES
        )
        self.assertIsNone(simpleps._get_pid_name_ps(sys.maxunicode))


if __name__ == "__main__":
    unittest.main()
