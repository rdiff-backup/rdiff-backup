import unittest, StringIO
from commontest import *
from rdiff_backup.iterfile import *
from rdiff_backup import lazy

class FileException:
	"""Like a file, but raise exception after certain # bytes read"""
	def __init__(self, max):
		self.count = 0
		self.max = max
	def read(self, l):
		self.count += l
		if self.count > self.max: raise IOError(13, "Permission Denied")
		return "a"*l
	def close(self): return None


class testIterFile(unittest.TestCase):
	def setUp(self):
		self.iter1maker = lambda: iter(range(50))
		self.iter2maker = lambda: iter(map(str, range(50)))

	def testConversion(self):
		"""Test iter to file conversion"""
		for itm in [self.iter1maker, self.iter2maker]:
			assert lazy.Iter.equal(itm(),
								   IterWrappingFile(FileWrappingIter(itm())))

	def testFile(self):
		"""Test sending files through iters"""
		buf1 = "hello"*10000
		file1 = StringIO.StringIO(buf1)
		buf2 = "goodbye"*10000
		file2 = StringIO.StringIO(buf2)
		file_iter = FileWrappingIter(iter([file1, file2]))

		new_iter = IterWrappingFile(file_iter)
		assert new_iter.next().read() == buf1
		assert new_iter.next().read() == buf2
		self.assertRaises(StopIteration, new_iter.next)

	def testFileException(self):
		"""Test encoding a file which raises an exception"""
		f = FileException(100*1024)
		new_iter = IterWrappingFile(FileWrappingIter(iter([f, "foo"])))
		f_out = new_iter.next()
		assert f_out.read(10000) == "a"*10000
		try: buf = f_out.read(100*1024)
		except IOError: pass
		else: assert 0, len(buf)

		assert new_iter.next() == "foo"
		self.assertRaises(StopIteration, new_iter.next)

		
class testBufferedRead(unittest.TestCase):
	def testBuffering(self):
		"""Test buffering a StringIO"""
		fp = StringIO.StringIO("12345678"*10000)
		bfp = BufferedRead(fp)
		assert bfp.read(5) == "12345"
		assert bfp.read(4) == "6781"
		assert len(bfp.read(75000)) == 75000


if __name__ == "__main__": unittest.main()
