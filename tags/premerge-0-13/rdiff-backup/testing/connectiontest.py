import unittest, types, tempfile, os, sys
from commontest import *
from rdiff_backup.connection import *
from rdiff_backup import Globals, rpath, FilenameMapping

class LocalConnectionTest(unittest.TestCase):
	"""Test the dummy connection"""
	lc = Globals.local_connection

	def testGetAttrs(self):
		"""Test getting of various attributes"""
		assert type(self.lc.LocalConnection) is types.ClassType
		try: self.lc.asotnuhaoseu
		except (NameError, KeyError): pass
		else: unittest.fail("NameError or KeyError should be raised")

	def testSetattrs(self):
		"""Test setting of global attributes"""
		self.lc.x = 5
		assert self.lc.x == 5
		self.lc.x = 7
		assert self.lc.x == 7

	def testDelattrs(self):
		"""Testing deletion of attributes"""
		self.lc.x = 5
		del self.lc.x
		try: self.lc.x
		except (NameError, KeyError): pass
		else: unittest.fail("No exception raised")

	def testReval(self):
		"""Test string evaluation"""
		assert self.lc.reval("pow", 2, 3) == 8


class LowLevelPipeConnectionTest(unittest.TestCase):
	"""Test LLPC class"""
	objs = ["Hello", ("Tuple", "of", "strings"),
			[1, 2, 3, 4], 53.34235]
	excts = [TypeError("te"), NameError("ne"), os.error("oe")]
	filename = tempfile.mktemp()

	def testObjects(self):
		"""Try moving objects across connection"""
		outpipe = open(self.filename, "w")
		LLPC = LowLevelPipeConnection(None, outpipe)
		for obj in self.objs: LLPC._putobj(obj, 3)
		outpipe.close()
		inpipe = open(self.filename, "r")
		LLPC.inpipe = inpipe
		for obj in self.objs:
			gotten = LLPC._get()
			assert gotten == (3, obj), gotten
		inpipe.close
		os.unlink(self.filename)
		
	def testBuf(self):
		"""Try moving a buffer"""
		outpipe = open(self.filename, "w")
		LLPC = LowLevelPipeConnection(None, outpipe)
		inbuf = open("testfiles/various_file_types/regular_file", "r").read()
		LLPC._putbuf(inbuf, 234)
		outpipe.close()
		inpipe = open(self.filename, "r")
		LLPC.inpipe = inpipe
		assert (234, inbuf) == LLPC._get()
		inpipe.close()
		os.unlink(self.filename)

	def testSendingExceptions(self):
		"""Exceptions should also be sent down pipe well"""
		outpipe = open(self.filename, "w")
		LLPC = LowLevelPipeConnection(None, outpipe)
		for exception in self.excts: LLPC._putobj(exception, 0)
		outpipe.close()
		inpipe = open(self.filename, "r")
		LLPC.inpipe = inpipe
		for exception in self.excts:
			incoming_exception = LLPC._get()
			assert isinstance(incoming_exception[1], exception.__class__)
		inpipe.close()
		os.unlink(self.filename)


class PipeConnectionTest(unittest.TestCase):
	"""Test Pipe connection"""
	regfilename = "testfiles/various_file_types/regular_file"

	def setUp(self):
		"""Must start a server for this"""
		stdin, stdout = os.popen2("python ./server.py "+SourceDir)
		self.conn = PipeConnection(stdout, stdin)
		#self.conn.Log.setverbosity(9)
		#Log.setverbosity(9)

	def testBasic(self):
		"""Test some basic pipe functions"""
		assert self.conn.ord("a") == 97
		assert self.conn.pow(2,3) == 8
		assert self.conn.reval("ord", "a") == 97

	def testModules(self):
		"""Test module emulation"""
		assert type(self.conn.tempfile.mktemp()) is types.StringType
		assert self.conn.os.path.join("a", "b") == "a/b"
		rp1 = rpath.RPath(self.conn, self.regfilename)
		assert rp1.isreg()

	def testVirtualFiles(self):
		"""Testing virtual files"""
		tempout = self.conn.open("testfiles/tempout", "w")
		assert isinstance(tempout, VirtualFile)
		regfilefp = open(self.regfilename, "r")
		rpath.copyfileobj(regfilefp, tempout)
		tempout.close()
		regfilefp.close()
		tempoutlocal = open("testfiles/tempout", "r")
		regfilefp = open(self.regfilename, "r")
		assert rpath.cmpfileobj(regfilefp, tempoutlocal)
		tempoutlocal.close()
		regfilefp.close()
		os.unlink("testfiles/tempout")

		assert rpath.cmpfileobj(self.conn.open(self.regfilename, "r"),
								open(self.regfilename, "r"))

	def testString(self):
		"""Test transmitting strings"""
		assert "32" == self.conn.str(32)
		assert 32 == self.conn.int("32")

	def testIterators(self):
		"""Test transmission of iterators"""
		i = iter(map(RORPsubstitute, range(10)))
		assert self.conn.hasattr(i, "next")
		datastring = self.conn.reval("lambda i: i.next().data", i)
		assert datastring == "Hello, there 0", datastring

	def testRPaths(self):
		"""Test transmission of rpaths"""
		rp = rpath.RPath(self.conn,
						 "testfiles/various_file_types/regular_file")
		assert self.conn.reval("lambda rp: rp.data", rp) == rp.data
		assert self.conn.reval("lambda rp: rp.conn is Globals.local_connection", rp)

	def testQuotedRPaths(self):
		"""Test transmission of quoted rpaths"""
		qrp = FilenameMapping.QuotedRPath(self.conn,
						   "testfiles/various_file_types/regular_file")
		assert self.conn.reval("lambda qrp: qrp.data", qrp) == qrp.data
		assert qrp.isreg(), qrp
		qrp_class_str = self.conn.reval("lambda qrp: str(qrp.__class__)", qrp)
		assert qrp_class_str.find("QuotedRPath") > -1, qrp_class_str

	def testExceptions(self):
		"""Test exceptional results"""
		self.assertRaises(os.error, self.conn.os.lstat,
						  "asoeut haosetnuhaoseu tn")
		self.assertRaises(SyntaxError, self.conn.reval,
						  "aoetnsu aoehtnsu")
		assert self.conn.pow(2,3) == 8

	def tearDown(self):
		"""Bring down connection"""
		self.conn.quit()


class RedirectedConnectionTest(unittest.TestCase):
	"""Test routing and redirection"""
	def setUp(self):
		"""Must start two servers for this"""
		#Log.setverbosity(9)
		self.conna = SetConnections.init_connection("python ./server.py " +
													SourceDir)
		self.connb = SetConnections.init_connection("python ./server.py " +
													SourceDir)

	def testBasic(self):
		"""Test basic operations with redirection"""
		self.conna.Globals.set("tmp_val", 1)
		self.connb.Globals.set("tmp_val", 2)
		assert self.conna.Globals.get("tmp_val") == 1
		assert self.connb.Globals.get("tmp_val") == 2

		self.conna.Globals.set("tmp_connb", self.connb)
		self.connb.Globals.set("tmp_conna", self.conna)
		assert self.conna.Globals.get("tmp_connb") is self.connb
		assert self.connb.Globals.get("tmp_conna") is self.conna

		val = self.conna.reval("Globals.get('tmp_connb').Globals.get",
							   "tmp_val")
		assert val == 2, val
		val = self.connb.reval("Globals.get('tmp_conna').Globals.get",
							   "tmp_val")
		assert val == 1, val

		assert self.conna.reval("Globals.get('tmp_connb').pow", 2, 3) == 8
		self.conna.reval("Globals.tmp_connb.reval",
						 "Globals.tmp_conna.Globals.set", "tmp_marker", 5)
		assert self.conna.Globals.get("tmp_marker") == 5

	def testRpaths(self):
		"""Test moving rpaths back and forth across connections"""
		rp = rpath.RPath(self.conna, "foo")
		self.connb.Globals.set("tmp_rpath", rp)
		rp_returned = self.connb.Globals.get("tmp_rpath")
		assert rp_returned.conn is rp.conn
		assert rp_returned.path == rp.path

	def tearDown(self):
		SetConnections.CloseConnections()

class RORPsubstitute:
	"""Used in testIterators above to simulate a RORP"""
	def __init__(self, i):
		self.index = i
		self.data = "Hello, there %d" % i
		self.file = None

if __name__ == "__main__":
	unittest.main()
