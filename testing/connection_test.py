"""
Test the connection functionality of rdiff-backup
"""

import os
import subprocess
import sys
import unittest
import errno

import commontest as comtst

from rdiff_backup import connection, rpath, Security, SetConnections
from rdiffbackup.locations.map import filenames as map_filenames
from rdiffbackup.singletons import specifics

TEST_BASE_DIR = comtst.get_test_base_dir(__file__)

SourceDir = "rdiff_backup"
regfilename = os.path.join(comtst.old_test_dir, b"various_file_types", b"regular_file")


class LocalConnectionTest(unittest.TestCase):
    """Test the dummy connection"""

    lc = specifics.local_connection

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
    filename = os.path.join(TEST_BASE_DIR, b"test_low_level_pipe")

    def testObjects(self):
        """Try moving objects across connection"""
        with open(self.filename, "wb") as outpipe:
            LLPC = connection.LowLevelPipeConnection(None, outpipe)
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
            LLPC = connection.LowLevelPipeConnection(None, outpipe)
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
            LLPC = connection.LowLevelPipeConnection(None, outpipe)
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
        pipe_cmd = (sys.executable, "testing/server.py", SourceDir)
        self.p = subprocess.Popen(
            pipe_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            close_fds=True,
        )
        (stdin, stdout) = (self.p.stdin, self.p.stdout)
        self.conn = connection.PipeConnection(stdout, stdin, process=self.p)
        Security._security_level = "override"

    def testBasic(self):
        """Test some basic pipe functions"""
        self.assertEqual(self.conn.ord("a"), 97)
        self.assertEqual(self.conn.pow(2, 3), 8)
        self.assertEqual(self.conn.reval("ord", "a"), 97)

    def testModules(self):
        """Test module emulation"""
        self.assertIsInstance(self.conn.os.getcwd(), str)
        self.assertEqual(self.conn.os.path.join(b"a", b"b"), os.path.join(b"a", b"b"))
        rp1 = rpath.RPath(self.conn, regfilename)
        self.assertTrue(rp1.isreg())

    def testVirtualFiles(self):
        """Testing virtual files"""
        # generate file name for temporary file
        temp_file = os.path.join(TEST_BASE_DIR, b"tempout")

        tempout = self.conn.open(temp_file, "wb")
        self.assertIsInstance(tempout, connection.VirtualFile)
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
            self.assertTrue(
                rpath._cmp_file_obj(self.conn.open(regfilename, "rb"), localfh)
            )

    def testString(self):
        """Test transmitting strings"""
        self.assertEqual("32", self.conn.str(32))
        self.assertEqual(32, self.conn.int("32"))

    def testIterators(self):
        """Test transmission of iterators"""
        i = iter([5, 10, 15] * 100)
        self.assertTrue(
            self.conn.hasattr(i, "__next__") and self.conn.hasattr(i, "__iter__")
        )
        self.assertEqual(self.conn.reval("max", i), 15)

    def testRPaths(self):
        """Test transmission of rpaths"""
        rp = rpath.RPath(self.conn, regfilename)
        self.assertEqual(self.conn.reval("getattr", rp, "data"), rp.data)
        self.assertEqual(
            self.conn.reval("getattr", rp, "conn"), specifics.local_connection
        )

    def testQuotedRPaths(self):
        """Test transmission of quoted rpaths"""
        qrp = map_filenames.QuotedRPath(self.conn, regfilename)
        self.assertEqual(self.conn.reval("getattr", qrp, "data"), qrp.data)
        self.assertTrue(qrp.isreg())
        qrp_class_str = str(self.conn.reval("rpath.RPath.__class__", qrp))
        self.assertGreater(qrp_class_str.find("QuotedRPath"), -1)

    def testExceptions(self):
        """Test exceptional results"""
        with self.assertRaises(os.error) as ctx:
            self.conn.os.lstat("asoeut haosetnuhaoseu tn")
        self.assertEqual(ctx.exception.errno, errno.ENOENT)
        self.assertEqual(ctx.exception.errno_str, "ENOENT")
        self.assertRaises(NameError, self.conn.reval, "aoetnsu aoehtnsu")
        self.assertRaises(NameError, self.conn.reval, "aoetnsu.aoehtnsu")
        self.assertEqual(self.conn.pow(2, 3), 8)

    def tearDown(self):
        """Bring down connection"""
        self.conn.quit()


class RedirectedConnectionTest(unittest.TestCase):
    """Test routing and redirection"""

    def setUp(self):
        """Must start two servers for this"""
        self.conna = SetConnections._init_connection(
            "%s testing/server.py %s" % (sys.executable, SourceDir)
        )
        self.connb = SetConnections._init_connection(
            "%s testing/server.py %s" % (sys.executable, SourceDir)
        )

    def testBasic(self):
        """Test basic operations with redirection"""
        self.conna.specifics.set("tmp_val", 1)
        self.connb.specifics.set("tmp_val", 2)
        self.assertEqual(self.conna.specifics.get("tmp_val"), 1)
        self.assertEqual(self.connb.specifics.get("tmp_val"), 2)

        self.conna.specifics.set("tmp_connb", self.connb)
        self.connb.specifics.set("tmp_conna", self.conna)
        self.assertIs(self.conna.specifics.get("tmp_connb"), self.connb)
        self.assertIs(self.connb.specifics.get("tmp_conna"), self.conna)

    def testRpaths(self):
        """Test moving rpaths back and forth across connections"""
        rp = rpath.RPath(self.conna, "foo")
        self.connb.specifics.set("tmp_rpath", rp)
        rp_returned = self.connb.specifics.get("tmp_rpath")
        self.assertIs(rp_returned.conn, rp.conn)
        self.assertEqual(rp_returned.path, rp.path)

    def tearDown(self):
        SetConnections.CloseConnections()


@unittest.skipIf(os.name == "nt", "No way to prolongate a Windows command")
class LengthyConnectionTest(unittest.TestCase):
    """Test what happens if a server process takes too long to quit"""

    def test_killing_server_process(self):
        """Make the server process take longer"""
        pipe_cmd = "%s testing/server.py %s" % (sys.executable, SourceDir)
        pipe_cmd += "; sleep 10"
        self.p = subprocess.Popen(
            pipe_cmd,
            shell=True,  # nosec B602 subprocess_popen_with_shell_equals_true
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            close_fds=True,
        )
        (stdin, stdout) = (self.p.stdin, self.p.stdout)
        self.conn = connection.PipeConnection(stdout, stdin, process=self.p)
        Security._security_level = "override"
        # the sleep command should never be finished at this stage
        self.conn.quit()
        self.assertEqual(self.conn.process.returncode, -15)  # kill -15


if __name__ == "__main__":
    unittest.main()
