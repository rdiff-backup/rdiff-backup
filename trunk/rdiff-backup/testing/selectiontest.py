from __future__ import generators
import re, StringIO, unittest
execfile("commontest.py")
rbexec("highlevel.py")

class MatchingTest(unittest.TestCase):
	"""Test matching of file names against various selection functions"""
	def makedsrp(self, path): return DSRPath(Globals.local_connection, path)
	def makeext(self, path): return self.root.new_index(tuple(path.split("/")))

	def setUp(self):
		self.root = DSRPath(Globals.local_connection, "testfiles/select")
		self.Select = Select(self.root)

	def testRegexp(self):
		"""Test regular expression selection func"""
		sf1 = self.Select.regexp_get_sf(".*\.py", 1)
		assert sf1(self.makeext("1.py")) == 1
		assert sf1(self.makeext("usr/foo.py")) == 1
		assert sf1(self.root.append("1.doc")) == None

		sf2 = self.Select.regexp_get_sf("hello", 0)
		assert sf2(self.makedsrp("hello")) == 0
		assert sf2(self.makedsrp("hello_there")) == None

	def testTupleInclude(self):
		"""Test include selection function made from a regular filename"""
		sf1 = self.Select.glob_get_sf("foo", 1) # should warn
		assert sf1(13) == None
		assert sf1("foo") == None

		sf2 = self.Select.glob_get_sf("testfiles/select/usr/local/bin/", 1)
		assert sf2(self.makeext("usr")) == 1
		assert sf2(self.makeext("usr/local")) == 1
		assert sf2(self.makeext("usr/local/bin")) == 1
		assert sf2(self.makeext("usr/local/doc")) == None
		assert sf2(self.makeext("usr/local/bin/gzip")) == 1
		assert sf2(self.makeext("usr/local/bingzip")) == None

	def testTupleExclude(self):
		"""Test exclude selection function made from a regular filename"""
		sf1 = self.Select.glob_get_sf("foo", 0) # should warn
		assert sf1(13) == None
		assert sf1("foo") == None

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
		assert sf1(self.makeext("foo")) == 2
		assert sf1(self.makeext("usr/local/bin")) == 2
		assert sf1(self.makeext("what/ever.py")) == 1
		assert sf1(self.makeext("what/ever.py/foo")) == 1

	def testGlobStarExclude(self):
		"""Test a few glob excludes, including **"""
		sf1 = self.Select.glob_get_sf("**", 0)
		assert sf1(self.makeext("/usr/local/bin")) == 0

		sf2 = self.Select.glob_get_sf("**.py", 0)
		assert sf1(self.makeext("foo")) == None
		assert sf1(self.makeext("usr/local/bin")) == None
		assert sf1(self.makeext("what/ever.py")) == 0
		assert sf1(self.makeext("what/ever.py/foo")) == 0

	def testFilelistInclude(self):
		"""Test included filelist"""
		fp = StringIO.StringIO("""
testfiles/select/1/2
testfiles/select/1
testfiles/select/1/2/3
testfiles/select/3/3/3""")
		sf = self.Select.filelist_get_sf(fp, 1, "test")
		assert sf(self.root) == 1
		assert sf(self.makeext("1")) == 1
		assert sf(self.makeext("1/1")) == None
		assert sf(self.makeext("1/2/3")) == 1
		assert sf(self.makeext("2/2")) == None
		assert sf(self.makeext("3")) == 1
		assert sf(self.makeext("3/3")) == 1

	def testFilelistExclude(self):
		"""Test included filelist"""
		fp = StringIO.StringIO("""
testfiles/select/1/2
testfiles/select/1
testfiles/select/1/2/3
testfiles/select/3/3/3""")
		sf = self.Select.filelist_get_sf(fp, 0, "test")
		assert sf(self.root) == None
		assert sf(self.makeext("1")) == 0
		assert sf(self.makeext("1/1")) == 0
		assert sf(self.makeext("1/2/3")) == 0
		assert sf(self.makeext("2/2")) == None
		assert sf(self.makeext("3")) == None
		assert sf(self.makeext("3/3/3")) == 0

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


class ParseArgsTest(unittest.TestCase):
	"""Test argument parsing"""
	def ParseTest(self, tuplelist, indicies):
		"""No error if running select on tuple goes over indicies"""
		self.root = DSRPath(Globals.local_connection, "testfiles/select")
		self.Select = Select(self.root)
		self.Select.ParseArgs(tuplelist)
		self.Select.set_iter()
		print self.Select.next # just make sure it exists
		for i in self.Select: print i
		assert Iter.equal(Iter.map(lambda dsrp: dsrp.index, self.Select),
						  iter(indicies))

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

		
if __name__ == "__main__": unittest.main()
