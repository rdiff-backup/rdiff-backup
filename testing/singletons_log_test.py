"""
Test the logging functionality
"""

import io
import unittest

from rdiffbackup.singletons import consts, generics, log, specifics


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
        self.assertEqual(testlog.set_verbosity(log.NONE), consts.RET_CODE_OK)
        self.assertEqual(testlog.file_verbosity, log.NONE)
        self.assertEqual(testlog.term_verbosity, log.NONE)
        self.assertEqual(
            testlog.set_verbosity(str(log.DEBUG), str(log.WARNING)),
            consts.RET_CODE_OK,
        )
        self.assertEqual(testlog.file_verbosity, log.DEBUG)
        self.assertEqual(testlog.term_verbosity, log.WARNING)
        # error cases
        self.assertEqual(testlog.set_verbosity(str(log.NONE - 1)), consts.RET_CODE_ERR)
        # nothing changes
        self.assertEqual(testlog.file_verbosity, log.DEBUG)
        self.assertEqual(testlog.term_verbosity, log.WARNING)
        self.assertEqual(
            testlog.set_verbosity(str(log.ERROR), log.TIMESTAMP + 1),
            consts.RET_CODE_ERR,
        )
        # nothing changes even if only the 2nd value is wrong
        self.assertEqual(testlog.file_verbosity, log.DEBUG)
        self.assertEqual(testlog.term_verbosity, log.WARNING)

    def test_log_open_logfile(self):
        """test that log strings are properly written to log writer"""
        specifics.set("is_backup_writer", True)
        testlog = log.Logger()
        logbuffer = io.BytesIO()
        testlog.open_logfile(logbuffer)
        testlog.set_verbosity(log.WARNING, log.NONE)
        testlog("Something fishy", log.WARNING)
        self.assertEqual(logbuffer.getvalue(), b"WARNING: Something fishy\n")
        testlog("All is good", log.NONE)
        self.assertEqual(
            logbuffer.getvalue(), b"WARNING: Something fishy\nAll is good\n"
        )

    def test_errorlog_open_logfile(self):
        """test that error log strings are properly written to log writer"""
        specifics.set("is_backup_writer", True)
        testlog = log.ErrorLogger()
        logbuffer = io.BytesIO()
        testlog.open_logfile(logbuffer)
        testlog("ListError", "Something\nfishy", Exception("xyz"))
        self.assertEqual(logbuffer.getvalue(), b"ListError: 'Something fishy' xyz\n")
        generics.set("null_separator", True)
        testlog("UpdateError", "Swimming\nagain", Exception("abc"))
        self.assertEqual(
            logbuffer.getvalue(),
            b"ListError: 'Something fishy' xyz\n"
            b"UpdateError: 'Swimming\nagain' abc\0",
        )


if __name__ == "__main__":
    unittest.main()
