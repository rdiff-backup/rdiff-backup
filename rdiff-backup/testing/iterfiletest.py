import unittest, StringIO
from commontest import *
from iterfile import *


class testIterFile(unittest.TestCase):
	def setUp(self):
		self.iter1maker = lambda: iter(range(50))
		self.iter2maker = lambda: iter(map(str, range(50)))

	def testConversion(self):
		"""Test iter to file conversion"""
		for itm in [self.iter1maker, self.iter2maker]:
			assert Iter.equal(itm(),
							  IterWrappingFile(FileWrappingIter(itm())))

class testBufferedRead(unittest.TestCase):
	def testBuffering(self):
		"""Test buffering a StringIO"""
		fp = StringIO.StringIO("12345678"*10000)
		bfp = BufferedRead(fp)
		assert bfp.read(5) == "12345"
		assert bfp.read(4) == "6781"
		assert len(bfp.read(75000)) == 75000


if __name__ == "__main__": unittest.main()
