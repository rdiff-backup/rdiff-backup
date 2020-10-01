import unittest
from rdiff_backup import C


class CTest(unittest.TestCase):
    """Test the C module by comparing results to python functions"""

    def test_sync(self):
        """Test running C.sync"""
        C.sync()

    def test_acl_quoting(self):
        """Test the acl_quote and acl_unquote functions"""
        self.assertEqual(C.acl_quote(b'foo'), b'foo')
        self.assertEqual(C.acl_quote(b'\n'), b'\\012')
        self.assertEqual(C.acl_unquote(b'\\012'), b'\n')
        s = b'\\\n\t\145\n\01=='
        self.assertEqual(C.acl_unquote(C.acl_quote(s)), s)

    def test_acl_quoting2(self):
        """This string used to segfault the quoting code, try now"""
        s = b'\xd8\xab\xb1Wb\xae\xc5]\x8a\xbb\x15v*\xf4\x0f!\xf9>\xe2Y\x86\xbb\xab\xdbp\xb0\x84\x13k\x1d\xc2\xf1\xf5e\xa5U\x82\x9aUV\xa0\xf4\xdf4\xba\xfdX\x03\x82\x07s\xce\x9e\x8b\xb34\x04\x9f\x17 \xf4\x8f\xa6\xfa\x97\xab\xd8\xac\xda\x85\xdcKvC\xfa#\x94\x92\x9e\xc9\xb7\xc3_\x0f\x84g\x9aB\x11<=^\xdbM\x13\x96c\x8b\xa7|*"\\\'^$@#!(){}?+ ~` '
        quoted = C.acl_quote(s)
        self.assertEqual(C.acl_unquote(quoted), s)

    def test_acl_quoting_equals(self):
        """Make sure the equals character is quoted"""
        self.assertNotEqual(C.acl_quote(b'='), b'=')


if __name__ == "__main__":
    unittest.main()
