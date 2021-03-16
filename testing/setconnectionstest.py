import unittest
from rdiff_backup import SetConnections


class SetConnectionsTest(unittest.TestCase):
    """Set SetConnections Class"""

    def testParsing(self):
        """Test parsing of various file descriptors"""

        pl = SetConnections.parse_location

        self.assertEqual(pl(b"bescoto@folly.stanford.edu::/usr/bin/ls"),
                         (b"bescoto@folly.stanford.edu", b"/usr/bin/ls", None))
        self.assertEqual(pl(b"hello there::/goodbye:euoeu"),
                         (b"hello there", b"/goodbye:euoeu", None))
        self.assertEqual(pl(rb"test\\ing\::more::and more\\.."),
                         (rb"test\ing::more", rb"and more\\..", None))
        self.assertEqual(pl(b"a:b:c:d::e"), (b"a:b:c:d", b"e", None))
        self.assertEqual(pl(b"foobar"), (None, b"foobar", None))
        self.assertEqual(pl(rb"hello\::there"), (None, rb"hello\::there", None))
        self.assertEqual(pl(rb"foobar\\"), (None, rb"foobar\\", None))

        # test missing path and missing host
        self.assertIsNotNone(pl(rb"hello\:there::")[2])
        self.assertIsNotNone(pl(b"::some/path/without/host")[2])


if __name__ == "__main__":
    unittest.main()
