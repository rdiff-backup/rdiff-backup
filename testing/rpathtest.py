import os
import pickle
import sys
import unittest
import time
from commontest import old_test_dir, abs_test_dir, re_init_subdir, abs_output_dir, \
    re_init_rpath_dir, os_system
from rdiff_backup import Globals, rpath


class RPathTest(unittest.TestCase):
    lc = Globals.local_connection
    mainprefix = old_test_dir
    prefix = os.path.join(mainprefix, b"various_file_types")
    write_dir = re_init_subdir(abs_test_dir, b"rpathtests")
    rp_prefix = rpath.RPath(lc, prefix, ())


class RORPStateTest(RPathTest):
    """Test Pickling of RORPaths"""

    def testPickle(self):
        rorp = rpath.RPath(self.lc, self.prefix, ("regular_file", )).getRORPath()
        rorp.file = sys.stdin  # try to confuse pickler
        self.assertTrue(rorp.isreg())
        rorp2 = pickle.loads(pickle.dumps(rorp, 1))
        self.assertTrue(rorp2.isreg())
        self.assertEqual(rorp2.data, rorp.data)
        self.assertEqual(rorp2.index, rorp.index)


class CheckTypes(RPathTest):
    """Check to see if file types are identified correctly"""

    def testExist(self):
        """Can tell if files exist"""
        self.assertTrue(rpath.RPath(self.lc, self.prefix, ()).lstat())
        self.assertFalse(rpath.RPath(self.lc, "asuthasetuouo", ()).lstat())

    def testDir(self):
        """Directories identified correctly"""
        self.assertTrue(rpath.RPath(self.lc, self.prefix, ()).isdir())
        self.assertFalse(
            rpath.RPath(self.lc, self.prefix, ("regular_file", )).isdir())

    def testSym(self):
        """Symbolic links identified"""
        self.assertTrue(
            rpath.RPath(self.lc, self.prefix, ("symbolic_link", )).issym())
        self.assertFalse(rpath.RPath(self.lc, self.prefix, ()).issym())

    def testReg(self):
        """Regular files identified"""
        self.assertTrue(
            rpath.RPath(self.lc, self.prefix, ("regular_file", )).isreg())
        self.assertFalse(
            rpath.RPath(self.lc, self.prefix, ("symbolic_link", )).isreg())

    @unittest.skipIf(os.name == "nt", "Fifo don't exist under Windows")
    def testFifo(self):
        """Fifo's identified"""
        self.assertTrue(rpath.RPath(self.lc, self.prefix, ("fifo", )).isfifo())
        self.assertFalse(rpath.RPath(self.lc, self.prefix, ()).isfifo())

    @unittest.skipUnless(os.path.exists('/dev/tty2'), "Test requires /dev/tty2")
    def testCharDev(self):
        """Char special files identified"""
        self.assertTrue(rpath.RPath(self.lc, "/dev/tty2", ()).ischardev())
        self.assertFalse(
            rpath.RPath(self.lc, self.prefix, ("regular_file", )).ischardev())

    @unittest.skipUnless(
        os.path.exists('/dev/sda') or os.path.exists('/dev/nvme0n1'),
        "Test requires either /dev/sda or /dev/nvme0n1")
    def testBlockDev(self):
        """Block special files identified"""
        # Introducing a new dependency just for a few tests doesn't sound
        # reasonable, especially as it doesn't solve minor/major questions
        # somediskdev = os.path.realpath(psutil.disk_partitions()[0].device)
        # We assume that anybody must have a hard drive, SSD or NVMe
        if (os.path.exists('/dev/sda')):
            self.assertTrue(rpath.RPath(self.lc, '/dev/sda', ()).isblkdev())
        else:
            self.assertTrue(rpath.RPath(self.lc, '/dev/nvme0n1', ()).isblkdev())
        self.assertFalse(
            rpath.RPath(self.lc, self.prefix, ("regular_file", )).isblkdev())


@unittest.skipIf(os.name == "nt", "Windows doesn't handle well rights")
class CheckPerms(RPathTest):
    """Check to see if permissions are reported and set accurately"""

    def testExecReport(self):
        """Check permissions for executable files"""
        self.assertEqual(self.rp_prefix.append('executable').getperms(), 0o755)
        self.assertEqual(self.rp_prefix.append('executable2').getperms(), 0o700)

    def testhighbits(self):
        """Test reporting of highbit permissions"""
        p = rpath.RPath(self.lc, os.path.join(self.mainprefix, b"rpath2",
                                              b"foobar")).getperms()
        self.assertEqual(p, 0o4100)

    def testOrdinaryReport(self):
        """Ordinary file permissions..."""
        self.assertEqual(
            self.rp_prefix.append("regular_file").getperms(), 0o644)
        self.assertEqual(
            self.rp_prefix.append('two_hardlinked_files1').getperms(), 0o640)

    def testChmod(self):
        """Test changing file permission"""
        rp = self.rp_prefix.append("changeable_permission")
        rp.chmod(0o700)
        self.assertEqual(rp.getperms(), 0o700)
        rp.chmod(0o644)
        self.assertEqual(rp.getperms(), 0o644)

    def testExceptions(self):
        """What happens when file absent"""
        self.assertRaises(
            Exception,
            rpath.RPath(self.lc, self.prefix, ("aoeunto", )).getperms())


class CheckTimes(RPathTest):
    """Check to see if times are reported and set accurately"""

    def testSet(self):
        """Check to see if times set properly"""
        rp = rpath.RPath(self.lc, self.prefix, ("timetest.foo", ))
        rp.touch()
        rp.settime(10000, 20000)
        rp.setdata()
        self.assertEqual(rp.getatime(), 10000)
        self.assertEqual(rp.getmtime(), 20000)
        rp.delete()

    @unittest.skipIf(os.name == "nt", "Windows doesn't handle ctime correctly")
    def testCtime(self):
        """Check to see if ctime read, compared"""
        rp = rpath.RPath(self.lc, self.prefix, ("ctimetest.1", ))
        rp2 = rpath.RPath(self.lc, self.prefix, ("ctimetest.2", ))
        rp.touch()
        rp.chmod(0o700)
        rpath.copy_with_attribs(rp, rp2)
        self.assertTrue(rpath._cmp_file_attribs(rp, rp2))

        time.sleep(1)
        rp2.chmod(0o755)
        rp2.chmod(0o700)
        rp2.setdata()
        self.assertGreater(rp2.getctime(), rp.getctime())
        self.assertFalse(rpath._cmp_file_attribs(rp, rp2))
        rp.delete()
        rp2.delete()


class CheckDir(RPathTest):
    """Check directory related functions"""

    def testCreation(self):
        """Test directory creation and deletion"""
        d = self.rp_prefix.append("tempdir")
        self.assertFalse(d.lstat())
        d.mkdir()
        self.assertTrue(d.isdir())
        d.rmdir()
        self.assertFalse(d.lstat())

    def testExceptions(self):
        """Should raise os.errors when no files"""
        d = rpath.RPath(self.lc, self.prefix, ("suthosutho", ))
        self.assertRaises(os.error, d.rmdir)
        d.mkdir()
        self.assertRaises(os.error, d.mkdir)
        d.rmdir()

    def testListdir(self):
        """Checking dir listings"""
        dirlist = rpath.RPath(self.lc, self.mainprefix,
                              ("sampledir", )).listdir()
        dirlist.sort()
        self.assertEqual(dirlist, [b"1", b"2", b"3", b"4"])


@unittest.skipIf(os.name == "nt", "Symlinks not supported under Windows")
class CheckSyms(RPathTest):
    """Check symlinking and reading"""

    def testRead(self):
        """symlink read"""
        self.assertEqual(
            rpath.RPath(self.lc, self.prefix, ("symbolic_link", )).readlink(),
            b"regular_file")

    def testMake(self):
        """Creating symlink"""
        link = rpath.RPath(self.lc, self.write_dir, ("symlink", ))
        self.assertFalse(link.lstat())
        link.symlink("abcdefg")
        self.assertTrue(link.issym())
        self.assertEqual(link.readlink(), b"abcdefg")
        link.delete()


@unittest.skipIf(os.name == "nt", "Sockets don't exist under Windows")
class CheckSockets(RPathTest):
    """Check reading and making sockets"""

    def testMake(self):
        """Create socket, then read it"""
        sock = rpath.RPath(self.lc, self.write_dir, ("socket", ))
        self.assertFalse(sock.lstat())
        sock.mksock()
        self.assertTrue(sock.issock())
        sock.delete()

    def testLongSock(self):
        """Test making a socket with a long name.
        It shouldn't be an issue anymore on modern systems"""
        sock = rpath.RPath(self.lc, self.write_dir, (
            "socketaoeusthaoeaoeutnhaonseuhtansoeuthasoneuthasoeutnhasonuthaoensuhtasoneuhtsanouhonetuhasoneuthsaoenaonsetuaosenuhtaoensuhaoeu",
        ))
        self.assertFalse(sock.lstat())
        sock.mksock()
        sock.setdata()
        self.assertTrue(sock.lstat())
        sock.delete()


class TouchDelete(RPathTest):
    """Check touching and deletion of files"""

    def testTouch(self):
        """Creation of 0 length files"""
        t = rpath.RPath(self.lc, self.write_dir, ("testtouch", ))
        self.assertFalse(t.lstat())
        t.touch()
        self.assertTrue(t.lstat())
        t.delete()

    def testDelete(self):
        """Deletion of files"""
        d = rpath.RPath(self.lc, self.write_dir, ("testdelete", ))
        d.touch()
        self.assertTrue(d.lstat())
        d.delete()
        self.assertFalse(d.lstat())


class MiscFileInfo(RPathTest):
    """Check Miscellaneous file information"""

    def testFileLength(self):
        """File length = getsize()"""
        self.assertEqual(
            rpath.RPath(self.lc, self.prefix, ("regular_file", )).getsize(),
            75650)


class FilenameOps(RPathTest):
    """Check filename operations"""
    normdict = {
        b"/": b"/",
        b".": b".",
        b"/a/b": b"/a/b",
        b"a/b": b"a/b",
        b"a//b": b"a/b",
        b"a////b//c": b"a/b/c",
        b"..": b"..",
        b"a/": b"a",
        b"/a//b///": b"/a/b",
        b"//host/share": b"//host/share",
        b"//host//share/": b"//host/share",
    }
    if os.name != "nt":  # Windows doesn't like double slashes
        normdict[b"//"] = b"/"
    dirsplitdict = {
        b"/": (b"", b""),
        b"/a": (b"", b"a"),
        b"/a/b": (b"/a", b"b"),
        b".": (b".", b"."),
        b"b/c": (b"b", b"c"),
        b"a": (b".", b"a"),
        b"//host/share": (b"//host", b"share"),
    }

    def testNormalize(self):
        """rpath.normalize() dictionary test"""
        for (before, after) in list(self.normdict.items()):
            self.assertEqual(
                rpath.RPath(self.lc, before, ()).normalize().path, after)

    def testDirsplit(self):
        """Test splitting of various directories"""
        for full, split in list(self.dirsplitdict.items()):
            result = rpath.RPath(self.lc, full, ()).dirsplit()
            self.assertEqual(result, split)

    @unittest.skipUnless(
        (os.path.exists('/dev/sda') or os.path.exists('/dev/nvme0n1'))
        and os.path.exists('/dev/tty2'),
        "Test requires either /dev/sda or /dev/nvme0n1")
    def testGetnums(self):
        """Test getting file numbers"""
        if (os.path.exists(b'/dev/sda')):
            devnums = rpath.RPath(self.lc, b"/dev/sda", ()).getdevnums()
            self.assertEqual(devnums, ('b', 8, 0))
        else:
            devnums = rpath.RPath(self.lc, b"/dev/nvme0n1", ()).getdevnums()
            self.assertEqual(devnums, ('b', 259, 0))
        devnums = rpath.RPath(self.lc, b"/dev/tty2", ()).getdevnums()
        self.assertEqual(devnums, ('c', 4, 2))


class FileIO(RPathTest):
    """Test file input and output"""

    def testRead(self):
        """File reading"""
        with rpath.RPath(self.lc, self.prefix, ("executable", )).open("r") as fp:
            self.assertEqual(fp.read(6), "#!/bin")

    def testWrite(self):
        """File writing"""
        rp = rpath.RPath(self.lc, self.mainprefix, ("testfile", ))
        with rp.open("w") as fp:
            fp.write("hello")
        with rp.open("r") as fp_input:
            self.assertEqual(fp_input.read(), "hello")
        rp.delete()

    def testGzipWrite(self):
        """Test writing of gzipped files"""
        try:
            os.mkdir(abs_output_dir)
        except OSError:
            pass
        file_nogz = os.path.join(abs_output_dir, b"file")
        file_gz = file_nogz + b".gz"
        rp_gz = rpath.RPath(self.lc, file_gz)
        rp_nogz = rpath.RPath(self.lc, file_nogz)
        if rp_nogz.lstat():
            rp_nogz.delete()
        s = b"Hello, world!"

        with rp_gz.open("wb", compress=1) as fp_out:
            fp_out.write(s)
        if os.name == "nt":
            self.assertEqual(
                os_system(b"7z x -o%s %s >NUL" % (abs_output_dir, file_gz)), 0)
            os_system(b"del %s" % file_gz)
        else:
            self.assertEqual(os_system(b"gunzip %s" % file_gz), 0)
        with rp_nogz.open("rb") as fp_in:
            self.assertEqual(fp_in.read(), s)

    def testGzipRead(self):
        """Test reading of gzipped files"""
        try:
            os.mkdir(abs_output_dir)
        except OSError:
            pass
        file_nogz = os.path.join(abs_output_dir, b"file")
        file_gz = file_nogz + b".gz"
        rp_gz = rpath.RPath(self.lc, file_gz)
        if rp_gz.lstat():
            rp_gz.delete()
        rp_nogz = rpath.RPath(self.lc, file_nogz)
        s = "Hello, world!"

        with rp_nogz.open("w") as fp_out:
            fp_out.write(s)
        rp_nogz.setdata()
        self.assertTrue(rp_nogz.lstat())

        if os.name == "nt":
            self.assertEqual(
                os_system(b"7z a -tgzip -sdel %s %s >NUL" % (file_gz,
                                                             file_nogz)),
                0)
        else:
            self.assertEqual(os_system(b"gzip %s" % file_nogz), 0)
        rp_nogz.setdata()
        rp_gz.setdata()
        self.assertFalse(rp_nogz.lstat())
        self.assertTrue(rp_gz.lstat())
        with rp_gz.open("r", compress=1) as fp_in:
            read_s = fp_in.read().decode()  # zip is always binary hence bytes
            self.assertEqual(read_s, s)


class FileCopying(RPathTest):
    """Test file copying and comparison"""

    def setUp(self):
        self.hl1 = rpath.RPath(self.lc, self.prefix, ("two_hardlinked_files1", ))
        self.hl2 = rpath.RPath(self.lc, self.prefix, ("two_hardlinked_files2", ))
        self.sl = rpath.RPath(self.lc, self.prefix, ("symbolic_link", ))
        self.dir = rpath.RPath(self.lc, self.prefix, ())
        self.fifo = rpath.RPath(self.lc, self.prefix, ("fifo", ))
        self.rf = rpath.RPath(self.lc, self.prefix, ("regular_file", ))
        self.dest = rpath.RPath(self.lc, self.mainprefix, ("dest", ))
        if self.dest.lstat():
            self.dest.delete()
        self.assertFalse(self.dest.lstat())

    def testComp(self):
        """Test comparisons involving regular files"""
        self.assertTrue(rpath.cmp(self.hl1, self.hl2))
        self.assertFalse(rpath.cmp(self.rf, self.hl1))
        self.assertFalse(rpath.cmp(self.dir, self.rf))

    @unittest.skipIf(os.name == "nt", "Symlinks not supported under Windows")
    def testCompMisc(self):
        """Test miscellaneous comparisons"""
        self.assertTrue(
            rpath.cmp(self.dir, rpath.RPath(self.lc, self.mainprefix, ())))
        self.dest.symlink("regular_file")
        self.assertTrue(rpath.cmp(self.sl, self.dest))
        self.dest.delete()
        self.assertFalse(rpath.cmp(self.sl, self.fifo))
        self.assertFalse(rpath.cmp(self.dir, self.sl))

    def testDirSizeComp(self):
        """Make sure directories can be equal,
        even if they are of different sizes"""
        smalldir = rpath.RPath(Globals.local_connection,
                               os.path.join(old_test_dir, b"dircomptest", b"1"))
        bigdir = rpath.RPath(Globals.local_connection,
                             os.path.join(old_test_dir, b"dircomptest", b"2"))
        # Can guarantee below by adding files to bigdir
        self.assertGreater(bigdir.getsize(), smalldir.getsize())
        self.assertEqual(smalldir, bigdir)

    def testCopy(self):
        """Test copy of various files"""
        if os.name == "nt":
            comp_list = [self.rf, self.dir]
        else:
            comp_list = [self.sl, self.rf, self.fifo, self.dir]
        for rp in comp_list:
            rpath.copy(rp, self.dest)
            self.assertTrue(self.dest.lstat())
            self.assertTrue(rpath.cmp(rp, self.dest))
            self.assertTrue(rpath.cmp(self.dest, rp))
            self.dest.delete()


class FileAttributes(FileCopying):
    """Test file attribute operations"""

    def setUp(self):
        FileCopying.setUp(self)
        self.noperms = rpath.RPath(self.lc, self.mainprefix, ("noperms", ))
        self.nowrite = rpath.RPath(self.lc, self.mainprefix, ("nowrite", ))
        self.exec1 = rpath.RPath(self.lc, self.prefix, ("executable", ))
        self.exec2 = rpath.RPath(self.lc, self.prefix, ("executable2", ))
        self.test = rpath.RPath(self.lc, self.prefix, ("test", ))
        self.nothing = rpath.RPath(self.lc, self.prefix, ("aoeunthoenuouo", ))
        self.sym = rpath.RPath(self.lc, self.prefix, ("symbolic_link", ))

    def testComp(self):
        """Test attribute comparison success"""
        testpairs = [(self.hl1, self.hl2)]
        for a, b in testpairs:
            self.assertTrue(a.equal_loose(b))
            self.assertTrue(b.equal_loose(a))

    def testCompFail(self):
        """Test attribute comparison failures"""
        testpairs = [(self.nowrite, self.noperms), (self.exec1, self.exec2),
                     (self.rf, self.hl1)]
        for a, b in testpairs:
            self.assertFalse(a.equal_loose(b))
            self.assertFalse(b.equal_loose(a))

    def testCheckRaise(self):
        """Should raise exception when file missing"""
        self.assertRaises(rpath.RPathException, rpath._check_for_files, self.nothing,
                          self.hl1)
        self.assertRaises(rpath.RPathException, rpath._check_for_files, self.hl1,
                          self.nothing)

    def testCopyAttribs(self):
        """Test copying attributes"""
        t = rpath.RPath(self.lc, self.write_dir, ("testattribs", ))
        if t.lstat():
            t.delete()
        for rp in [
                self.noperms, self.nowrite, self.rf, self.exec1, self.exec2,
                self.hl1, self.dir
        ]:
            rpath.copy(rp, t)
            rpath.copy_attribs(rp, t)
            self.assertTrue(t.equal_loose(rp))
            t.delete()

    def testCopyWithAttribs(self):
        """Test copying with attribs (bug found earlier)"""
        out = rpath.RPath(self.lc, self.write_dir, ("out", ))
        if out.lstat():
            out.delete()
        copy_list = [self.noperms, self.nowrite, self.rf,
                     self.exec1, self.exec2, self.hl1, self.dir]
        if os.name != "nt":  # symlinks not supported under Windows
            copy_list.append(self.sym)
        for rp in copy_list:
            rpath.copy_with_attribs(rp, out)
            self.assertTrue(rpath.cmp(rp, out))
            self.assertTrue(rp.equal_loose(out))
            out.delete()

    def testCopyRaise(self):
        """Should raise exception for non-existent files"""
        self.assertRaises(AssertionError, rpath.copy_attribs, self.hl1,
                          self.nothing)
        self.assertRaises(AssertionError, rpath.copy_attribs, self.nothing,
                          self.nowrite)


class CheckPath(unittest.TestCase):
    """Check to make sure paths generated properly"""

    def testpath(self):
        """Test root paths"""
        root = rpath.RPath(Globals.local_connection, "/")
        self.assertEqual(root.path, b"/")
        bin = root.append("bin")
        self.assertEqual(bin.path, b"/bin")
        bin2 = rpath.RPath(Globals.local_connection, "/bin")
        self.assertEqual(bin2.path, b"/bin")


class Gzip(RPathTest):
    """Test the gzip related functions/classes"""

    def test_maybe_gzip(self):
        """Test MaybeGzip"""
        dirrp = rpath.RPath(self.lc, abs_output_dir)
        re_init_rpath_dir(dirrp)

        base_rp = dirrp.append('foo')
        fileobj = rpath.MaybeGzip(base_rp)
        fileobj.close()
        base_rp.setdata()
        self.assertTrue(base_rp.isreg())
        self.assertEqual(base_rp.getsize(), 0)
        base_rp.delete()

        base_gz = dirrp.append('foo.gz')
        self.assertFalse(base_gz.lstat())
        fileobj = rpath.MaybeGzip(base_rp)
        fileobj.write(b"lala")
        fileobj.close()
        base_rp.setdata()
        base_gz.setdata()
        self.assertFalse(base_rp.lstat())
        self.assertTrue(base_gz.isreg())
        data = base_gz.get_bytes(compressed=1)
        self.assertEqual(data, b"lala")


if __name__ == "__main__":
    unittest.main()
