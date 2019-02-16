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
		f = FileException(200*1024) # size depends on buffer size
		new_iter = IterWrappingFile(FileWrappingIter(iter([f, "foo"])))
		f_out = new_iter.next()
		assert f_out.read(50000) == "a"*50000
		try: buf = f_out.read(190*1024)
		except IOError: pass
		else: assert 0, len(buf)

		assert new_iter.next() == "foo"
		self.assertRaises(StopIteration, new_iter.next)


class testMiscIters(unittest.TestCase):
	"""Test sending rorpiter back and forth"""
	def setUp(self):
		"""Make testfiles/output directory and a few files"""
		Myrm("testfiles/output")
		self.outputrp = rpath.RPath(Globals.local_connection,
									"testfiles/output")
		self.regfile1 = self.outputrp.append("reg1")
		self.regfile2 = self.outputrp.append("reg2")
		self.regfile3 = self.outputrp.append("reg3")

		self.outputrp.mkdir()

		fp = self.regfile1.open("wb")
		fp.write("hello")
		fp.close()
		self.regfile1.setfile(self.regfile1.open("rb"))

		self.regfile2.touch()
		self.regfile2.setfile(self.regfile2.open("rb"))

		fp = self.regfile3.open("wb")
		fp.write("goodbye")
		fp.close()
		self.regfile3.setfile(self.regfile3.open("rb"))
		
		self.regfile1.setdata()
		self.regfile2.setdata()
		self.regfile3.setdata()
		
	def print_MiscIterFile(self, rpiter_file):
		"""Print the given rorpiter file"""
		while 1:
			buf = rpiter_file.read()
			sys.stdout.write(buf)
			if buf[0] == "z": break

	def testBasic(self):
		"""Test basic conversion"""
		l = [self.outputrp, self.regfile1, self.regfile2, self.regfile3]
		i_out = FileToMiscIter(MiscIterToFile(iter(l)))

		out1 = i_out.next()
		assert out1 == self.outputrp

		out2 = i_out.next()
		assert out2 == self.regfile1
		fp = out2.open("rb")
		assert fp.read() == "hello"
		assert not fp.close()

		out3 = i_out.next()
		assert out3 == self.regfile2
		fp = out3.open("rb")
		assert fp.read() == ""
		assert not fp.close()

		i_out.next()
		self.assertRaises(StopIteration, i_out.next)

	def testMix(self):
		"""Test a mix of RPs and ordinary objects"""
		l = [5, self.regfile3, "hello"]
		s = MiscIterToFile(iter(l)).read()
		i_out = FileToMiscIter(StringIO.StringIO(s))

		out1 = i_out.next()
		assert out1 == 5, out1

		out2 = i_out.next()
		assert out2 == self.regfile3
		fp = out2.open("rb")
		assert fp.read() == "goodbye"
		assert not fp.close()

		out3 = i_out.next()
		assert out3 == "hello", out3

		self.assertRaises(StopIteration, i_out.next)

	def testFlush(self):
		"""Test flushing property of MiscIterToFile"""
		l = [self.outputrp, MiscIterFlush, self.outputrp]
		filelike = MiscIterToFile(iter(l))
		new_filelike = StringIO.StringIO((filelike.read() + "z" +
										  C.long2str(0L)))

		i_out = FileToMiscIter(new_filelike)
		assert i_out.next() == self.outputrp
		self.assertRaises(StopIteration, i_out.next)

		i_out2 = FileToMiscIter(filelike)
		assert i_out2.next() == self.outputrp
		self.assertRaises(StopIteration, i_out2.next)

	def testFlushRepeat(self):
		"""Test flushing like above, but have Flush obj emerge from iter"""
		l = [self.outputrp, MiscIterFlushRepeat, self.outputrp]
		filelike = MiscIterToFile(iter(l))
		new_filelike = StringIO.StringIO((filelike.read() + "z" +
										  C.long2str(0L)))

		i_out = FileToMiscIter(new_filelike)
		assert i_out.next() == self.outputrp
		assert i_out.next() is MiscIterFlushRepeat
		self.assertRaises(StopIteration, i_out.next)

		i_out2 = FileToMiscIter(filelike)
		assert i_out2.next() == self.outputrp
		self.assertRaises(StopIteration, i_out2.next)



if __name__ == "__main__": unittest.main()
