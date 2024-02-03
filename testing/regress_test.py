"""
regresstest - test the regress module.

Not to be confused with the regression tests.
"""

import os
import unittest

import commontest as comtst

from rdiff_backup import Globals, rpath, Time

TEST_BASE_DIR = comtst.get_test_base_dir(__file__)


class RegressTest(unittest.TestCase):
    out_dir = os.path.join(TEST_BASE_DIR, b"output")
    out_rp = rpath.RPath(Globals.local_connection, out_dir)
    out_rbdir_rp = out_rp.append_path("rdiff-backup-data")
    incrp = []
    for i in range(4):
        incrp.append(
            rpath.RPath(
                Globals.local_connection,
                os.path.join(comtst.old_test_dir, b"increment%d" % (i + 1)),
            )
        )

    def runtest(self, regress_function):
        """Test regressing a full directory to older state

        Make two directories, one with one more backup in it.  Then
        regress the bigger one, and then make sure they compare the
        same.

        Regress_function takes a time and should regress
        self.out_rp back to that time.

        """
        self.out_rp.setdata()
        if self.out_rp.lstat():
            comtst.remove_dir(self.out_dir)

        comtst.rdiff_backup(1, 1, self.incrp[0].path, self.out_dir, current_time=10000)
        self.assertTrue(comtst.compare_recursive(self.incrp[0], self.out_rp))

        comtst.rdiff_backup(1, 1, self.incrp[1].path, self.out_dir, current_time=20000)
        self.assertTrue(comtst.compare_recursive(self.incrp[1], self.out_rp))

        comtst.rdiff_backup(1, 1, self.incrp[2].path, self.out_dir, current_time=30000)
        self.assertTrue(comtst.compare_recursive(self.incrp[2], self.out_rp))

        comtst.rdiff_backup(1, 1, self.incrp[3].path, self.out_dir, current_time=40000)
        self.assertTrue(comtst.compare_recursive(self.incrp[3], self.out_rp))

        Globals.rbdir = self.out_rbdir_rp

        regress_function(30000)
        self.assertTrue(
            comtst.compare_recursive(self.incrp[2], self.out_rp, compare_hardlinks=0)
        )
        regress_function(20000)
        self.assertTrue(
            comtst.compare_recursive(self.incrp[1], self.out_rp, compare_hardlinks=0)
        )
        regress_function(10000)
        self.assertTrue(
            comtst.compare_recursive(self.incrp[0], self.out_rp, compare_hardlinks=0)
        )

    def regress_to_time_local(self, time):
        """Regress self.out_rp to time by running regress locally"""
        self.out_rp.setdata()
        self.out_rbdir_rp.setdata()
        self.add_current_mirror(time)
        comtst.rdiff_backup_action(True, True, self.out_rp, None, (), b"regress", ())

    def add_current_mirror(self, time):
        """Add current_mirror marker at given time"""
        cur_mirror_rp = self.out_rbdir_rp.append(
            "current_mirror.%s.data" % (Time.timetostring(time),)
        )
        cur_mirror_rp.touch()

    def regress_to_time_remote(self, time):
        """Like test_full above, but run regress remotely"""
        self.out_rp.setdata()
        self.out_rbdir_rp.setdata()
        self.add_current_mirror(time)

        comtst.rdiff_backup(
            False,
            False,
            self.out_dir,
            None,
            extra_options=b"regress",
            expected_ret_code=Globals.RET_CODE_WARN,
        )

    def test_local(self):
        """Run regress test locally"""
        self.runtest(self.regress_to_time_local)

    def test_remote(self):
        """Run regress test remotely"""
        self.runtest(self.regress_to_time_remote)

    def test_unreadable(self):
        """Run regress test when regular file is unreadable"""
        self.out_rp.setdata()
        if self.out_rp.lstat():
            comtst.remove_dir(self.out_dir)
        unreadable_rp = self.make_unreadable()

        comtst.rdiff_backup(1, 1, unreadable_rp.path, self.out_dir, current_time=1)
        rbdir = self.out_rp.append("rdiff-backup-data")
        marker = rbdir.append("current_mirror.2000-12-31T21:33:20-07:00.data")
        marker.touch()
        self.change_unreadable()

        cmd = (b"rdiff-backup", b"regress", self.out_dir)
        print("Executing:", cmd)
        self.assertEqual(comtst.os_system(cmd), Globals.RET_CODE_WARN)

    def make_unreadable(self):
        """Make unreadable input directory

        The directory needs to be readable initially (otherwise it
        just won't get backed up, and then later we will turn it
        unreadable.

        """
        rp = rpath.RPath(
            Globals.local_connection, os.path.join(TEST_BASE_DIR, b"regress")
        )
        if rp.lstat():
            comtst.remove_dir(rp.path)
        rp.setdata()
        rp.mkdir()
        rp1 = rp.append("unreadable_dir")
        rp1.mkdir()
        rp1_1 = rp1.append("to_be_unreadable")
        rp1_1.write_string("aensuthaoeustnahoeu")
        return rp

    def change_unreadable(self):
        """Change attributes in directory, so regress will request fp"""
        subdir = self.out_rp.append("unreadable_dir")
        self.assertTrue(subdir.lstat())
        rp1_1 = subdir.append("to_be_unreadable")
        rp1_1.chmod(0)
        subdir.chmod(0)


if __name__ == "__main__":
    unittest.main()
