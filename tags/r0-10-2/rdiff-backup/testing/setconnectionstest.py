import unittest
from commontest import *
import SetConnections

class SetConnectionsTest(unittest.TestCase):
	"""Set SetConnections Class"""
	def testParsing(self):
		"""Test parsing of various file descriptors"""
		pfd = SetConnections.parse_file_desc
		assert pfd("bescoto@folly.stanford.edu::/usr/bin/ls") == \
			   ("bescoto@folly.stanford.edu", "/usr/bin/ls")
		assert pfd("hello there::/goodbye:euoeu") == \
			   ("hello there", "/goodbye:euoeu")
		assert pfd(r"test\\ing\::more::and more\\..") == \
			   (r"test\ing::more", r"and more\\.."), \
			   pfd(r"test\\ing\::more::and more\\..")
		assert pfd("a:b:c:d::e") == ("a:b:c:d", "e")
		assert pfd("foobar") == (None, "foobar")
		assert pfd(r"hello\::there") == (None, "hello\::there")

		self.assertRaises(SetConnections.SetConnectionsException,
						  pfd, r"hello\:there::")
		self.assertRaises(SetConnections.SetConnectionsException,
						  pfd, "foobar\\")


if __name__ == "__main__": unittest.main()
