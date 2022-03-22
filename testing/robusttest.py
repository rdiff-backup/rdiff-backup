import os
import unittest

import commontest as comtst
from rdiff_backup import robust


class RobustTest(unittest.TestCase):
    """
    Test robust module
    """

    def test_check_common_error(self):
        """
        Test capturing errors (or not)
        """

        def cause_catchable_error(a):
            os.lstat("aoenuthaoeu/aosutnhcg.4fpr,38p")

        def cause_uncatchable_error():
            ansoethusaotneuhsaotneuhsaontehuaou  # noqa: F821 undefined name

        result = robust.check_common_error(None, cause_catchable_error, [1])
        self.assertIsNone(result)
        with self.assertRaises(NameError):
            robust.check_common_error(None, cause_uncatchable_error)

    @unittest.skipIf(os.name == "nt", "Test is meaningless under Windows")
    def test_check_failed_errorlog(self):
        """
        Validate that one unreadable file doesn't fail the whole backup
        """
        src_dir = os.path.join(comtst.old_test_dir, b"rpath2")
        base_dir = comtst.re_init_subdir(comtst.abs_test_dir, b"robust")
        target_dir = os.path.join(base_dir, b"bak")
        self.assertEqual(comtst.rdiff_backup_action(
            True, True, src_dir, target_dir,
            ("--api-version", "201"), b"backup", ()), 0)


if __name__ == '__main__':
    unittest.main()
