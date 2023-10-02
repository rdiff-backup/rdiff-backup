import os
import time
import unittest
import commontest as ct
from rdiff_backup import Globals, rpath
from rdiffbackup.locations.map import filenames as map_filenames


class FilenameMappingTest(unittest.TestCase):
    """Test the map_filenames module, for quoting filenames"""

    def setUp(self):
        """Just initialize quoting"""
        ctq = b'A-Z'
        # FIXME possibly too much internas
        regexp, unregexp = map_filenames.get_quoting_regexps(
            ctq, Globals.quoting_char)

        Globals.set_all('chars_to_quote', ctq)
        Globals.set_all('chars_to_quote_regexp', regexp)
        Globals.set_all('chars_to_quote_unregexp', unregexp)

    def testBasicQuote(self):
        """Test basic quoting and unquoting"""
        filenames = [
            b"hello", b"HeLLo", b"EUOeu/EUOeu", b":", b"::::EU", b"/:/:"
        ]
        for filename in filenames:
            quoted = map_filenames.quote(filename)
            self.assertEqual(map_filenames.unquote(quoted), filename)

    def testQuotedRPath(self):
        """Test the QuotedRPath class"""
        path = (b"/usr/local/mirror_metadata"
                b".1969-12-31;08421;05833;05820-07;05800.data.gz")
        qrp = map_filenames.get_quotedrpath(
            rpath.RPath(Globals.local_connection, path), 1)
        self.assertEqual(qrp.base, b"/usr/local")
        self.assertEqual(len(qrp.index), 1)
        self.assertEqual(qrp.index[0],
                         b"mirror_metadata.1969-12-31T21:33:20-07:00.data.gz")

    def testLongFilenames(self):
        """See if long quoted filenames cause crash"""
        ct.MakeOutputDir()
        outrp = rpath.RPath(Globals.local_connection, ct.abs_output_dir)
        inrp = rpath.RPath(Globals.local_connection,
                           os.path.join(ct.abs_test_dir, b"quotetest"))
        ct.re_init_rpath_dir(inrp)
        long_filename = b"A" * 200  # when quoted should cause overflow
        longrp = inrp.append(long_filename)
        longrp.touch()
        shortrp = inrp.append(b"B")
        shortrp.touch()

        ct.rdiff_backup(True, True,
                        inrp.path, outrp.path,
                        100000,
                        extra_options=b"--chars-to-quote A backup")

        longrp_out = outrp.append(long_filename)
        self.assertFalse(longrp_out.lstat())
        shortrp_out = outrp.append('B')
        self.assertTrue(shortrp_out.lstat())

        ct.rdiff_backup(True, True,
                        os.path.join(ct.old_test_dir, b"empty"), outrp.path,
                        200000)
        shortrp_out.setdata()
        self.assertFalse(shortrp_out.lstat())
        ct.rdiff_backup(True, True, inrp.path, outrp.path, 300000)
        shortrp_out.setdata()
        self.assertTrue(shortrp_out.lstat())

    def testReQuote(self):
        inrp = rpath.RPath(Globals.local_connection,
                           os.path.join(ct.abs_test_dir, b"requote"))
        ct.re_init_rpath_dir(inrp)
        inrp.append("ABC_XYZ.1").touch()
        outrp = rpath.RPath(Globals.local_connection, ct.abs_output_dir)
        ct.re_init_rpath_dir(outrp)
        self.assertEqual(
            ct.rdiff_backup_action(True, True, inrp.path, outrp.path,
                                   ("--chars-to-quote", "A-C"),
                                   b"backup", ()),
            0)
        time.sleep(1)
        inrp.append("ABC_XYZ.2").touch()
        # enforce a requote of the whole repository and see it refused
        self.assertNotEqual(
            ct.rdiff_backup_action(True, True, inrp.path, outrp.path,
                                   ("--chars-to-quote", "X-Z", "--force"),
                                   b"backup", ()),
            0)


if __name__ == "__main__":
    unittest.main()
