"""
Test filename mapping functions
"""

import os
import time
import unittest

import commontest as comtst

from rdiff_backup import rpath
from rdiffbackup.locations.map import filenames as map_filenames
from rdiffbackup.singletons import consts, generics, specifics

TEST_BASE_DIR = comtst.get_test_base_dir(__file__)


class FilenameMappingTest(unittest.TestCase):
    """Test the map_filenames module, for quoting filenames"""

    out_dir = os.path.join(TEST_BASE_DIR, b"output")

    def setUp(self):
        """Just initialize quoting"""
        ctq = b"A-Z"
        # FIXME possibly too much internas
        regexp, unregexp = map_filenames.get_quoting_regexps(ctq, consts.QUOTING_CHAR)

        generics.set("chars_to_quote", ctq)
        generics.set("chars_to_quote_regexp", regexp)
        generics.set("chars_to_quote_unregexp", unregexp)

    def tearDown(self):
        comtst.reset_connections()

    def testBasicQuote(self):
        """Test basic quoting and unquoting"""
        filenames = [b"hello", b"HeLLo", b"EUOeu/EUOeu", b":", b"::::EU", b"/:/:"]
        for filename in filenames:
            quoted = map_filenames.quote(filename)
            self.assertEqual(map_filenames.unquote(quoted), filename)

    def testQuotedRPath(self):
        """Test the QuotedRPath class"""
        path = (
            b"/usr/local/mirror_metadata"
            b".1969-12-31;08421;05833;05820-07;05800.data.gz"
        )
        qrp = map_filenames.get_quotedrpath(
            rpath.RPath(specifics.local_connection, path), 1
        )
        self.assertEqual(qrp.base, b"/usr/local")
        self.assertEqual(len(qrp.index), 1)
        self.assertEqual(
            qrp.index[0], b"mirror_metadata.1969-12-31T21:33:20-07:00.data.gz"
        )

    def testLongFilenames(self):
        """See if long quoted filenames cause crash"""
        outrp = rpath.RPath(specifics.local_connection, self.out_dir)
        comtst.re_init_rpath_dir(outrp)
        inrp = rpath.RPath(
            specifics.local_connection, os.path.join(TEST_BASE_DIR, b"quotetest")
        )
        comtst.re_init_rpath_dir(inrp)
        long_filename = b"A" * 200  # when quoted should cause overflow
        longrp = inrp.append(long_filename)
        longrp.touch()
        shortrp = inrp.append(b"B")
        shortrp.touch()

        comtst.rdiff_backup(
            True,
            True,
            inrp.path,
            outrp.path,
            100000,
            extra_options=(b"--chars-to-quote", b"A", b"backup"),
        )

        longrp_out = outrp.append(long_filename)
        self.assertFalse(longrp_out.lstat())
        shortrp_out = outrp.append("B")
        self.assertTrue(shortrp_out.lstat())

        comtst.rdiff_backup(
            True, True, os.path.join(comtst.old_test_dir, b"empty"), outrp.path, 200000
        )
        shortrp_out.setdata()
        self.assertFalse(shortrp_out.lstat())
        comtst.rdiff_backup(True, True, inrp.path, outrp.path, 300000)
        shortrp_out.setdata()
        self.assertTrue(shortrp_out.lstat())

    def testReQuote(self):
        inrp = rpath.RPath(
            specifics.local_connection, os.path.join(TEST_BASE_DIR, b"requote")
        )
        comtst.re_init_rpath_dir(inrp)
        inrp.append("ABC_XYZ.1").touch()
        outrp = rpath.RPath(specifics.local_connection, self.out_dir)
        comtst.re_init_rpath_dir(outrp)
        self.assertEqual(
            comtst.rdiff_backup_action(
                True,
                True,
                inrp.path,
                outrp.path,
                ("--chars-to-quote", "A-C"),
                b"backup",
                (),
            ),
            0,
        )
        time.sleep(1)
        inrp.append("ABC_XYZ.2").touch()
        # enforce a requote of the whole repository and see it refused
        self.assertNotEqual(
            comtst.rdiff_backup_action(
                True,
                True,
                inrp.path,
                outrp.path,
                ("--chars-to-quote", "X-Z", "--force"),
                b"backup",
                (),
            ),
            0,
        )


if __name__ == "__main__":
    unittest.main()
