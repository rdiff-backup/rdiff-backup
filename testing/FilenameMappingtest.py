import unittest
import os
from commontest import MakeOutputDir, abs_output_dir, abs_test_dir, old_test_dir, \
    re_init_rpath_dir, rdiff_backup
from rdiff_backup import FilenameMapping, rpath, Globals


class FilenameMappingTest(unittest.TestCase):
    """Test the FilenameMapping class, for quoting filenames"""

    def setUp(self):
        """Just initialize quoting"""
        Globals.chars_to_quote = b'A-Z'
        FilenameMapping.set_init_quote_vals()

    def testBasicQuote(self):
        """Test basic quoting and unquoting"""
        filenames = [
            b"hello", b"HeLLo", b"EUOeu/EUOeu", b":", b"::::EU", b"/:/:"
        ]
        for filename in filenames:
            quoted = FilenameMapping.quote(filename)
            self.assertEqual(FilenameMapping.unquote(quoted), filename)

    def testQuotedRPath(self):
        """Test the QuotedRPath class"""
        path = (b"/usr/local/mirror_metadata"
                b".1969-12-31;08421;05833;05820-07;05800.data.gz")
        qrp = FilenameMapping.get_quotedrpath(
            rpath.RPath(Globals.local_connection, path), 1)
        self.assertEqual(qrp.base, b"/usr/local")
        self.assertEqual(len(qrp.index), 1)
        self.assertEqual(qrp.index[0],
                         b"mirror_metadata.1969-12-31T21:33:20-07:00.data.gz")

    def testLongFilenames(self):
        """See if long quoted filenames cause crash"""
        MakeOutputDir()
        outrp = rpath.RPath(Globals.local_connection, abs_output_dir)
        inrp = rpath.RPath(Globals.local_connection,
                           os.path.join(abs_test_dir, b"quotetest"))
        re_init_rpath_dir(inrp)
        long_filename = b"A" * 200  # when quoted should cause overflow
        longrp = inrp.append(long_filename)
        longrp.touch()
        shortrp = inrp.append(b"B")
        shortrp.touch()

        rdiff_backup(1,
                     1,
                     inrp.path,
                     outrp.path,
                     100000,
                     extra_options=b"--override-chars-to-quote A")

        longrp_out = outrp.append(long_filename)
        self.assertFalse(longrp_out.lstat())
        shortrp_out = outrp.append('B')
        self.assertTrue(shortrp_out.lstat())

        rdiff_backup(1, 1, os.path.join(old_test_dir, b"empty"), outrp.path,
                     200000)
        shortrp_out.setdata()
        self.assertFalse(shortrp_out.lstat())
        rdiff_backup(1, 1, inrp.path, outrp.path, 300000)
        shortrp_out.setdata()
        self.assertTrue(shortrp_out.lstat())


if __name__ == "__main__":
    unittest.main()
