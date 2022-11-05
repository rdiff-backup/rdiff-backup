"""
Test the simpleps alternative implementation
"""
import os
import unittest
import sys

from rdiffbackup.utils import simpleps


class UtilsPsutilTest(unittest.TestCase):
    """
    Test that rdiff-backup properly handles hardlinks
    """

    def test_utils_simpleps(self):
        """
        verify that hardlinked files can be rotated, see issue #272
        i.e. first one removed and new one added.
        """
        # the split is meant to get rid of `.exe` under Windows
        self.assertIn(simpleps.get_pid_name(os.getpid()).split(".")[0],
                      ("python", "python3", "coverage"))

        # max unicode doesn't make a lot of sense but it works under Linux
        # and Windows, and it should be seldom enough to not break the pipeline
        self.assertIsNone(simpleps.get_pid_name(sys.maxunicode))

        # we repeat the same tests with the internal version to improve code
        # coverage (assuming psutil might be installed)
        self.assertIn(simpleps._get_pid_name_ps(os.getpid()).split(".")[0],
                      ("python", "python3", "coverage"))
        self.assertIsNone(simpleps._get_pid_name_ps(sys.maxunicode))


if __name__ == "__main__":
    unittest.main()
