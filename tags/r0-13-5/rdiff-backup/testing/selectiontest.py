from __future__ import generators
import re, StringIO, unittest, types
from commontest import *
from rdiff_backup.selection import *
from rdiff_backup import Globals, rpath, lazy


class MatchingTest(unittest.TestCase):
	"""Test matching of file names against various selection functions"""
	def makerp(self, path): return rpath.RPath(Globals.local_connection, path)
	def makeext(self, path): return self.root.new_index(tuple(path.split("/")))

	def setUp(self):
		self.root = rpath.RPath(Globals.local_connection, "testfiles/select")
		self.Select = Select(self.root)

	def testRegexp(self):
		"""Test regular expression selection func"""
		sf1 = self.Select.regexp_get_sf(".*\.py", 1)
		assert sf1(self.makeext("1.py")) == 1
		assert sf1(self.makeext("usr/foo.py")) == 1
		assert sf1(self.root.append("1.doc")) == None

		sf2 = self.Select.regexp_get_sf("hello", 0)
		assert sf2(self.makerp("hello")) == 0
		assert sf2(self.makerp("foohello_there")) == 0
		assert sf2(self.makerp("foo")) == None

	def testTupleInclude(self):
		"""Test include selection function made from a regular filename"""
		self.assertRaises(FilePrefixError,
						  self.Select.glob_get_filename_sf, "foo", 1)

		sf2 = self.Select.glob_get_sf("testfiles/select/usr/local/bin/", 1)
		assert sf2(self.makeext("usr")) == 1
		assert sf2(self.makeext("usr/local")) == 1
		assert sf2(self.makeext("usr/local/bin")) == 1
		assert sf2(self.makeext("usr/local/doc")) == None
		assert sf2(self.makeext("usr/local/bin/gzip")) == 1
		assert sf2(self.makeext("usr/local/bingzip")) == None

	def testTupleExclude(self):
		"""Test exclude selection function made from a regular filename"""
		self.assertRaises(FilePrefixError,
						  self.Select.glob_get_filename_sf, "foo", 0)

		sf2 = self.Select.glob_get_sf("testfiles/select/usr/local/bin/", 0)
		assert sf2(self.makeext("usr")) == None
		assert sf2(self.makeext("usr/local")) == None
		assert sf2(self.makeext("usr/local/bin")) == 0
		assert sf2(self.makeext("usr/local/doc")) == None
		assert sf2(self.makeext("usr/local/bin/gzip")) == 0
		assert sf2(self.makeext("usr/local/bingzip")) == None

	def testGlobStarInclude(self):
		"""Test a few globbing patterns, including **"""
		sf1 = self.Select.glob_get_sf("**", 1)
		assert sf1(self.makeext("foo")) == 1
		assert sf1(self.makeext("")) == 1

		sf2 = self.Select.glob_get_sf("**.py", 1)
		assert sf2(self.makeext("foo")) == 2
		assert sf2(self.makeext("usr/local/bin")) == 2
		assert sf2(self.makeext("what/ever.py")) == 1
		assert sf2(self.makeext("what/ever.py/foo")) == 1

	def testGlobStarExclude(self):
		"""Test a few glob excludes, including **"""
		sf1 = self.Select.glob_get_sf("**", 0)
		assert sf1(self.makeext("/usr/local/bin")) == 0

		sf2 = self.Select.glob_get_sf("**.py", 0)
		assert sf2(self.makeext("foo")) == None, sf2(self.makeext("foo"))
		assert sf2(self.makeext("usr/local/bin")) == None
		assert sf2(self.makeext("what/ever.py")) == 0
		assert sf2(self.makeext("what/ever.py/foo")) == 0

	def testFilelistInclude(self):
		"""Test included filelist"""
		fp = StringIO.StringIO("""
testfiles/select/1/2
testfiles/select/1
testfiles/select/1/2/3
testfiles/select/3/3/2""")
		sf = self.Select.filelist_get_sf(fp, 1, "test")
		assert sf(self.root) == 1
		assert sf(self.makeext("1")) == 1
		assert sf(self.makeext("1/1")) == None
		assert sf(self.makeext("1/2/3")) == 1
		assert sf(self.makeext("2/2")) == None
		assert sf(self.makeext("3")) == 1
		assert sf(self.makeext("3/3")) == 1
		assert sf(self.makeext("3/3/3")) == None

	def testFilelistWhitespaceInclude(self):
		"""Test included filelist, with some whitespace"""
		fp = StringIO.StringIO("""
+ testfiles/select/1  
- testfiles/select/2  
testfiles/select/3\t""")
		sf = self.Select.filelist_get_sf(fp, 1, "test")
		assert sf(self.root) == 1
		assert sf(self.makeext("1  ")) == 1
		assert sf(self.makeext("2  ")) == 0
		assert sf(self.makeext("3\t")) == 1
		assert sf(self.makeext("4")) == None

	def testFilelistIncludeNullSep(self):
		"""Test included filelist but with null_separator set"""
		fp = StringIO.StringIO("""\0testfiles/select/1/2\0testfiles/select/1\0testfiles/select/1/2/3\0testfiles/select/3/3/2\0testfiles/select/hello\nthere\0""")
		Globals.null_separator = 1
		sf = self.Select.filelist_get_sf(fp, 1, "test")
		assert sf(self.root) == 1
		assert sf(self.makeext("1")) == 1
		assert sf(self.makeext("1/1")) == None
		assert sf(self.makeext("1/2/3")) == 1
		assert sf(self.makeext("2/2")) == None
		assert sf(self.makeext("3")) == 1
		assert sf(self.makeext("3/3")) == 1
		assert sf(self.makeext("3/3/3")) == None
		assert sf(self.makeext("hello\nthere")) == 1
		Globals.null_separator = 0

	def testFilelistExclude(self):
		"""Test included filelist"""
		fp = StringIO.StringIO("""
testfiles/select/1/2
testfiles/select/1
this is a badly formed line which should be ignored

testfiles/select/1/2/3
testfiles/select/3/3/2""")
		sf = self.Select.filelist_get_sf(fp, 0, "test")
		assert sf(self.root) == None
		assert sf(self.makeext("1")) == 0
		assert sf(self.makeext("1/1")) == 0
		assert sf(self.makeext("1/2/3")) == 0
		assert sf(self.makeext("2/2")) == None
		assert sf(self.makeext("3")) == None
		assert sf(self.makeext("3/3/2")) == 0
		assert sf(self.makeext("3/3/3")) == None

	def testFilelistInclude2(self):
		"""testFilelistInclude2 - with modifiers"""
		fp = StringIO.StringIO("""
testfiles/select/1/1
- testfiles/select/1/2
+ testfiles/select/1/3
- testfiles/select/3""")
		sf = self.Select.filelist_get_sf(fp, 1, "test1")
		assert sf(self.makeext("1")) == 1
		assert sf(self.makeext("1/1")) == 1
		assert sf(self.makeext("1/1/2")) == None				 
		assert sf(self.makeext("1/2")) == 0
		assert sf(self.makeext("1/2/3")) == 0
		assert sf(self.makeext("1/3")) == 1
		assert sf(self.makeext("2")) == None
		assert sf(self.makeext("3")) == 0

	def testFilelistExclude2(self):
		"""testFilelistExclude2 - with modifiers"""
		fp = StringIO.StringIO("""
testfiles/select/1/1
- testfiles/select/1/2
+ testfiles/select/1/3
- testfiles/select/3""")
		sf = self.Select.filelist_get_sf(fp, 0, "test1")
		sf_val1 = sf(self.root)
		assert sf_val1 == 1 or sf_val1 == None # either is OK
		sf_val2 = sf(self.makeext("1"))
		assert sf_val2 == 1 or sf_val2 == None
		assert sf(self.makeext("1/1")) == 0
		assert sf(self.makeext("1/1/2")) == 0
		assert sf(self.makeext("1/2")) == 0
		assert sf(self.makeext("1/2/3")) == 0
		assert sf(self.makeext("1/3")) == 1
		assert sf(self.makeext("2")) == None
		assert sf(self.makeext("3")) == 0

	def testGlobRE(self):
		"""testGlobRE - test translation of shell pattern to regular exp"""
		assert self.Select.glob_to_re("hello") == "hello"
		assert self.Select.glob_to_re(".e?ll**o") == "\\.e[^/]ll.*o"
		r = self.Select.glob_to_re("[abc]el[^de][!fg]h")
		assert r == "[abc]el[^de][^fg]h", r
		r = self.Select.glob_to_re("/usr/*/bin/")
		assert r == "\\/usr\\/[^/]*\\/bin\\/", r
		assert self.Select.glob_to_re("[a.b/c]") == "[a.b/c]"
		r = self.Select.glob_to_re("[a*b-c]e[!]]")
		assert r == "[a*b-c]e[^]]", r

	def testGlobSFException(self):
		"""testGlobSFException - see if globbing errors returned"""
		self.assertRaises(GlobbingError, self.Select.glob_get_normal_sf,
						  "testfiles/select/hello//there", 1)
		self.assertRaises(FilePrefixError,
						  self.Select.glob_get_sf, "testfiles/whatever", 1)
		self.assertRaises(FilePrefixError,
						  self.Select.glob_get_sf, "testfiles/?hello", 0)
		assert self.Select.glob_get_normal_sf("**", 1)

	def testIgnoreCase(self):
		"""testIgnoreCase - try a few expressions with ignorecase:"""
		sf = self.Select.glob_get_sf("ignorecase:testfiles/SeLect/foo/bar", 1)
		assert sf(self.makeext("FOO/BAR")) == 1
		assert sf(self.makeext("foo/bar")) == 1
		assert sf(self.makeext("fOo/BaR")) == 1
		self.assertRaises(FilePrefixError, self.Select.glob_get_sf,
						  "ignorecase:tesfiles/sect/foo/bar", 1)
						  
	def testDev(self):
		"""Test device and special file selection"""
		dir = self.root.append("filetypes")
		fifo = dir.append("fifo")
		assert fifo.isfifo(), fifo
		sym = dir.append("symlink")
		assert sym.issym(), sym
		reg = dir.append("regular_file")
		assert reg.isreg(), reg
		sock = dir.append("replace_with_socket")
		if not sock.issock():
			assert sock.isreg(), sock
			sock.delete()
			sock.mksock()
			assert sock.issock()
		dev = dir.append("ttyS1")
		assert dev.isdev(), dev
		
		sf = self.Select.devfiles_get_sf(0)
		assert sf(dir) == None
		assert sf(dev) == 0
		assert sf(sock) == None

		sf2 = self.Select.special_get_sf(0)
		assert sf2(dir) == None
		assert sf2(reg) == None
		assert sf2(dev) == 0
		assert sf2(sock) == 0
		assert sf2(fifo) == 0
		assert sf2(sym) == 0

		sf3 = self.Select.symlinks_get_sf(0)
		assert sf3(dir) == None
		assert sf3(reg) == None
		assert sf3(dev) == None
		assert sf3(sock) == None
		assert sf3(fifo) == None
		assert sf3(sym) == 0

	def testRoot(self):
		"""testRoot - / may be a counterexample to several of these.."""
		root = rpath.RPath(Globals.local_connection, "/")
		select = Select(root)

		assert select.glob_get_sf("/", 1)(root) == 1
		assert select.glob_get_sf("/foo", 1)(root) == 1
		assert select.glob_get_sf("/foo/bar", 1)(root) == 1
		assert select.glob_get_sf("/", 0)(root) == 0
		assert select.glob_get_sf("/foo", 0)(root) == None

		assert select.glob_get_sf("**.py", 1)(root) == 2
		assert select.glob_get_sf("**", 1)(root) == 1
		assert select.glob_get_sf("ignorecase:/", 1)(root) == 1
		assert select.glob_get_sf("**.py", 0)(root) == None
		assert select.glob_get_sf("**", 0)(root) == 0
		assert select.glob_get_sf("/foo/*", 0)(root) == None

		select.filelist_get_sf(StringIO.StringIO("/"), 1, "test")(root) == 1
		select.filelist_get_sf(StringIO.StringIO("/foo/bar"), 1,
							   "test")(root) == 1
		select.filelist_get_sf(StringIO.StringIO("/"), 0, "test")(root) == 0
		select.filelist_get_sf(StringIO.StringIO("/foo/bar"), 0,
							   "test")(root) == None

	def testOtherFilesystems(self):
		"""Test to see if --exclude-other-filesystems works correctly"""
		root = rpath.RPath(Globals.local_connection, "/")
		select = Select(root)
		sf = select.other_filesystems_get_sf(0)
		assert sf(root) is None
		assert sf(RPath(Globals.local_connection, "/usr/bin")) is None, \
			   "Assumption: /usr/bin is on the same filesystem as /"
		assert sf(RPath(Globals.local_connection, "/proc")) == 0, \
			   "Assumption: /proc is on a different filesystem"
		assert sf(RPath(Globals.local_connection, "/boot")) == 0, \
			   "Assumption: /boot is on a different filesystem"

class ParseArgsTest(unittest.TestCase):
	"""Test argument parsing as well as filelist globbing"""
	root = None
	def ParseTest(self, tuplelist, indicies, filelists = []):
		"""No error if running select on tuple goes over indicies"""
		if not self.root:
			self.root = RPath(Globals.local_connection, "testfiles/select")
		self.Select = Select(self.root)
		self.Select.ParseArgs(tuplelist, self.remake_filelists(filelists))
		self.Select.set_iter()
		assert lazy.Iter.equal(lazy.Iter.map(lambda dsrp: dsrp.index,
											 self.Select),
							   iter(indicies), verbose = 1)

	def remake_filelists(self, filelist):
		"""Turn strings in filelist into fileobjs"""
		new_filelists = []
		for f in filelist:
			if type(f) is types.StringType:
				new_filelists.append(StringIO.StringIO(f))
			else: new_filelists.append(f)
		return new_filelists

	def testParse(self):
		"""Test just one include, all exclude"""
		self.ParseTest([("--include", "testfiles/select/1/1"),
						("--exclude", "**")],
					   [(), ('1',), ("1", "1"), ("1", '1', '1'),
							 ('1', '1', '2'), ('1', '1', '3')])
		
	def testParse2(self):
		"""Test three level include/exclude"""
		self.ParseTest([("--exclude", "testfiles/select/1/1/1"),
							   ("--include", "testfiles/select/1/1"),
							   ("--exclude", "testfiles/select/1"),
							   ("--exclude", "**")],
					   [(), ('1',), ('1', '1'), ('1', '1', '2'),
						('1', '1', '3')])

	def test_globbing_filelist(self):
		"""Filelist glob test similar to above testParse2"""
		self.ParseTest([("--include-globbing-filelist", "file")],
					   [(), ('1',), ('1', '1'), ('1', '1', '2'),
						('1', '1', '3')],
					   ["""
- testfiles/select/1/1/1
testfiles/select/1/1
- testfiles/select/1
- **
"""])

	def testGlob(self):
		"""Test globbing expression"""
		self.ParseTest([("--exclude", "**[3-5]"),
						("--include", "testfiles/select/1"),
						("--exclude", "**")],
					   [(), ('1',), ('1', '1'),
						('1', '1', '1'), ('1', '1', '2'),
						('1', '2'), ('1', '2', '1'), ('1', '2', '2')])
		self.ParseTest([("--include", "testfiles/select**/2"),
						("--exclude", "**")],
					   [(), ('1',), ('1', '1'),
						('1', '1', '2'),
						('1', '2'),
						('1', '2', '1'), ('1', '2', '2'), ('1', '2', '3'),
						('1', '3'),
						('1', '3', '2'),
						('2',), ('2', '1'),
						('2', '1', '1'), ('2', '1', '2'), ('2', '1', '3'),
						('2', '2'),
						('2', '2', '1'), ('2', '2', '2'), ('2', '2', '3'),
						('2', '3'),
						('2', '3', '1'), ('2', '3', '2'), ('2', '3', '3'),
						('3',), ('3', '1'),
						('3', '1', '2'),
						('3', '2'),
						('3', '2', '1'), ('3', '2', '2'), ('3', '2', '3'),
						('3', '3'),
						('3', '3', '2')])

	def test_globbing_filelist2(self):
		"""Filelist glob test similar to above testGlob"""
		self.ParseTest([("--exclude-globbing-filelist", "asoeuth")],
					   [(), ('1',), ('1', '1'),
						('1', '1', '1'), ('1', '1', '2'),
						('1', '2'), ('1', '2', '1'), ('1', '2', '2')],
					   ["""
**[3-5]
+ testfiles/select/1
**
"""])
		self.ParseTest([("--include-globbing-filelist", "file")],
					   [(), ('1',), ('1', '1'),
						('1', '1', '2'),
						('1', '2'),
						('1', '2', '1'), ('1', '2', '2'), ('1', '2', '3'),
						('1', '3'),
						('1', '3', '2'),
						('2',), ('2', '1'),
						('2', '1', '1'), ('2', '1', '2'), ('2', '1', '3'),
						('2', '2'),
						('2', '2', '1'), ('2', '2', '2'), ('2', '2', '3'),
						('2', '3'),
						('2', '3', '1'), ('2', '3', '2'), ('2', '3', '3'),
						('3',), ('3', '1'),
						('3', '1', '2'),
						('3', '2'),
						('3', '2', '1'), ('3', '2', '2'), ('3', '2', '3'),
						('3', '3'),
						('3', '3', '2')],
					   ["""
testfiles/select**/2
- **
"""])
					   
	def testGlob2(self):
		"""Test more globbing functions"""
		self.ParseTest([("--include", "testfiles/select/*foo*/p*"),
						("--exclude", "**")],
					   [(), ('efools',), ('efools', 'ping'),
						('foobar',), ('foobar', 'pong')])
		self.ParseTest([("--exclude", "testfiles/select/1/1/*"),
						("--exclude", "testfiles/select/1/2/**"),
						("--exclude", "testfiles/select/1/3**"),
						("--include", "testfiles/select/1"),
						("--exclude", "**")],
					   [(), ('1',), ('1', '1'), ('1', '2')])

	def testAlternateRoot(self):
		"""Test select with different root"""
		self.root = rpath.RPath(Globals.local_connection, "testfiles/select/1")
		self.ParseTest([("--exclude", "testfiles/select/1/[23]")],
					   [(), ('1',), ('1', '1'), ('1', '2'), ('1', '3')])

		self.root = rpath.RPath(Globals.local_connection, "/")
		self.ParseTest([("--exclude", "/home/*"),
						("--include", "/home"),
						("--exclude", "/")],
					   [(), ("home",)])

#	def testParseStartingFrom(self):
#		"""Test parse, this time starting from inside"""
#		self.root = rpath.RPath(Globals.local_connection, "testfiles/select")
#		self.Select = Select(self.root)
#		self.Select.ParseArgs([("--include", "testfiles/select/1/1"),
#							   ("--exclude", "**")], [])
#		self.Select.set_iter(('1', '1'))
#		assert lazy.Iter.equal(lazy.Iter.map(lambda dsrp: dsrp.index,
#											 self.Select),
#						  iter([("1", '1', '1'),
#								('1', '1', '2'),
#								('1', '1', '3')]),
#						  verbose = 1)


if __name__ == "__main__": unittest.main()
