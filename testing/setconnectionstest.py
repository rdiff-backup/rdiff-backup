import unittest
from rdiff_backup import SetConnections


class SetConnectionsTest(unittest.TestCase):
    """Set SetConnections Class"""

    def testParsing(self):
        """Test parsing of various file descriptors"""
        pfd = SetConnections.parse_file_desc
        self.assertEqual(pfd(b"bescoto@folly.stanford.edu::/usr/bin/ls"),
                         (b"bescoto@folly.stanford.edu", b"/usr/bin/ls"))
        self.assertEqual(pfd(b"hello there::/goodbye:euoeu"),
                         (b"hello there", b"/goodbye:euoeu"))
        self.assertEqual(pfd(rb"test\\ing\::more::and more\\.."),
                         (rb"test\ing::more", rb"and more\\.."))
        self.assertEqual(pfd(b"a:b:c:d::e"), (b"a:b:c:d", b"e"))
        self.assertEqual(pfd(b"foobar"), (None, b"foobar"))
        self.assertEqual(pfd(rb"hello\::there"), (None, rb"hello\::there"))
        self.assertEqual(pfd(rb"foobar\\"), (None, rb"foobar\\"))

        # test missing path and missing host
        self.assertRaises(SetConnections.SetConnectionsException, pfd, rb"hello\:there::")
        self.assertRaises(SetConnections.SetConnectionsException, pfd, b"::some/path/without/host")


if __name__ == "__main__":
    unittest.main()
