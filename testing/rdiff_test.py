"""
Compare results with call to rdiff utility
"""

import os
import random
import unittest

import commontest as comtst

from rdiff_backup import Rdiff, rpath
from rdiffbackup.singletons import specifics

TEST_BASE_DIR = comtst.get_test_base_dir(__file__)


def MakeRandomFile(path):
    """Writes a random file of length between 10000 and 100000"""
    with open(path, "w", encoding="UTF-8") as fp:
        randseq = []
        for i in range(random.randrange(5000, 30000)):
            randseq.append(chr(random.randrange(256)))
        randstr = "".join(randseq)
        fp.write(randstr)


class RdiffTest(unittest.TestCase):
    """Test rdiff"""

    lc = specifics.local_connection

    basis = rpath.RPath(lc, os.path.join(TEST_BASE_DIR, b"basis"))
    new = rpath.RPath(lc, os.path.join(TEST_BASE_DIR, b"new"))
    output = rpath.RPath(lc, os.path.join(TEST_BASE_DIR, b"output"))
    delta = rpath.RPath(lc, os.path.join(TEST_BASE_DIR, b"delta"))
    signature = rpath.RPath(lc, os.path.join(TEST_BASE_DIR, b"signature"))

    def testRdiffSig(self):
        """Test making rdiff signatures"""
        sig = rpath.RPath(
            self.lc,
            os.path.join(
                comtst.old_test_dir, b"various_file_types", b"regular_file.sig"
            ),
        )
        sigfp = sig.open("rb")
        rfsig = Rdiff.get_signature(
            rpath.RPath(
                self.lc,
                os.path.join(
                    comtst.old_test_dir, b"various_file_types", b"regular_file"
                ),
            ),
            2048,
        )
        self.assertTrue(rpath._cmp_file_obj(sigfp, rfsig))
        sigfp.close()
        rfsig.close()

    def testRdiffDeltaPatch(self):
        """Test making deltas and patching files"""
        rplist = [self.basis, self.new, self.delta, self.signature, self.output]
        for rp in rplist:
            if rp.lstat():
                rp.delete()

        for i in range(2):
            MakeRandomFile(self.basis.path)
            MakeRandomFile(self.new.path)
            list(map(rpath.RPath.setdata, [self.basis, self.new]))
            self.assertTrue(self.basis.lstat() and self.new.lstat())
            self.signature.write_from_fileobj(Rdiff.get_signature(self.basis))
            self.assertTrue(self.signature.lstat())
            self.delta.write_from_fileobj(
                Rdiff.get_delta_sigrp_hash(self.signature, self.new)
            )
            self.assertTrue(self.delta.lstat())
            Rdiff.patch_local(self.basis, self.delta, self.output)
            self.assertTrue(rpath.cmp(self.new, self.output))
            list(map(rpath.RPath.delete, rplist))

    def testRdiffDeltaPatchGzip(self):
        """Same as above by try gzipping patches"""
        rplist = [self.basis, self.new, self.delta, self.signature, self.output]
        for rp in rplist:
            if rp.lstat():
                rp.delete()

        MakeRandomFile(self.basis.path)
        MakeRandomFile(self.new.path)
        list(map(rpath.RPath.setdata, [self.basis, self.new]))
        self.assertTrue(self.basis.lstat() and self.new.lstat())
        self.signature.write_from_fileobj(Rdiff.get_signature(self.basis))
        self.assertTrue(self.signature.lstat())
        self.delta.write_from_fileobj(
            Rdiff.get_delta_sigrp_hash(self.signature, self.new)
        )
        self.assertTrue(self.delta.lstat())
        gzip_path = self.delta.path + b".gz"
        if os.name == "nt":
            # simulate gzip using 7z on Windows
            comtst.os_system(
                (
                    b"7z",
                    b"a",
                    b"-tgzip",
                    b"-sdel",
                    b"-bb0",
                    b"-y",
                    gzip_path,
                    self.delta.path,
                )
            )
        else:
            comtst.os_system((b"gzip", self.delta.path))
        os.rename(gzip_path, self.delta.path)
        self.delta.setdata()

        Rdiff.patch_local(self.basis, self.delta, self.output, delta_compressed=1)
        self.assertTrue(rpath.cmp(self.new, self.output))
        list(map(rpath.RPath.delete, rplist))

    def testWriteDelta(self):
        """Test write delta feature of rdiff"""
        if self.delta.lstat():
            self.delta.delete()
        rplist = [self.basis, self.new, self.delta, self.output]
        MakeRandomFile(self.basis.path)
        MakeRandomFile(self.new.path)
        list(map(rpath.RPath.setdata, [self.basis, self.new]))
        self.assertTrue(self.basis.lstat() and self.new.lstat())

        Rdiff.write_delta(self.basis, self.new, self.delta)
        self.assertTrue(self.delta.lstat())
        Rdiff.patch_local(self.basis, self.delta, self.output)
        self.assertTrue(rpath.cmp(self.new, self.output))
        list(map(rpath.RPath.delete, rplist))

    def testWriteDeltaGzip(self):
        """Same as above but delta is written gzipped"""
        rplist = [self.basis, self.new, self.delta, self.output]
        MakeRandomFile(self.basis.path)
        MakeRandomFile(self.new.path)
        list(map(rpath.RPath.setdata, [self.basis, self.new]))
        self.assertTrue(self.basis.lstat() and self.new.lstat())
        delta_gz = rpath.RPath(self.delta.conn, self.delta.path + b".gz")
        if delta_gz.lstat():
            delta_gz.delete()

        Rdiff.write_delta(self.basis, self.new, delta_gz, 1)
        self.assertTrue(delta_gz.lstat())
        if os.name == "nt":
            # simulate gunzip using 7z on Windows
            comtst.os_system(
                (
                    b"7z",
                    b"e",
                    b"-tgzip",
                    b"-bb0",
                    b"-y",
                    b"-o%b" % os.fspath(delta_gz.get_parent_rp()),
                    os.fspath(delta_gz),
                )
            )
            delta_gz.delete()
        else:
            comtst.os_system((b"gunzip", delta_gz.path))
        delta_gz.setdata()
        self.delta.setdata()
        Rdiff.patch_local(self.basis, self.delta, self.output)
        self.assertTrue(rpath.cmp(self.new, self.output))
        list(map(rpath.RPath.delete, rplist))

    @unittest.skipIf(os.name == "nt", "FIXME fails under Windows")
    def testRdiffRename(self):
        """Rdiff replacing original file with patch outfile"""
        rplist = [self.basis, self.new, self.delta, self.signature]
        for rp in rplist:
            if rp.lstat():
                rp.delete()

        MakeRandomFile(self.basis.path)
        MakeRandomFile(self.new.path)
        list(map(rpath.RPath.setdata, [self.basis, self.new]))
        self.assertTrue(self.basis.lstat() and self.new.lstat())
        self.signature.write_from_fileobj(Rdiff.get_signature(self.basis))
        self.assertTrue(self.signature.lstat())
        self.delta.write_from_fileobj(
            Rdiff.get_delta_sigrp_hash(self.signature, self.new)
        )
        self.assertTrue(self.delta.lstat())
        Rdiff.patch_local(self.basis, self.delta)
        self.assertTrue(rpath.cmp(self.basis, self.new))
        list(map(rpath.RPath.delete, rplist))


if __name__ == "__main__":
    unittest.main()
