"""
Test the logging functionality
"""

import unittest

from rdiff_backup import Globals, log


class LogTest(unittest.TestCase):
    """
    Test that rdiff-backup properly logs messages
    """

    def test_log_validate_verbosity(self):
        """test that verbosity validation works correctly"""
        # happy path
        self.assertEqual(log.Logger.validate_verbosity(log.NONE), log.NONE)
        self.assertEqual(log.Logger.validate_verbosity(str(log.NOTE)), log.NOTE)
        self.assertEqual(log.Logger.validate_verbosity(log.TIMESTAMP), log.TIMESTAMP)
        # error cases
        self.assertRaises(ValueError, log.Logger.validate_verbosity, log.NONE - 1)
        self.assertRaises(
            ValueError, log.Logger.validate_verbosity, str(log.TIMESTAMP + 1)
        )
        self.assertRaises(ValueError, log.Logger.validate_verbosity, "xxx")
        self.assertRaises(ValueError, log.Logger.validate_verbosity, "NaN")

    def test_log_set_verbosity(self):
        """test that verbosity is correctly set"""
        # happy path
        testlog = log.Logger()
        self.assertEqual(testlog.set_verbosity(log.NONE), Globals.RET_CODE_OK)
        self.assertEqual(testlog.file_verbosity, log.NONE)
        self.assertEqual(testlog.term_verbosity, log.NONE)
        self.assertEqual(
            testlog.set_verbosity(str(log.DEBUG), str(log.WARNING)),
            Globals.RET_CODE_OK,
        )
        self.assertEqual(testlog.file_verbosity, log.DEBUG)
        self.assertEqual(testlog.term_verbosity, log.WARNING)
        # error cases
        self.assertEqual(testlog.set_verbosity(str(log.NONE - 1)), Globals.RET_CODE_ERR)
        # nothing changes
        self.assertEqual(testlog.file_verbosity, log.DEBUG)
        self.assertEqual(testlog.term_verbosity, log.WARNING)
        self.assertEqual(
            testlog.set_verbosity(str(log.ERROR), log.TIMESTAMP + 1),
            Globals.RET_CODE_ERR,
        )
        # nothing changes even if only the 2nd value is wrong
        self.assertEqual(testlog.file_verbosity, log.DEBUG)
        self.assertEqual(testlog.term_verbosity, log.WARNING)


if __name__ == "__main__":
    unittest.main()
