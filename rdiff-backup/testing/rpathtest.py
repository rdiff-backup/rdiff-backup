import os, cPickle, sys, unittest
from commontest import *
from rpath import *


class RPathTest(unittest.TestCase):
	lc = Globals.local_connection
	prefix = "testfiles/various_file_types/"
	mainprefix = "testfiles/"
	rp_prefix = RPath(lc, prefix, ())
	rp_main = RPath(lc, mainprefix, ())


class RORPStateTest(RPathTest):
	"""Test Pickling of RORPaths"""
	def testPickle(self):
		rorp = RPath(self.lc, self.prefix, ("regular_file",)).getRORPath()
		rorp.file = sys.stdin # try to confuse pickler
		assert rorp.isreg()
		rorp2 = cPickle.loads(cPickle.dumps(rorp, 1))
		assert rorp2.isreg()
		assert rorp2.data == rorp.data and rorp.index == rorp2.index
		

class CheckTypes(RPathTest):
	"""Check to see if file types are identified correctly"""
	def testExist(self):
		"""Can tell if files exist"""
		assert RPath(self.lc, self.prefix, ()).lstat()
		assert not RPath(self.lc, "asuthasetuouo", ()).lstat()

	def testDir(self):
		"""Directories identified correctly"""
		assert RPath(self.lc, self.prefix, ()).isdir()
		assert not RPath(self.lc, self.prefix, ("regular_file",)).isdir()

	def testSym(self):
		"""Symbolic links identified"""
		assert RPath(self.lc, self.prefix, ("symbolic_link",)).issym()
		assert not RPath(self.lc, self.prefix, ()).issym()

	def testReg(self):
		"""Regular files identified"""
		assert RPath(self.lc, self.prefix, ("regular_file",)).isreg()
		assert not RPath(self.lc, self.prefix, ("symbolic_link",)).isreg()

	def testFifo(self):
		"""Fifo's identified"""
		assert RPath(self.lc, self.prefix, ("fifo",)).isfifo()
		assert not RPath(self.lc, self.prefix, ()).isfifo()

	def testCharDev(self):
		"""Char special files identified"""
		assert RPath(self.lc, "/dev/tty2", ()).ischardev()
		assert not RPath(self.lc, self.prefix, ("regular_file",)).ischardev()

	def testBlockDev(self):
		"""Block special files identified"""
		assert RPath(self.lc, "/dev/hda", ()).isblkdev()
		assert not RPath(self.lc, self.prefix, ("regular_file",)).isblkdev()


class CheckPerms(RPathTest):
	"""Check to see if permissions are reported and set accurately"""
	def testExecReport(self):
		"""Check permissions for executable files"""
		assert self.rp_prefix.append('executable').getperms() == 0755
		assert self.rp_prefix.append('executable2').getperms() == 0700

	def testhighbits(self):
		"""Test reporting of highbit permissions"""
		p = RPath(self.lc, "testfiles/rpath2/foobar").getperms()
		assert p == 04100, p

	def testOrdinaryReport(self):
		"""Ordinary file permissions..."""
		assert self.rp_prefix.append("regular_file").getperms() == 0644
		assert self.rp_prefix.append('two_hardlinked_files1').getperms() == 0640

	def testChmod(self):
		"""Test changing file permission"""
		rp = self.rp_prefix.append("changeable_permission")
		rp.chmod(0700)
		assert rp.getperms() == 0700
		rp.chmod(0644)
		assert rp.getperms() == 0644

	def testExceptions(self):
		"""What happens when file absent"""
		self.assertRaises(Exception,
						  RPath(self.lc, self.prefix, ("aoeunto",)).getperms)


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
		d = RPath(self.lc, self.prefix, ("suthosutho",))
		self.assertRaises(os.error, d.rmdir)
		d.mkdir()
		self.assertRaises(os.error, d.mkdir)
		d.rmdir()

	def testListdir(self):
		"""Checking dir listings"""
		assert (RPath(self.lc, self.mainprefix, ("sampledir",)).listdir() ==
				["1", "2", "3", "4"])


class CheckSyms(RPathTest):
	"""Check symlinking and reading"""
	def testRead(self):
		"""symlink read"""
		assert (RPath(self.lc, self.prefix, ("symbolic_link",)).readlink() ==
				"regular_file")

	def testMake(self):
		"""Creating symlink"""
		link = RPath(self.lc, self.mainprefix, ("symlink",))
		assert not link.lstat()
		link.symlink("abcdefg")
		assert link.issym()
		assert link.readlink() == "abcdefg"
		link.delete()


class TouchDelete(RPathTest):
	"""Check touching and deletion of files"""
	def testTouch(self):
		"""Creation of 0 length files"""
		t = RPath(self.lc, self.mainprefix, ("testtouch",))
		assert not t.lstat()
		t.touch()
		assert t.lstat()
		t.delete()

	def testDelete(self):
		"""Deletion of files"""
		d = RPath(self.lc, self.mainprefix, ("testdelete",))
		d.touch()
		assert d.lstat()
		d.delete()
		assert not d.lstat()


class MiscFileInfo(RPathTest):
	"""Check Miscellaneous file information"""
	def testFileLength(self):
		"""File length = getsize()"""
		assert (RPath(self.lc, self.prefix, ("regular_file",)).getsize() ==
				75650)


class FilenameOps(RPathTest):
	"""Check filename operations"""
	weirdfilename = eval('\'\\xd8\\xab\\xb1Wb\\xae\\xc5]\\x8a\\xbb\\x15v*\\xf4\\x0f!\\xf9>\\xe2Y\\x86\\xbb\\xab\\xdbp\\xb0\\x84\\x13k\\x1d\\xc2\\xf1\\xf5e\\xa5U\\x82\\x9aUV\\xa0\\xf4\\xdf4\\xba\\xfdX\\x03\\x82\\x07s\\xce\\x9e\\x8b\\xb34\\x04\\x9f\\x17 \\xf4\\x8f\\xa6\\xfa\\x97\\xab\\xd8\\xac\\xda\\x85\\xdcKvC\\xfa#\\x94\\x92\\x9e\\xc9\\xb7\\xc3_\\x0f\\x84g\\x9aB\\x11<=^\\xdbM\\x13\\x96c\\x8b\\xa7|*"\\\\\\\'^$@#!(){}?+ ~` \'')
	normdict = {"/": "/",
				".": ".",
				"//": "/",
				"/a/b": "/a/b",
				"a/b": "a/b",
				"a//b": "a/b",
				"a////b//c": "a/b/c",
				"..": "..",
				"a/": "a",
				"/a//b///": "/a/b"}
	dirsplitdict = {"/": ("", ""),
					"/a": ("", "a"),
					"/a/b": ("/a", "b"),
					".": (".", "."),
					"b/c": ("b", "c"),
					"a": (".", "a")}
	
	def testQuote(self):
		"""See if filename quoting works"""
		wtf = RPath(self.lc, self.prefix, (self.weirdfilename,))
		reg = RPath(self.lc, self.prefix, ("regular_file",))
		assert wtf.lstat()
		assert reg.lstat()
		assert not os.system("ls %s >/dev/null 2>&1" % wtf.quote())
		assert not os.system("ls %s >/dev/null 2>&1" % reg.quote())

	def testNormalize(self):
		"""rpath.normalize() dictionary test"""
		for (before, after) in self.normdict.items():
			assert RPath(self.lc, before, ()).normalize().path == after, \
				   "Normalize fails for %s => %s" % (before, after)

	def testDirsplit(self):
		"""Test splitting of various directories"""
		for full, split in self.dirsplitdict.items():
			result = RPath(self.lc, full, ()).dirsplit()
			assert result == split, \
				   "%s => %s instead of %s" % (full, result, split)

	def testGetnums(self):
		"""Test getting file numbers"""
		devnums = RPath(self.lc, "/dev/hda", ()).getdevnums()
		assert devnums == (3, 0), devnums
		devnums = RPath(self.lc, "/dev/tty2", ()).getdevnums()
		assert devnums == (4, 2), devnums


class FileIO(RPathTest):
	"""Test file input and output"""
	def testRead(self):
		"""File reading"""
		fp = RPath(self.lc, self.prefix, ("executable",)).open("r")
		assert fp.read(6) == "#!/bin"
		fp.close()

	def testWrite(self):
		"""File writing"""
		rp = RPath(self.lc, self.mainprefix, ("testfile",))
		fp = rp.open("w")
		fp.write("hello")
		fp.close()
		fp_input = rp.open("r")
		assert fp_input.read() == "hello"
		fp_input.close()
		rp.delete()

	def testGzipWrite(self):
		"""Test writing of gzipped files"""
		try: os.mkdir("testfiles/output")
		except OSError: pass
		rp_gz = RPath(self.lc, "testfiles/output/file.gz")
		rp = RPath(self.lc, "testfiles/output/file")
		if rp.lstat(): rp.delete()
		s = "Hello, world!"
		
		fp_out = rp_gz.open("wb", compress = 1)
		fp_out.write(s)
		assert not fp_out.close()
		assert not os.system("gunzip testfiles/output/file.gz")
		fp_in = rp.open("rb")
		assert fp_in.read() == s
		fp_in.close()

	def testGzipRead(self):
		"""Test reading of gzipped files"""
		try: os.mkdir("testfiles/output")
		except OSError: pass
		rp_gz = RPath(self.lc, "testfiles/output/file.gz")
		if rp_gz.lstat(): rp_gz.delete()
		rp = RPath(self.lc, "testfiles/output/file")
		s = "Hello, world!"
		
		fp_out = rp.open("wb")
		fp_out.write(s)
		assert not fp_out.close()
		rp.setdata()
		assert rp.lstat()

		assert not os.system("gzip testfiles/output/file")
		rp.setdata()
		rp_gz.setdata()
		assert not rp.lstat()
		assert rp_gz.lstat()
		fp_in = rp_gz.open("rb", compress = 1)
		assert fp_in.read() == s
		assert not fp_in.close()		


class FileCopying(RPathTest):
	"""Test file copying and comparison"""
	def setUp(self):
		self.hl1 = RPath(self.lc, self.prefix, ("two_hardlinked_files1",))
		self.hl2 = RPath(self.lc, self.prefix, ("two_hardlinked_files2",))
		self.sl = RPath(self.lc, self.prefix, ("symbolic_link",))
		self.dir = RPath(self.lc, self.prefix, ())
		self.fifo = RPath(self.lc, self.prefix, ("fifo",))
		self.rf = RPath(self.lc, self.prefix, ("regular_file",))
		self.dest = RPath(self.lc, self.mainprefix, ("dest",))
		if self.dest.lstat(): self.dest.delete()
		assert not self.dest.lstat()

	def testComp(self):
		"""Test comparisons involving regular files"""
		assert RPath.cmp(self.hl1, self.hl2)
		assert not RPath.cmp(self.rf, self.hl1)
		assert not RPath.cmp(self.dir, self.rf)

	def testCompMisc(self):
		"""Test miscellaneous comparisons"""
		assert RPath.cmp(self.dir, RPath(self.lc, self.mainprefix, ()))
		self.dest.symlink("regular_file")
		assert RPath.cmp(self.sl, self.dest)
		self.dest.delete()
		assert not RPath.cmp(self.sl, self.fifo)
		assert not RPath.cmp(self.dir, self.sl)

	def testDirSizeComp(self):
		"""Make sure directories can be equal,
		even if they are of different sizes"""
		smalldir = RPath(Globals.local_connection, "testfiles/dircomptest/1")
		bigdir = RPath(Globals.local_connection, "testfiles/dircomptest/2")
		assert smalldir == bigdir

	def testCopy(self):
		"""Test copy of various files"""
		for rp in [self.sl, self.rf, self.fifo, self.dir]:
			RPath.copy(rp, self.dest)
			assert self.dest.lstat(), "%s doesn't exist" % self.dest.path
			assert RPath.cmp(rp, self.dest)
			assert RPath.cmp(self.dest, rp)
			self.dest.delete()


class FileAttributes(FileCopying):
	"""Test file attribute operations"""
	def setUp(self):
		FileCopying.setUp(self)
		self.noperms = RPath(self.lc, self.mainprefix, ("noperms",))
		self.nowrite = RPath(self.lc, self.mainprefix, ("nowrite",))
		self.exec1 = RPath(self.lc, self.prefix, ("executable",))
		self.exec2 = RPath(self.lc, self.prefix, ("executable2",))
		self.test = RPath(self.lc, self.prefix, ("test",))
		self.nothing = RPath(self.lc, self.prefix, ("aoeunthoenuouo",))
		self.sym = RPath(self.lc, self.prefix, ("symbolic_link",))

	def testComp(self):
		"""Test attribute comparison success"""
		testpairs = [(self.hl1, self.hl2)]
		for a, b in testpairs:
			assert RPath.cmp_attribs(a, b), "Err with %s %s" % (a.path, b.path)
			assert RPath.cmp_attribs(b, a), "Err with %s %s" % (b.path, a.path)

	def testCompFail(self):
		"""Test attribute comparison failures"""
		testpairs = [(self.nowrite, self.noperms),
					 (self.exec1, self.exec2),
					 (self.rf, self.hl1)]
		for a, b in testpairs:
			assert not RPath.cmp_attribs(a, b), \
				   "Err with %s %s" % (a.path, b.path)
			assert not RPath.cmp_attribs(b, a), \
				   "Err with %s %s" % (b.path, a.path)

	def testCompRaise(self):
		"""Should raise exception when file missing"""
		self.assertRaises(RPathException, RPath.cmp_attribs,
						  self.nothing, self.hl1)
		self.assertRaises(RPathException, RPath.cmp_attribs,
						  self.noperms, self.nothing)

	def testCopyAttribs(self):
		"""Test copying attributes"""
		t = RPath(self.lc, self.mainprefix, ("testattribs",))
		if t.lstat(): t.delete()
		for rp in [self.noperms, self.nowrite, self.rf, self.exec1,
				   self.exec2, self.hl1, self.dir]:
			t.touch()
			RPath.copy_attribs(rp, t)
			assert RPath.cmp_attribs(t, rp), \
				   "Attributes for file %s not copied successfully" % rp.path
			t.delete()

	def testCopyWithAttribs(self):
		"""Test copying with attribs (bug found earlier)"""
		out = RPath(self.lc, self.mainprefix, ("out",))
		if out.lstat(): out.delete()
		for rp in [self.noperms, self.nowrite, self.rf, self.exec1,
				   self.exec2, self.hl1, self.dir, self.sym]:
			RPath.copy_with_attribs(rp, out)
			assert RPath.cmp(rp, out)
			assert RPath.cmp_attribs(rp, out)
			out.delete()

	def testCopyRaise(self):
		"""Should raise exception for non-existent files"""
		self.assertRaises(RPathException, RPath.copy_attribs,
						  self.hl1, self.nothing)
		self.assertRaises(RPathException, RPath.copy_attribs,
						  self.nothing, self.nowrite)

class CheckPath(unittest.TestCase):
	"""Check to make sure paths generated properly"""
	def testpath(self):
		"""Test root paths"""
		root = RPath(Globals.local_connection, "/")
		assert root.path == "/", root.path
		bin = root.append("bin")
		assert bin.path == "/bin", bin.path
		bin2 = RPath(Globals.local_connection, "/bin")
		assert bin.path == "/bin", bin2.path

if __name__ == "__main__":
	unittest.main()
