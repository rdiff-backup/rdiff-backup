import os
import unittest
from rdiff_backup import robust


class RobustTest(unittest.TestCase):
    """Test robust module"""

    def test_check_common_error(self):
        """Test capturing errors"""

        def cause_catchable_error(a):
            os.lstat("aoenuthaoeu/aosutnhcg.4fpr,38p")

        def cause_uncatchable_error():
            ansoethusaotneuhsaotneuhsaontehuaou  # noqa: F821 undefined name

        result = robust.check_common_error(None, cause_catchable_error, [1])
        self.assertIsNone(result)
        with self.assertRaises(NameError):
            robust.check_common_error(None, cause_uncatchable_error)


if __name__ == '__main__':
    unittest.main()
