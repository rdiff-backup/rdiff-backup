"""
Test the librsync functionality
"""

import os
import random
import subprocess
import unittest

import commontest as comtst

from rdiff_backup import Globals, librsync, rpath

TEST_BASE_DIR = comtst.get_test_base_dir(__file__)


def MakeRandomFile(path, length=None):
    """Writes a random file of given length, or random len if unspecified"""
    if not length:
        length = random.randrange(5000, 100000)
    with open(path, "wb") as fp:
        fp.write(os.urandom(length))


class LibrsyncTest(unittest.TestCase):
    """Test various librsync wrapper functions"""

    basis = rpath.RPath(specifics.local_connection, os.path.join(TEST_BASE_DIR, b"basis"))
    new = rpath.RPath(specifics.local_connection, os.path.join(TEST_BASE_DIR, b"new"))
    new2 = rpath.RPath(specifics.local_connection, os.path.join(TEST_BASE_DIR, b"new2"))
    sig = rpath.RPath(
        specifics.local_connection, os.path.join(TEST_BASE_DIR, b"signature")
    )
    sig2 = rpath.RPath(
        specifics.local_connection, os.path.join(TEST_BASE_DIR, b"signature2")
    )
    delta = rpath.RPath(specifics.local_connection, os.path.join(TEST_BASE_DIR, b"delta"))

    def sig_file_test_helper(self, blocksize, iterations, file_len=None):
        """Compare SigFile output to rdiff output at given blocksize"""
        for i in range(iterations):
            MakeRandomFile(self.basis.path, file_len)
            self._clean_file(self.sig)
            rdiff_help_text = subprocess.check_output(["rdiff", "--help"])
            if b"-R" in rdiff_help_text:
                self.assertEqual(
                    comtst.os_system(
                        (
                            b"rdiff",
                            b"-b",
                            b"%i" % blocksize,
                            b"-R",
                            b"rollsum",
                            b"-S",
                            b"8",
                            b"-H",
                            b"md4",
                            b"signature",
                            self.basis.path,
                            self.sig.path,
                        )
                    ),
                    0,
                )
            elif b"-H" in rdiff_help_text:
                self.assertEqual(
                    comtst.os_system(
                        (
                            b"rdiff",
                            b"-b",
                            b"%i" % blocksize,
                            b"-H",
                            b"md4",
                            b"signature",
                            self.basis.path,
                            self.sig.path,
                        )
                    ),
                    0,
                )
            else:
                self.assertEqual(
                    comtst.os_system(
                        (
                            b"rdiff",
                            b"-b",
                            b"%i" % blocksize,
                            b"signature",
                            self.basis.path,
                            self.sig.path,
                        )
                    ),
                    0,
                )
            with self.sig.open("rb") as fp:
                rdiff_sig = fp.read()

            sf = librsync.SigFile(self.basis.open("rb"), blocksize)
            librsync_sig = sf.read()
            sf.close()

            self.assertEqual(rdiff_sig, librsync_sig)

    def _clean_file(self, rp):
        """Make sure the given rpath is properly cleaned"""
        rp.setdata()
        if rp.lstat():
            rp.delete()

    def testSigFile(self):
        """Make sure SigFile generates same data as rdiff, blocksize 512"""
        self.sig_file_test_helper(512, 5)

    def testSigFile2(self):
        """Test SigFile like above, but try various blocksize"""
        self.sig_file_test_helper(2048, 1, 60000)
        self.sig_file_test_helper(7168, 1, 6000)
        self.sig_file_test_helper(204800, 1, 40 * 1024 * 1024)

    def testSigGenerator(self):
        """Test SigGenerator, make sure it's same as SigFile"""
        for i in range(5):
            MakeRandomFile(self.basis.path)

            sf = librsync.SigFile(self.basis.open("rb"))
            sigfile_string = sf.read()
            sf.close()

            sig_gen = librsync.SigGenerator()
            with self.basis.open("rb") as infile:
                while 1:
                    buf = infile.read(1000)
                    if not buf:
                        break
                    sig_gen.update(buf)
                siggen_string = sig_gen.get_sig()

            self.assertEqual(sigfile_string, siggen_string)

    def OldtestDelta(self):
        """Test delta generation against Rdiff"""
        MakeRandomFile(self.basis.path)
        self.assertEqual(
            comtst.os_system((b"rdiff", b"signature", self.basis.path, self.sig.path)),
            0,
        )
        for i in range(5):
            MakeRandomFile(self.new.path)
            self.assertEqual(
                comtst.os_system(
                    (b"rdiff", b"delta", self.sig.path, self.new.path, self.delta.path)
                ),
                0,
            )
            fp = self.delta.open("rb")
            rdiff_delta = fp.read()
            fp.close()

            df = librsync.DeltaFile(self.sig.open("rb"), self.new.open("rb"))
            librsync_delta = df.read()
            df.close()

            print(len(rdiff_delta), len(librsync_delta))
            print(repr(rdiff_delta[:100]))
            print(repr(librsync_delta[:100]))
            self.assertEqual(rdiff_delta, librsync_delta)

    def testDelta(self):
        """Test delta generation by making sure rdiff can process output

        There appears to be some indeterminism so we can't just
        byte-compare the deltas produced by rdiff and DeltaFile.

        """
        MakeRandomFile(self.basis.path)
        self._clean_file(self.sig)
        self.assertEqual(
            comtst.os_system((b"rdiff", b"signature", self.basis.path, self.sig.path)),
            0,
        )
        for i in range(5):
            MakeRandomFile(self.new.path)
            df = librsync.DeltaFile(self.sig.open("rb"), self.new.open("rb"))
            librsync_delta = df.read()
            df.close()
            fp = self.delta.open("wb")
            fp.write(librsync_delta)
            fp.close()

            self._clean_file(self.new2)
            self.assertEqual(
                comtst.os_system(
                    (
                        b"rdiff",
                        b"patch",
                        self.basis.path,
                        self.delta.path,
                        self.new2.path,
                    )
                ),
                0,
            )
            new_fp = self.new.open("rb")
            new = new_fp.read()
            new_fp.close()

            new2_fp = self.new2.open("rb")
            new2 = new2_fp.read()
            new2_fp.close()

            self.assertEqual(new, new2)

    def testPatch(self):
        """Test patching against Rdiff"""
        MakeRandomFile(self.basis.path)
        self._clean_file(self.sig)
        self.assertEqual(
            comtst.os_system((b"rdiff", b"signature", self.basis.path, self.sig.path)),
            0,
        )
        for i in range(5):
            MakeRandomFile(self.new.path)
            self._clean_file(self.delta)
            self.assertEqual(
                comtst.os_system(
                    (b"rdiff", b"delta", self.sig.path, self.new.path, self.delta.path)
                ),
                0,
            )
            fp = self.new.open("rb")
            real_new = fp.read()
            fp.close()

            pf = librsync.PatchedFile(self.basis.open("rb"), self.delta.open("rb"))
            librsync_new = pf.read()
            pf.close()

            self.assertEqual(real_new, librsync_new)


if __name__ == "__main__":
    unittest.main()
