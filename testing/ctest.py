import unittest
from commontest import *
from rdiff_backup import C
from rdiff_backup.rpath import *

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

	def test_sync(self):
		"""Test running C.sync"""
		C.sync()

	def test_acl_quoting(self):
		"""Test the acl_quote and acl_unquote functions"""
		assert C.acl_quote('foo') == 'foo', C.acl_quote('foo')
		assert C.acl_quote('\n') == '\\012', C.acl_quote('\n')
		assert C.acl_unquote('\\012') == '\n'
		s = '\\\n\t\145\n\01=='
		assert C.acl_unquote(C.acl_quote(s)) == s

	def test_acl_quoting2(self):
		"""This string used to segfault the quoting code, try now"""
		s = '\xd8\xab\xb1Wb\xae\xc5]\x8a\xbb\x15v*\xf4\x0f!\xf9>\xe2Y\x86\xbb\xab\xdbp\xb0\x84\x13k\x1d\xc2\xf1\xf5e\xa5U\x82\x9aUV\xa0\xf4\xdf4\xba\xfdX\x03\x82\x07s\xce\x9e\x8b\xb34\x04\x9f\x17 \xf4\x8f\xa6\xfa\x97\xab\xd8\xac\xda\x85\xdcKvC\xfa#\x94\x92\x9e\xc9\xb7\xc3_\x0f\x84g\x9aB\x11<=^\xdbM\x13\x96c\x8b\xa7|*"\\\'^$@#!(){}?+ ~` '
		quoted = C.acl_quote(s)
		assert C.acl_unquote(quoted) == s

	def test_acl_quoting_equals(self):
		"""Make sure the equals character is quoted"""
		assert C.acl_quote('=') != '='

if __name__ == "__main__": unittest.main()
