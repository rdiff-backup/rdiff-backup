import unittest, StringIO
execfile("commontest.py")
rbexec("filelist.py")


class FilelistTest(unittest.TestCase):
	"""Test Filelist class"""
	def testFile2Iter(self):
		"""Test File2Iter function"""
		filelist = """
hello
goodbye
a/b/c

test"""
		baserp = RPath(Globals.local_connection, "/base")
		i = Filelist.File2Iter(StringIO.StringIO(filelist), baserp)
		assert i.next().path == "/base/hello"
		assert i.next().path == "/base/goodbye"
		assert i.next().path == "/base/a/b/c"
		assert i.next().path == "/base/test"
		self.assertRaises(StopIteration, i.next)

	def testmake_subdirs(self):
		"""Test Filelist.make_subdirs"""
		self.assertRaises(os.error, os.lstat, "foo_delete_me")
		Filelist.make_subdirs(RPath(Globals.local_connection,
									"foo_delete_me/a/b/c/d"))
		os.lstat("foo_delete_me")
		os.lstat("foo_delete_me/a")
		os.lstat("foo_delete_me/a/b")
		os.lstat("foo_delete_me/a/b/c")
		os.system("rm -rf foo_delete_me")

if __name__ == "__main__": unittest.main()
