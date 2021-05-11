import unittest
import io
import os
import sys
from commontest import iter_equal, abs_output_dir, Myrm
from rdiff_backup import rpath, Globals
from rdiff_backup.iterfile import IterWrappingFile, FileWrappingIter, \
    FileToMiscIter, MiscIterToFile, MiscIterFlush, MiscIterFlushRepeat


class FileException:
    """Like a file, but raise exception after certain # bytes read"""

    def __init__(self, max):
        self.count = 0
        self.max = max

    def read(self, chars):
        self.count += chars
        if self.count > self.max:
            raise OSError(13, "Permission Denied")
        return b"a" * chars

    def close(self):
        return None


class testIterFile(unittest.TestCase):
    def setUp(self):
        self.iter1maker = lambda: iter(list(range(50)))
        self.iter2maker = lambda: iter(map(str, list(range(50))))

    def testConversion(self):
        """Test iter to file conversion"""
        for itm in [self.iter1maker, self.iter2maker]:
            self.assertTrue(
                iter_equal(itm(), IterWrappingFile(FileWrappingIter(itm()))))

    def testFile(self):
        """Test sending files through iters"""
        buf1 = b"hello" * 10000
        file1 = io.BytesIO(buf1)
        buf2 = b"goodbye" * 10000
        file2 = io.BytesIO(buf2)
        file_iter = FileWrappingIter(iter([file1, file2]))

        new_iter = IterWrappingFile(file_iter)
        self.assertEqual(next(new_iter).read(), buf1)
        self.assertEqual(next(new_iter).read(), buf2)

        self.assertRaises(StopIteration, new_iter.__next__)

    def testFileException(self):
        """Test encoding a file which raises an exception"""
        f = FileException(200 * 1024)  # size depends on buffer size
        new_iter = IterWrappingFile(FileWrappingIter(iter([f, b"foo"])))
        f_out = next(new_iter)
        self.assertEqual(f_out.read(50000), b"a" * 50000)
        with self.assertRaises(OSError):
            buf = f_out.read(190 * 1024)  # noqa: F841

        self.assertEqual(next(new_iter), b"foo")
        self.assertRaises(StopIteration, new_iter.__next__)


class testMiscIters(unittest.TestCase):
    """Test sending rorpiter back and forth"""

    def setUp(self):
        """Make testfiles/output directory and a few files"""
        Myrm(abs_output_dir)
        self.outputrp = rpath.RPath(Globals.local_connection, abs_output_dir)
        self.regfile1 = self.outputrp.append("reg1")
        self.regfile2 = self.outputrp.append("reg2")
        self.regfile3 = self.outputrp.append("reg3")

        self.outputrp.mkdir()

        with self.regfile1.open("wb") as fp:
            fp.write(b"hello")
        self.regfile1.setfile(self.regfile1.open("rb"))

        self.regfile2.touch()
        self.regfile2.setfile(self.regfile2.open("rb"))

        with self.regfile3.open("wb") as fp:
            fp.write(b"goodbye")
        self.regfile3.setfile(self.regfile3.open("rb"))

        self.regfile1.setdata()
        self.regfile2.setdata()
        self.regfile3.setdata()

    def print_MiscIterFile(self, rpiter_file):
        """Print the given rorpiter file"""
        while 1:
            buf = rpiter_file.read()
            sys.stdout.write(buf)
            if buf[0] == b"z":
                break

    def testBasic(self):
        """Test basic conversion"""
        rplist = [self.outputrp, self.regfile1, self.regfile2, self.regfile3]
        i_out = FileToMiscIter(MiscIterToFile(iter(rplist)))

        out1 = next(i_out)
        self.assertEqual(out1, self.outputrp)

        out2 = next(i_out)
        self.assertEqual(out2, self.regfile1)
        fp = out2.open("rb")
        self.assertEqual(fp.read(), b"hello")
        self.assertFalse(fp.close())

        out3 = next(i_out)
        self.assertEqual(out3, self.regfile2)
        fp = out3.open("rb")
        self.assertEqual(fp.read(), b"")
        self.assertFalse(fp.close())

        next(i_out)
        self.assertRaises(StopIteration, i_out.__next__)

    @unittest.skipIf(os.name == "nt", "FIXME fails under Windows")
    def testMix(self):
        """Test a mix of RPs and ordinary objects"""
        filelist = [5, self.regfile3, "hello"]
        s = MiscIterToFile(iter(filelist)).read()
        i_out = FileToMiscIter(io.BytesIO(s))

        out1 = next(i_out)
        self.assertEqual(out1, 5)

        out2 = next(i_out)
        self.assertEqual(out2, self.regfile3)
        fp = out2.open("rb")
        self.assertEqual(fp.read(), b"goodbye")
        self.assertFalse(fp.close())

        out3 = next(i_out)
        self.assertEqual(out3, "hello")

        self.assertRaises(StopIteration, i_out.__next__)

    def testFlush(self):
        """Test flushing property of MiscIterToFile"""
        rplist = [self.outputrp, MiscIterFlush, self.outputrp]
        filelike = MiscIterToFile(iter(rplist))
        new_filelike = io.BytesIO(
            (filelike.read() + b"z" + filelike._i2b(0, 7)))

        i_out = FileToMiscIter(new_filelike)
        self.assertEqual(next(i_out), self.outputrp)
        self.assertRaises(StopIteration, i_out.__next__)

        i_out2 = FileToMiscIter(filelike)
        self.assertEqual(next(i_out2), self.outputrp)
        self.assertRaises(StopIteration, i_out2.__next__)

    @unittest.skipIf(os.name == "nt", "FIXME fails under Windows")
    def testFlushRepeat(self):
        """Test flushing like above, but have Flush obj emerge from iter"""
        rplist = [self.outputrp, MiscIterFlushRepeat, self.outputrp]
        filelike = MiscIterToFile(iter(rplist))
        new_filelike = io.BytesIO(
            (filelike.read() + b"z" + filelike._i2b(0, 7)))

        i_out = FileToMiscIter(new_filelike)
        self.assertEqual(next(i_out), self.outputrp)
        self.assertIs(next(i_out), MiscIterFlushRepeat)
        self.assertRaises(StopIteration, i_out.__next__)

        i_out2 = FileToMiscIter(filelike)
        self.assertEqual(next(i_out2), self.outputrp)
        self.assertRaises(StopIteration, i_out2.__next__)


if __name__ == "__main__":
    unittest.main()
