import unittest
import random
import os
from commontest import abs_test_dir, old_test_dir, abs_output_dir
from rdiff_backup import Globals, Rdiff, rpath


def MakeRandomFile(path):
    """Writes a random file of length between 10000 and 100000"""
    with open(path, "w") as fp:
        randseq = []
        for i in range(random.randrange(5000, 30000)):
            randseq.append(chr(random.randrange(256)))
        fp.write("".join(randseq))


class RdiffTest(unittest.TestCase):
    """Test rdiff"""
    lc = Globals.local_connection

    basis = rpath.RPath(lc, os.path.join(abs_test_dir, b"basis"))
    new = rpath.RPath(lc, os.path.join(abs_test_dir, b"new"))
    output = rpath.RPath(lc, abs_output_dir)
    delta = rpath.RPath(lc, os.path.join(abs_test_dir, b"delta"))
    signature = rpath.RPath(lc, os.path.join(abs_test_dir, b"signature"))

    def testRdiffSig(self):
        """Test making rdiff signatures"""
        sig = rpath.RPath(
            self.lc,
            os.path.join(old_test_dir, b"various_file_types",
                         b"regular_file.sig"))
        sigfp = sig.open("rb")
        rfsig = Rdiff.get_signature(
            rpath.RPath(
                self.lc,
                os.path.join(old_test_dir, b"various_file_types",
                             b"regular_file")), 2048)
        assert rpath.cmpfileobj(sigfp, rfsig)
        sigfp.close()
        rfsig.close()

    def testRdiffDeltaPatch(self):
        """Test making deltas and patching files"""
        rplist = [
            self.basis, self.new, self.delta, self.signature, self.output
        ]
        for rp in rplist:
            if rp.lstat():
                rp.delete()

        for i in range(2):
            MakeRandomFile(self.basis.path)
            MakeRandomFile(self.new.path)
            list(map(rpath.RPath.setdata, [self.basis, self.new]))
            assert self.basis.lstat() and self.new.lstat()
            self.signature.write_from_fileobj(Rdiff.get_signature(self.basis))
            assert self.signature.lstat()
            self.delta.write_from_fileobj(
                Rdiff.get_delta_sigrp(self.signature, self.new))
            assert self.delta.lstat()
            Rdiff.patch_local(self.basis, self.delta, self.output)
            assert rpath.cmp(self.new, self.output)
            list(map(rpath.RPath.delete, rplist))

    def testRdiffDeltaPatchGzip(self):
        """Same as above by try gzipping patches"""
        rplist = [
            self.basis, self.new, self.delta, self.signature, self.output
        ]
        for rp in rplist:
            if rp.lstat():
                rp.delete()

        MakeRandomFile(self.basis.path)
        MakeRandomFile(self.new.path)
        list(map(rpath.RPath.setdata, [self.basis, self.new]))
        assert self.basis.lstat() and self.new.lstat()
        self.signature.write_from_fileobj(Rdiff.get_signature(self.basis))
        assert self.signature.lstat()
        self.delta.write_from_fileobj(
            Rdiff.get_delta_sigrp(self.signature, self.new))
        assert self.delta.lstat()
        os.system(b"gzip %s" % self.delta.path)
        os.system(b"mv %s.gz %s" % (self.delta.path, self.delta.path))
        self.delta.setdata()

        Rdiff.patch_local(self.basis,
                          self.delta,
                          self.output,
                          delta_compressed=1)
        assert rpath.cmp(self.new, self.output)
        list(map(rpath.RPath.delete, rplist))

    def testWriteDelta(self):
        """Test write delta feature of rdiff"""
        if self.delta.lstat():
            self.delta.delete()
        rplist = [self.basis, self.new, self.delta, self.output]
        MakeRandomFile(self.basis.path)
        MakeRandomFile(self.new.path)
        list(map(rpath.RPath.setdata, [self.basis, self.new]))
        assert self.basis.lstat() and self.new.lstat()

        Rdiff.write_delta(self.basis, self.new, self.delta)
        assert self.delta.lstat()
        Rdiff.patch_local(self.basis, self.delta, self.output)
        assert rpath.cmp(self.new, self.output)
        list(map(rpath.RPath.delete, rplist))

    def testWriteDeltaGzip(self):
        """Same as above but delta is written gzipped"""
        rplist = [self.basis, self.new, self.delta, self.output]
        MakeRandomFile(self.basis.path)
        MakeRandomFile(self.new.path)
        list(map(rpath.RPath.setdata, [self.basis, self.new]))
        assert self.basis.lstat() and self.new.lstat()
        delta_gz = rpath.RPath(self.delta.conn, self.delta.path + b".gz")
        if delta_gz.lstat():
            delta_gz.delete()

        Rdiff.write_delta(self.basis, self.new, delta_gz, 1)
        assert delta_gz.lstat()
        os.system(b"gunzip %s" % delta_gz.path)
        delta_gz.setdata()
        self.delta.setdata()
        Rdiff.patch_local(self.basis, self.delta, self.output)
        assert rpath.cmp(self.new, self.output)
        list(map(rpath.RPath.delete, rplist))

    def testRdiffRename(self):
        """Rdiff replacing original file with patch outfile"""
        rplist = [self.basis, self.new, self.delta, self.signature]
        for rp in rplist:
            if rp.lstat():
                rp.delete()

        MakeRandomFile(self.basis.path)
        MakeRandomFile(self.new.path)
        list(map(rpath.RPath.setdata, [self.basis, self.new]))
        assert self.basis.lstat() and self.new.lstat()
        self.signature.write_from_fileobj(Rdiff.get_signature(self.basis))
        assert self.signature.lstat()
        self.delta.write_from_fileobj(
            Rdiff.get_delta_sigrp(self.signature, self.new))
        assert self.delta.lstat()
        Rdiff.patch_local(self.basis, self.delta)
        assert rpath.cmp(self.basis, self.new)
        list(map(rpath.RPath.delete, rplist))

    def testCopy(self):
        """Using rdiff to copy two files"""
        rplist = [self.basis, self.new]
        for rp in rplist:
            if rp.lstat():
                rp.delete()

        MakeRandomFile(self.basis.path)
        MakeRandomFile(self.new.path)
        list(map(rpath.RPath.setdata, rplist))
        Rdiff.copy_local(self.basis, self.new)
        assert rpath.cmp(self.basis, self.new)
        list(map(rpath.RPath.delete, rplist))


if __name__ == '__main__':
    unittest.main()
