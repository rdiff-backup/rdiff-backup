"""
Test the psutil alternative implementation
"""
import os
import unittest
import sys

from rdiffbackup.utils import psutil


class UtilsPsutilTest(unittest.TestCase):
    """
    Test that rdiff-backup properly handles hardlinks
    """

    def test_utils_psutil(self):
        """
        verify that hardlinked files can be rotated, see issue #272
        i.e. first one removed and new one added.
        """
        # the split is meant to get rid of `.exe` under Windows
        self.assertIn(psutil.get_pid_name(os.getpid()).split(".")[0],
                      ("python", "python3", "coverage"))

        print(sys.argv[0])
        self.assertIsNone(psutil.get_pid_name(sys.maxsize))


if __name__ == "__main__":
    unittest.main()
