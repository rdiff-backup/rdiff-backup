import unittest
from commontest import *
from C import *
from rpath import *

class CTest(unittest.TestCase):
	"""Test the C module by comparing results to python functions"""
	def test_make_dict(self):
		"""Test making stat dictionaries"""
		rp1 = RPath(Globals.local_connection, "/dev/ttyS1")
		rp2 = RPath(Globals.local_connection, "./ctest.py")
		rp3 = RPath(Globals.local_connection, "aestu/aeutoheu/oeu")
		rp4 = RPath(Globals.local_connection, "testfiles/various_file_types/symbolic_link")
		rp5 = RPath(Globals.local_connection, "testfiles/various_file_types/fifo")

		for rp in [rp1, rp2, rp3, rp4, rp5]:
			dict1 = rp.make_file_dict_old()
			dict2 = C.make_file_dict(rp.path)
			if dict1 != dict2:
				print "Python dictionary: ", dict1
				print "not equal to C dictionary: ", dict2
				print "for path ", rp.path
				assert 0

	def test_strlong(self):
		"""Test str2long and long2str"""
		self.assertRaises(TypeError, C.long2str, "hello")
		self.assertRaises(TypeError, C.str2long, 34)
		self.assertRaises(TypeError, C.str2long, "oeuo")
		self.assertRaises(TypeError, C.str2long, "oeuoaoeuaoeu")

		for s in ["\0\0\0\0\0\0\0", "helloto",
				  "\xff\xff\xff\xff\xff\xff\xff", "randoms"]:
			assert len(s) == 7, repr(s)
			s_out = C.long2str(C.str2long(s))
			assert s_out == s, (s_out, C.str2long(s), s)
		for l in 0L, 1L, 4000000000L, 34234L, 234234234L:
			assert C.str2long(C.long2str(l)) == l


if __name__ == "__main__": unittest.main()
