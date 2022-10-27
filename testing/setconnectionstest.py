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
        self.assertEqual(pl(b"a:b:c:d::e"), (b"a:b:c:d", b"e", None))
        self.assertEqual(pl(b"foobar"), (None, b"foobar", None))
        self.assertEqual(pl(rb"test\\ing\::more::and more\\.."),
                         (b"test\\ing::more", b"and more/..", None))
        self.assertEqual(pl(rb"strangely named\::file"),
                         (None, b"strangely named::file", None))
        self.assertEqual(pl(rb"foobar\\"), (None, b"foobar/", None))
        self.assertEqual(pl(rb"not\::too::many\\\::paths"),
                         (b"not::too", b"many/::paths", None))
        self.assertEqual(pl(rb"\\hostname\unc\path"),
                         (None, b"//hostname/unc/path", None))
        self.assertEqual(pl(rb"remotehost::\\hostname\unc\path"),
                         (b"remotehost", b"//hostname/unc/path", None))

        # test missing path and missing host
        self.assertIsNotNone(pl(rb"a host without\:path::")[2])
        self.assertIsNotNone(pl(b"::some/path/without/host")[2])
        self.assertIsNotNone(pl(b"too::many::paths")[2])


if __name__ == "__main__":
    unittest.main()
