import os
import pickle
import sys
import unittest
import time
from commontest import old_test_dir, abs_test_dir, re_init_subdir, abs_output_dir, \
    re_init_rpath_dir
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
        assert rorp.isreg()
        rorp2 = pickle.loads(pickle.dumps(rorp, 1))
        assert rorp2.isreg()
        assert rorp2.data == rorp.data and rorp.index == rorp2.index


class CheckTypes(RPathTest):
    """Check to see if file types are identified correctly"""

    def testExist(self):
        """Can tell if files exist"""
        assert rpath.RPath(self.lc, self.prefix, ()).lstat()
        assert not rpath.RPath(self.lc, "asuthasetuouo", ()).lstat()

    def testDir(self):
        """Directories identified correctly"""
        assert rpath.RPath(self.lc, self.prefix, ()).isdir()
        assert not rpath.RPath(self.lc, self.prefix, ("regular_file", )).isdir()

    def testSym(self):
        """Symbolic links identified"""
        assert rpath.RPath(self.lc, self.prefix, ("symbolic_link", )).issym()
        assert not rpath.RPath(self.lc, self.prefix, ()).issym()

    def testReg(self):
        """Regular files identified"""
        assert rpath.RPath(self.lc, self.prefix, ("regular_file", )).isreg()
        assert not rpath.RPath(self.lc, self.prefix, ("symbolic_link", )).isreg()

    def testFifo(self):
        """Fifo's identified"""
        assert rpath.RPath(self.lc, self.prefix, ("fifo", )).isfifo()
        assert not rpath.RPath(self.lc, self.prefix, ()).isfifo()

    @unittest.skipUnless(os.path.exists('/dev/tty2'), "Test requires /dev/tty2")
    def testCharDev(self):
        """Char special files identified"""
        assert rpath.RPath(self.lc, "/dev/tty2", ()).ischardev()
        assert not rpath.RPath(self.lc, self.prefix, ("regular_file", )).ischardev()

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
            assert rpath.RPath(self.lc, '/dev/sda', ()).isblkdev()
        else:
            assert rpath.RPath(self.lc, '/dev/nvme0n1', ()).isblkdev()
        assert not rpath.RPath(self.lc, self.prefix, ("regular_file", )).isblkdev()


class CheckPerms(RPathTest):
    """Check to see if permissions are reported and set accurately"""

    def testExecReport(self):
        """Check permissions for executable files"""
        assert self.rp_prefix.append('executable').getperms() == 0o755
        assert self.rp_prefix.append('executable2').getperms() == 0o700

    def testhighbits(self):
        """Test reporting of highbit permissions"""
        p = rpath.RPath(self.lc, os.path.join(self.mainprefix, b"rpath2",
                                              b"foobar")).getperms()
        assert p == 0o4100, p

    def testOrdinaryReport(self):
        """Ordinary file permissions..."""
        assert self.rp_prefix.append("regular_file").getperms() == 0o644
        assert self.rp_prefix.append(
            'two_hardlinked_files1').getperms() == 0o640

    def testChmod(self):
        """Test changing file permission"""
        rp = self.rp_prefix.append("changeable_permission")
        rp.chmod(0o700)
        assert rp.getperms() == 0o700
        rp.chmod(0o644)
        assert rp.getperms() == 0o644

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
        assert rp.getatime() == 10000
        assert rp.getmtime() == 20000
        rp.delete()

    def testCtime(self):
        """Check to see if ctime read, compared"""
        rp = rpath.RPath(self.lc, self.prefix, ("ctimetest.1", ))
        rp2 = rpath.RPath(self.lc, self.prefix, ("ctimetest.2", ))
        rp.touch()
        rp.chmod(0o700)
        rpath.copy_with_attribs(rp, rp2)
        assert rpath.cmp_attribs(rp, rp2)

        time.sleep(1)
        rp2.chmod(0o755)
        rp2.chmod(0o700)
        rp2.setdata()
        assert rp2.getctime() > rp.getctime()
        assert not rpath.cmp_attribs(rp, rp2)
        rp.delete()
        rp2.delete()


class CheckDir(RPathTest):
    """Check directory related functions"""

    def testCreation(self):
        """Test directory creation and deletion"""
        d = self.rp_prefix.append("tempdir")
        assert not d.lstat()
        d.mkdir()
        assert d.isdir()
        d.rmdir()
        assert not d.lstat()

    def testExceptions(self):
        """Should raise os.errors when no files"""
        d = rpath.RPath(self.lc, self.prefix, ("suthosutho", ))
        self.assertRaises(os.error, d.rmdir)
        d.mkdir()
        self.assertRaises(os.error, d.mkdir)
        d.rmdir()

    def testListdir(self):
        """Checking dir listings"""
        dirlist = rpath.RPath(self.lc, self.mainprefix, ("sampledir", )).listdir()
        dirlist.sort()
        assert dirlist == [b"1", b"2", b"3", b"4"], dirlist


class CheckSyms(RPathTest):
    """Check symlinking and reading"""

    def testRead(self):
        """symlink read"""
        assert (rpath.RPath(self.lc, self.prefix,
                            ("symbolic_link", )).readlink() == b"regular_file")

    def testMake(self):
        """Creating symlink"""
        link = rpath.RPath(self.lc, self.write_dir, ("symlink", ))
        assert not link.lstat()
        link.symlink("abcdefg")
        assert link.issym()
        assert link.readlink() == b"abcdefg"
        link.delete()


class CheckSockets(RPathTest):
    """Check reading and making sockets"""

    def testMake(self):
        """Create socket, then read it"""
        sock = rpath.RPath(self.lc, self.write_dir, ("socket", ))
        assert not sock.lstat()
        sock.mksock()
        assert sock.issock()
        sock.delete()

    def testLongSock(self):
        """Test making a socket with a long name

        On some systems, the name of a socket is restricted, and
        cannot be as long as a regular file.  When this happens, a
        SkipFileException should be raised.

        """
        sock = rpath.RPath(self.lc, self.write_dir, (
            "socketaoeusthaoeaoeutnhaonseuhtansoeuthasoneuthasoeutnhasonuthaoensuhtasoneuhtsanouhonetuhasoneuthsaoenaonsetuaosenuhtaoensuhaoeu",
        ))
        assert not sock.lstat()
        try:
            sock.mksock()
        except rpath.SkipFileException:
            pass
        else:
            print("Warning, making long socket did not fail")
        sock.setdata()
        if sock.lstat():
            sock.delete()


class TouchDelete(RPathTest):
    """Check touching and deletion of files"""

    def testTouch(self):
        """Creation of 0 length files"""
        t = rpath.RPath(self.lc, self.write_dir, ("testtouch", ))
        assert not t.lstat()
        t.touch()
        assert t.lstat()
        t.delete()

    def testDelete(self):
        """Deletion of files"""
        d = rpath.RPath(self.lc, self.write_dir, ("testdelete", ))
        d.touch()
        assert d.lstat()
        d.delete()
        assert not d.lstat()


class MiscFileInfo(RPathTest):
    """Check Miscellaneous file information"""

    def testFileLength(self):
        """File length = getsize()"""
        assert (rpath.RPath(self.lc, self.prefix,
                            ("regular_file", )).getsize() == 75650)


class FilenameOps(RPathTest):
    """Check filename operations"""
    weirdfilename = eval(
        '\'\\xd8\\xab\\xb1Wb\\xae\\xc5]\\x8a\\xbb\\x15v*\\xf4\\x0f!\\xf9>\\xe2Y\\x86\\xbb\\xab\\xdbp\\xb0\\x84\\x13k\\x1d\\xc2\\xf1\\xf5e\\xa5U\\x82\\x9aUV\\xa0\\xf4\\xdf4\\xba\\xfdX\\x03\\x82\\x07s\\xce\\x9e\\x8b\\xb34\\x04\\x9f\\x17 \\xf4\\x8f\\xa6\\xfa\\x97\\xab\\xd8\\xac\\xda\\x85\\xdcKvC\\xfa#\\x94\\x92\\x9e\\xc9\\xb7\\xc3_\\x0f\\x84g\\x9aB\\x11<=^\\xdbM\\x13\\x96c\\x8b\\xa7|*"\\\\\\\'^$@#!(){}?+ ~` \''
    )
    normdict = {
        b"/": b"/",
        b".": b".",
        b"//": b"/",
        b"/a/b": b"/a/b",
        b"a/b": b"a/b",
        b"a//b": b"a/b",
        b"a////b//c": b"a/b/c",
        b"..": b"..",
        b"a/": b"a",
        b"/a//b///": b"/a/b"
    }
    dirsplitdict = {
        b"/": (b"", b""),
        b"/a": (b"", b"a"),
        b"/a/b": (b"/a", b"b"),
        b".": (b".", b"."),
        b"b/c": (b"b", b"c"),
        b"a": (b".", b"a")
    }

    def testQuote(self):
        """See if filename quoting works"""
        wtf = rpath.RPath(self.lc, self.prefix, (self.weirdfilename, ))
        reg = rpath.RPath(self.lc, self.prefix, (b"regular_file", ))
        assert wtf.lstat()
        assert reg.lstat()
        assert not os.system(b"ls %s >/dev/null 2>&1" % wtf.quote())
        assert not os.system(b"ls %s >/dev/null 2>&1" % reg.quote())

    def testNormalize(self):
        """rpath.normalize() dictionary test"""
        for (before, after) in list(self.normdict.items()):
            assert rpath.RPath(self.lc, before, ()).normalize().path == after, \
                "Normalize fails for %a => %a" % (before, after)

    def testDirsplit(self):
        """Test splitting of various directories"""
        for full, split in list(self.dirsplitdict.items()):
            result = rpath.RPath(self.lc, full, ()).dirsplit()
            assert result == split, \
                "%s => %s instead of %s" % (full, result, split)

    @unittest.skipUnless(
        (os.path.exists('/dev/sda') or os.path.exists('/dev/nvme0n1'))
        and os.path.exists('/dev/tty2'),
        "Test requires either /dev/sda or /dev/nvme0n1")
    def testGetnums(self):
        """Test getting file numbers"""
        if (os.path.exists(b'/dev/sda')):
            devnums = rpath.RPath(self.lc, b"/dev/sda", ()).getdevnums()
            assert devnums == (8, 0), devnums
        else:
            devnums = rpath.RPath(self.lc, b"/dev/nvme0n1", ()).getdevnums()
            assert devnums == (259, 0), devnums
        devnums = rpath.RPath(self.lc, b"/dev/tty2", ()).getdevnums()
        assert devnums == (4, 2), devnums


class FileIO(RPathTest):
    """Test file input and output"""

    def testRead(self):
        """File reading"""
        with rpath.RPath(self.lc, self.prefix, ("executable", )).open("r") as fp:
            assert fp.read(6) == "#!/bin"

    def testWrite(self):
        """File writing"""
        rp = rpath.RPath(self.lc, self.mainprefix, ("testfile", ))
        with rp.open("w") as fp:
            fp.write("hello")
        with rp.open("r") as fp_input:
            assert fp_input.read() == "hello"
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
        assert not os.system(b"gunzip %s" % file_gz)
        with rp_nogz.open("rb") as fp_in:
            assert fp_in.read() == s

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
        assert rp_nogz.lstat()

        assert not os.system(b"gzip %s" % file_nogz)
        rp_nogz.setdata()
        rp_gz.setdata()
        assert not rp_nogz.lstat()
        assert rp_gz.lstat()
        with rp_gz.open("r", compress=1) as fp_in:
            read_s = fp_in.read().decode()  # zip is always binary hence bytes
            assert read_s == s, "Read string %s not like written %s." % (
                read_s, s)


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
        assert not self.dest.lstat()

    def testComp(self):
        """Test comparisons involving regular files"""
        assert rpath.cmp(self.hl1, self.hl2)
        assert not rpath.cmp(self.rf, self.hl1)
        assert not rpath.cmp(self.dir, self.rf)

    def testCompMisc(self):
        """Test miscellaneous comparisons"""
        assert rpath.cmp(self.dir, rpath.RPath(self.lc, self.mainprefix, ()))
        self.dest.symlink("regular_file")
        assert rpath.cmp(self.sl, self.dest)
        self.dest.delete()
        assert not rpath.cmp(self.sl, self.fifo)
        assert not rpath.cmp(self.dir, self.sl)

    def testDirSizeComp(self):
        """Make sure directories can be equal,
        even if they are of different sizes"""
        smalldir = rpath.RPath(Globals.local_connection,
                               os.path.join(old_test_dir, b"dircomptest", b"1"))
        bigdir = rpath.RPath(Globals.local_connection,
                             os.path.join(old_test_dir, b"dircomptest", b"2"))
        # Can guarantee below by adding files to bigdir
        assert bigdir.getsize() > smalldir.getsize()
        assert smalldir == bigdir

    def testCopy(self):
        """Test copy of various files"""
        for rp in [self.sl, self.rf, self.fifo, self.dir]:
            rpath.copy(rp, self.dest)
            assert self.dest.lstat(), "%a doesn't exist" % self.dest.path
            assert rpath.cmp(rp, self.dest)
            assert rpath.cmp(self.dest, rp)
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
            assert a.equal_loose(b), "Err with %a %a" % (a.path, b.path)
            assert b.equal_loose(a), "Err with %a %a" % (b.path, a.path)

    def testCompFail(self):
        """Test attribute comparison failures"""
        testpairs = [(self.nowrite, self.noperms), (self.exec1, self.exec2),
                     (self.rf, self.hl1)]
        for a, b in testpairs:
            assert not a.equal_loose(b), "Err with %a %a" % (a.path, b.path)
            assert not b.equal_loose(a), "Err with %a %a" % (b.path, a.path)

    def testCheckRaise(self):
        """Should raise exception when file missing"""
        self.assertRaises(rpath.RPathException, rpath.check_for_files, self.nothing,
                          self.hl1)
        self.assertRaises(rpath.RPathException, rpath.check_for_files, self.hl1,
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
            assert t.equal_loose(rp), \
                "Attributes for file %s not copied successfully" % rp.path
            t.delete()

    def testCopyWithAttribs(self):
        """Test copying with attribs (bug found earlier)"""
        out = rpath.RPath(self.lc, self.write_dir, ("out", ))
        if out.lstat():
            out.delete()
        for rp in [
                self.noperms, self.nowrite, self.rf, self.exec1, self.exec2,
                self.hl1, self.dir, self.sym
        ]:
            rpath.copy_with_attribs(rp, out)
            assert rpath.cmp(rp, out)
            assert rp.equal_loose(out)
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
        assert root.path == b"/", root.path
        bin = root.append("bin")
        assert bin.path == b"/bin", bin.path
        bin2 = rpath.RPath(Globals.local_connection, "/bin")
        assert bin2.path == b"/bin", bin2.path


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
        assert base_rp.isreg(), base_rp
        assert base_rp.getsize() == 0
        base_rp.delete()

        base_gz = dirrp.append('foo.gz')
        assert not base_gz.lstat()
        fileobj = rpath.MaybeGzip(base_rp)
        fileobj.write(b"lala")
        fileobj.close()
        base_rp.setdata()
        base_gz.setdata()
        assert not base_rp.lstat()
        assert base_gz.isreg(), base_gz
        data = base_gz.get_bytes(compressed=1)
        assert data == b"lala", data


if __name__ == "__main__":
    unittest.main()
