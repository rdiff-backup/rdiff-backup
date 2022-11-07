import os
import unittest
import commontest as comtst


class ActionTestTest(unittest.TestCase):
    """Test api versioning functionality"""
    def setUp(self):
        if os.name == "nt":
            self.dir1 = b"C:\\"
            self.dir2 = b"C:\\"
        else:
            self.dir1 = b"/tmp"
            self.dir2 = b"/var/tmp"

    def test_action_test(self):
        """test the "test" action"""
        # the test action works with one or two locations (or more)
        self.assertEqual(
            comtst.rdiff_backup_action(False, False, self.dir1, self.dir2,
                                       (), b"test", ()),
            0)
        self.assertEqual(
            comtst.rdiff_backup_action(False, True, self.dir1, None,
                                       (), b"test", ()),
            0)
        # but it doesn't work with a local one
        self.assertNotEqual(
            comtst.rdiff_backup_action(False, True, self.dir1, self.dir2,
                                       (), b"test", ()),
            0)
        # and it doesn't work without any location
        self.assertNotEqual(
            comtst.rdiff_backup_action(True, True, None, None,
                                       (), b"test", ()),
            0)


if __name__ == "__main__":
    unittest.main()
