import unittest
from rdiff_backup import SetConnections


class SetConnectionsTest(unittest.TestCase):
    """Set SetConnections Class"""

    def testParsing(self):
        """Test parsing of various file descriptors"""
        pfd = SetConnections.parse_file_desc
        assert pfd(b"bescoto@folly.stanford.edu::/usr/bin/ls") == \
            (b"bescoto@folly.stanford.edu", b"/usr/bin/ls")
        assert pfd(b"hello there::/goodbye:euoeu") == \
            (b"hello there", b"/goodbye:euoeu")
        assert pfd(rb"test\\ing\::more::and more\\..") == \
            (rb"test\ing::more", rb"and more\\.."), \
            pfd(r"test\\ing\::more::and more\\..")
        assert pfd(b"a:b:c:d::e") == (b"a:b:c:d", b"e")
        assert pfd(b"foobar") == (None, b"foobar")
        assert pfd(rb"hello\::there") == (None, rb"hello\::there")

        self.assertRaises(SetConnections.SetConnectionsException, pfd,
                          rb"hello\:there::")
        self.assertRaises(SetConnections.SetConnectionsException, pfd,
                          b"foobar\\")


if __name__ == "__main__":
    unittest.main()
