import os
import sys
import subprocess
import tempfile
import time
import unittest
from commontest import old_test_dir, abs_test_dir
from rdiff_backup.connection import LowLevelPipeConnection, PipeConnection, \
    VirtualFile, SetConnections
from rdiff_backup import Globals, rpath, FilenameMapping, Security

SourceDir = 'rdiff_backup'
regfilename = os.path.join(old_test_dir, b"various_file_types",
                           b"regular_file")


class LocalConnectionTest(unittest.TestCase):
    """Test the dummy connection"""
    lc = Globals.local_connection

    def testGetAttrs(self):
        """Test getting of various attributes"""
        self.assertIsInstance(self.lc.LocalConnection, type)
        try:
            self.lc.asotnuhaoseu
        except (NameError, KeyError):
            pass
        else:
            unittest.fail("NameError or KeyError should be raised")

    def testSetattrs(self):
        """Test setting of global attributes"""
        self.lc.x = 5
        self.assertEqual(self.lc.x, 5)
        self.lc.x = 7
        self.assertEqual(self.lc.x, 7)

    def testDelattrs(self):
        """Testing deletion of attributes"""
        self.lc.x = 5
        del self.lc.x
        try:
            self.lc.x
        except (NameError, KeyError):
            pass
        else:
            unittest.fail("No exception raised")

    def testReval(self):
        """Test string evaluation"""
        self.assertEqual(self.lc.reval("pow", 2, 3), 8)


class LowLevelPipeConnectionTest(unittest.TestCase):
    """Test LLPC class"""
    objs = ["Hello", ("Tuple", "of", "strings"), [1, 2, 3, 4], 53.34235]
    excts = [TypeError("te"), NameError("ne"), os.error("oe")]
    filename = tempfile.mktemp()

    def testObjects(self):
        """Try moving objects across connection"""
        with open(self.filename, "wb") as outpipe:
            LLPC = LowLevelPipeConnection(None, outpipe)
            for obj in self.objs:
                LLPC._putobj(obj, 3)
        with open(self.filename, "rb") as inpipe:
            LLPC.inpipe = inpipe
            for obj in self.objs:
                gotten = LLPC._get()
                self.assertEqual(gotten, (3, obj))
        os.unlink(self.filename)

    def testBuf(self):
        """Try moving a buffer"""
        with open(self.filename, "wb") as outpipe:
            LLPC = LowLevelPipeConnection(None, outpipe)
            with open(regfilename, "rb") as inpipe:
                inbuf = inpipe.read()
            LLPC._putbuf(inbuf, 234)
        with open(self.filename, "rb") as inpipe:
            LLPC.inpipe = inpipe
            self.assertEqual((234, inbuf), LLPC._get())
        os.unlink(self.filename)

    def testSendingExceptions(self):
        """Exceptions should also be sent down pipe well"""
        with open(self.filename, "wb") as outpipe:
            LLPC = LowLevelPipeConnection(None, outpipe)
            for exception in self.excts:
                LLPC._putobj(exception, 0)
        with open(self.filename, "rb") as inpipe:
            LLPC.inpipe = inpipe
            for exception in self.excts:
                incoming_exception = LLPC._get()
                self.assertIsInstance(incoming_exception[1], exception.__class__)
        os.unlink(self.filename)


class PipeConnectionTest(unittest.TestCase):
    """Test Pipe connection"""

    def setUp(self):
        """Must start a server for this"""
        pipe_cmd = "%s testing/server.py %s" \
            % (sys.executable, SourceDir)
        self.p = subprocess.Popen(pipe_cmd,
                                  shell=True,
                                  stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE,
                                  close_fds=True)
        (stdin, stdout) = (self.p.stdin, self.p.stdout)
        self.conn = PipeConnection(stdout, stdin)
        Security._security_level = "override"

    def testBasic(self):
        """Test some basic pipe functions"""
        self.assertEqual(self.conn.ord("a"), 97)
        self.assertEqual(self.conn.pow(2, 3), 8)
        self.assertEqual(self.conn.reval("ord", "a"), 97)

    def testModules(self):
        """Test module emulation"""
        self.assertIsInstance(self.conn.tempfile.mktemp(), str)
        self.assertEqual(self.conn.os.path.join(b"a", b"b"),
                         os.path.join(b"a", b"b"))
        rp1 = rpath.RPath(self.conn, regfilename)
        self.assertTrue(rp1.isreg())

    def testVirtualFiles(self):
        """Testing virtual files"""
        # generate file name for temporary file
        temp_file = os.path.join(abs_test_dir, b"tempout")

        tempout = self.conn.open(temp_file, "wb")
        self.assertIsInstance(tempout, VirtualFile)
        regfilefp = open(regfilename, "rb")
        rpath.copyfileobj(regfilefp, tempout)
        tempout.close()
        regfilefp.close()
        tempoutlocal = open(temp_file, "rb")
        regfilefp = open(regfilename, "rb")
        self.assertTrue(rpath._cmp_file_obj(regfilefp, tempoutlocal))
        tempoutlocal.close()
        regfilefp.close()
        os.unlink(temp_file)

        with open(regfilename, "rb") as localfh:
            self.assertTrue(rpath._cmp_file_obj(self.conn.open(
                regfilename, "rb"), localfh))

    def testString(self):
        """Test transmitting strings"""
        self.assertEqual("32", self.conn.str(32))
        self.assertEqual(32, self.conn.int("32"))

    def testIterators(self):
        """Test transmission of iterators"""
        i = iter([5, 10, 15] * 100)
        self.assertTrue(self.conn.hasattr(i, "__next__")
                        and self.conn.hasattr(i, "__iter__"))
        ret_val = self.conn.reval("lambda i: next(i)*next(i)", i)
        self.assertEqual(ret_val, 50)

    def testRPaths(self):
        """Test transmission of rpaths"""
        rp = rpath.RPath(self.conn, regfilename)
        self.assertEqual(self.conn.reval("lambda rp: rp.data", rp), rp.data)
        self.assertTrue(self.conn.reval(
            "lambda rp: rp.conn is Globals.local_connection", rp))

    def testQuotedRPaths(self):
        """Test transmission of quoted rpaths"""
        qrp = FilenameMapping.QuotedRPath(self.conn, regfilename)
        self.assertEqual(self.conn.reval("lambda qrp: qrp.data", qrp), qrp.data)
        self.assertTrue(qrp.isreg())
        qrp_class_str = self.conn.reval("lambda qrp: str(qrp.__class__)", qrp)
        self.assertGreater(qrp_class_str.find("QuotedRPath"), -1)

    def testExceptions(self):
        """Test exceptional results"""
        self.assertRaises(os.error, self.conn.os.lstat,
                          "asoeut haosetnuhaoseu tn")
        self.assertRaises(SyntaxError, self.conn.reval, "aoetnsu aoehtnsu")
        self.assertEqual(self.conn.pow(2, 3), 8)

    def tearDown(self):
        """Bring down connection"""
        self.conn.quit()
        time.sleep(0.1)  # give the process time to quit
        if (self.p.poll() is None):
            self.p.terminate()


class RedirectedConnectionTest(unittest.TestCase):
    """Test routing and redirection"""

    def setUp(self):
        """Must start two servers for this"""
        self.conna = SetConnections._init_connection(
            "%s testing/server.py %s" % (sys.executable, SourceDir))
        self.connb = SetConnections._init_connection(
            "%s testing/server.py %s" % (sys.executable, SourceDir))

    def testBasic(self):
        """Test basic operations with redirection"""
        self.conna.Globals.set("tmp_val", 1)
        self.connb.Globals.set("tmp_val", 2)
        self.assertEqual(self.conna.Globals.get("tmp_val"), 1)
        self.assertEqual(self.connb.Globals.get("tmp_val"), 2)

        self.conna.Globals.set("tmp_connb", self.connb)
        self.connb.Globals.set("tmp_conna", self.conna)
        self.assertIs(self.conna.Globals.get("tmp_connb"), self.connb)
        self.assertIs(self.connb.Globals.get("tmp_conna"), self.conna)

        val = self.conna.reval("Globals.get('tmp_connb').Globals.get",
                               "tmp_val")
        self.assertEqual(val, 2)
        val = self.connb.reval("Globals.get('tmp_conna').Globals.get",
                               "tmp_val")
        self.assertEqual(val, 1)

        self.assertEqual(
            self.conna.reval("Globals.get('tmp_connb').pow", 2, 3), 8)
        self.conna.reval("Globals.tmp_connb.reval",
                         "Globals.tmp_conna.Globals.set", "tmp_marker", 5)
        self.assertEqual(self.conna.Globals.get("tmp_marker"), 5)

    def testRpaths(self):
        """Test moving rpaths back and forth across connections"""
        rp = rpath.RPath(self.conna, "foo")
        self.connb.Globals.set("tmp_rpath", rp)
        rp_returned = self.connb.Globals.get("tmp_rpath")
        self.assertIs(rp_returned.conn, rp.conn)
        self.assertEqual(rp_returned.path, rp.path)

    def tearDown(self):
        SetConnections.CloseConnections()


if __name__ == "__main__":
    unittest.main()
