"""
Test the convert utils module
"""

import unittest

from rdiffbackup.utils import convert


class UtilsConvertTest(unittest.TestCase):
    """
    Test the convert module
    """

    def test_safe_convert(self):
        """Test conversion of bytes to str and back"""
        some_str = "Élégant schöne lady"
        self.assertEqual(some_str, convert.to_safe_str(convert.to_safe_bytes(some_str)))
        some_bytes = bytes.fromhex("2Ef0 F1f2  ")
        safe_str = convert.to_safe_str(some_bytes)
        self.assertIsInstance(safe_str, str)
        safe_bytes = convert.to_safe_bytes(safe_str)
        self.assertIsInstance(safe_bytes, bytes)

    def test_human_size_str(self):
        """Test conversion of bytes size to human readable strings"""
        f = convert.to_human_size_str
        self.assertEqual(f(1), "1 B")
        self.assertEqual(f(234), "234 B")
        self.assertEqual(f(2048), "2.00 KiB")
        self.assertEqual(f(3502243), "3.34 MiB")
        self.assertEqual(f(-314992230), "-300 MiB")
        self.assertEqual(f(36874871216), "34.3 GiB")
        self.assertEqual(f(3775986812573450), "3.35 PiB")
        self.assertEqual(f(999**9), "820 YiB")


if __name__ == "__main__":
    unittest.main()
