import unittest
import random
import subprocess
import os
from commontest import abs_test_dir
from rdiff_backup import Globals, librsync, rpath


def MakeRandomFile(path, length=None):
    """Writes a random file of given length, or random len if unspecified"""
    if not length:
        length = random.randrange(5000, 100000)
    fp = open(path, "wb")
    fp_random = open('/dev/urandom', 'rb')

    fp.write(fp_random.read(length))

    fp.close()
    fp_random.close()


class LibrsyncTest(unittest.TestCase):
    """Test various librsync wrapper functions"""
    basis = rpath.RPath(Globals.local_connection, os.path.join(abs_test_dir, b"basis"))
    new = rpath.RPath(Globals.local_connection, os.path.join(abs_test_dir, b"new"))
    new2 = rpath.RPath(Globals.local_connection, os.path.join(abs_test_dir, b"new2"))
    sig = rpath.RPath(Globals.local_connection, os.path.join(abs_test_dir, b"signature"))
    sig2 = rpath.RPath(Globals.local_connection, os.path.join(abs_test_dir, b"signature2"))
    delta = rpath.RPath(Globals.local_connection, os.path.join(abs_test_dir, b"delta"))

    def sig_file_test_helper(self, blocksize, iterations, file_len=None):
        """Compare SigFile output to rdiff output at given blocksize"""
        for i in range(iterations):
            MakeRandomFile(self.basis.path, file_len)
            self._clean_file(self.sig)
            if b'-H' in subprocess.check_output(["rdiff", "--help"]):
                assert not os.system(
                    b"rdiff -b %i -H md4 signature %b %b" %
                    (blocksize, self.basis.path, self.sig.path))
            else:
                assert not os.system(
                    b"rdiff -b %i signature %b %b" %
                    (blocksize, self.basis.path, self.sig.path))
            with self.sig.open("rb") as fp:
                rdiff_sig = fp.read()

            sf = librsync.SigFile(self.basis.open("rb"), blocksize)
            librsync_sig = sf.read()
            sf.close()

            assert rdiff_sig == librsync_sig, \
                (len(rdiff_sig), len(librsync_sig))

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
                siggen_string = sig_gen.getsig()

            assert sigfile_string == siggen_string, \
                (len(sigfile_string), len(siggen_string))

    def OldtestDelta(self):
        """Test delta generation against Rdiff"""
        MakeRandomFile(self.basis.path)
        assert not os.system(b"rdiff signature %s %s" %
                             (self.basis.path, self.sig.path))
        for i in range(5):
            MakeRandomFile(self.new.path)
            assert not os.system(
                b"rdiff delta %b %b %b" %
                (self.sig.path, self.new.path, self.delta.path))
            fp = self.delta.open("rb")
            rdiff_delta = fp.read()
            fp.close()

            df = librsync.DeltaFile(self.sig.open("rb"), self.new.open("rb"))
            librsync_delta = df.read()
            df.close()

            print(len(rdiff_delta), len(librsync_delta))
            print(repr(rdiff_delta[:100]))
            print(repr(librsync_delta[:100]))
            assert rdiff_delta == librsync_delta

    def testDelta(self):
        """Test delta generation by making sure rdiff can process output

        There appears to be some indeterminism so we can't just
        byte-compare the deltas produced by rdiff and DeltaFile.

        """
        MakeRandomFile(self.basis.path)
        self._clean_file(self.sig)
        assert not os.system(b"rdiff signature %s %s" %
                             (self.basis.path, self.sig.path))
        for i in range(5):
            MakeRandomFile(self.new.path)
            df = librsync.DeltaFile(self.sig.open("rb"), self.new.open("rb"))
            librsync_delta = df.read()
            df.close()
            fp = self.delta.open("wb")
            fp.write(librsync_delta)
            fp.close()

            self._clean_file(self.new2)
            assert not os.system(
                b"rdiff patch %s %s %s" %
                (self.basis.path, self.delta.path, self.new2.path))
            new_fp = self.new.open("rb")
            new = new_fp.read()
            new_fp.close()

            new2_fp = self.new2.open("rb")
            new2 = new2_fp.read()
            new2_fp.close()

            assert new == new2, (len(new), len(new2))

    def testPatch(self):
        """Test patching against Rdiff"""
        MakeRandomFile(self.basis.path)
        self._clean_file(self.sig)
        assert not os.system(b"rdiff signature %s %s" %
                             (self.basis.path, self.sig.path))
        for i in range(5):
            MakeRandomFile(self.new.path)
            self._clean_file(self.delta)
            assert not os.system(
                b"rdiff delta %s %s %s" %
                (self.sig.path, self.new.path, self.delta.path))
            fp = self.new.open("rb")
            real_new = fp.read()
            fp.close()

            pf = librsync.PatchedFile(self.basis.open("rb"),
                                      self.delta.open("rb"))
            librsync_new = pf.read()
            pf.close()

            assert real_new == librsync_new, \
                (len(real_new), len(librsync_new))


if __name__ == "__main__":
    unittest.main()
