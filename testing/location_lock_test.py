"""
Test the handling of locking with api version >= 201
"""
import os
import shutil
import unittest

from rdiff_backup import Globals, rpath
from rdiffbackup.locations import _repo_shadow

import commontest as comtst


class LocationLockTest(unittest.TestCase):
    """
    Test that rdiff-backup properly handles locking
    """

    def setUp(self):
        self.base_dir = os.path.join(comtst.abs_test_dir, b"location_lock")
        self.base_rp = rpath.RPath(Globals.local_connection, self.base_dir)
        self.lockfile = self.base_rp.append("lock")
        comtst.re_init_rpath_dir(self.base_rp)
        self.success = False

    def test_location_lock(self):
        """
        verify that all kinds of locking mechanisms do work properly
        """
        self.assertFalse(_repo_shadow.RepoShadow.is_locked(self.lockfile))
        self.assertTrue(_repo_shadow.RepoShadow.lock(self.lockfile))
        self.assertTrue(_repo_shadow.RepoShadow.is_locked(self.lockfile))
        self.assertFalse(_repo_shadow.RepoShadow.lock(self.lockfile))
        self.assertTrue(_repo_shadow.RepoShadow.lock(self.lockfile,
                                                     force=True))
        self.assertIsNone(_repo_shadow.RepoShadow.unlock(self.lockfile))
        self.assertFalse(_repo_shadow.RepoShadow.is_locked(self.lockfile))
        self.success = True

    def tearDown(self):
        # we clean-up only if the test was successful
        if self.success:
            shutil.rmtree(self.base_dir)


if __name__ == "__main__":
    unittest.main()
