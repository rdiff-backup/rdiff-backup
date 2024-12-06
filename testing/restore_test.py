"""
Test the restore action
"""

import os
import unittest

import commontest as comtst

from rdiff_backup import rpath, Time
from rdiffbackup.locations import _repo_shadow
from rdiffbackup.singletons import log, specifics

TEST_BASE_DIR = comtst.get_test_base_dir(__file__)

lc = specifics.local_connection
restore_base_rp = rpath.RPath(
    specifics.local_connection, os.path.join(comtst.old_test_dir, b"restoretest")
)
restore_base_filenames = restore_base_rp.listdir()
mirror_time = 1041109438  # just some late time


class RestoreFileComparer:
    """Holds a file to be restored and tests against it

    Each object has a restore file and a dictionary of times ->
    rpaths.  When the restore file is restored to one of the given
    times, the resulting file should be the same as the related rpath.

    """

    def __init__(self, rf):
        self.rf = rf
        self.time_rp_dict = {}
        self.out_dir = os.path.join(TEST_BASE_DIR, b"output")
        self.out_rp = rpath.RPath(specifics.local_connection, self.out_dir)

    def add_rpath(self, rp, t):
        """Add rp, which represents what rf should be at given time t"""
        if t in self.time_rp_dict:
            raise KeyError(
                "Time {time} is already registered in {tdict}".format(
                    time=t, tdict=self.time_rp_dict
                )
            )
        self.time_rp_dict[t] = rp

    def _compare_at_time(self, t):
        """Restore file, make sure it is the same at time t"""
        log.Log("Checking result at time %s" % (t,), 7)
        tf = self.out_rp.get_temp_rpath()
        _repo_shadow.RepoShadow._mirror_time = mirror_time
        _repo_shadow.RepoShadow._restore_time = t
        self.rf.set_relevant_incs()
        out_rorpath = self.rf.get_attribs().getRORPath()
        correct_result = self.time_rp_dict[t]

        if out_rorpath.isreg():
            out_rorpath.setfile(self.rf.get_restore_fp())
        rpath.copy_with_attribs(out_rorpath, tf)
        if not tf._equal_verbose(correct_result, check_index=0):
            return (
                "Restored file {rest!s} isn't same "
                "as original file {orig!s}.".format(rest=tf, orig=correct_result)
            )
        if tf.isreg():
            with tf.open("rb") as tf_fd, correct_result.open("rb") as corr_fd:
                if not rpath._cmp_file_obj(tf_fd, corr_fd):
                    return (
                        "Content of restored file {rest!s} isn't same "
                        "as original file {orig!s}.".format(
                            rest=tf, orig=correct_result
                        )
                    )
        if tf.lstat():
            tf.delete()
        return ()  # no error found

    def compare_all(self):
        """Check restore results for all available times and return a list
        of errors, empty if everything is fine."""
        errors = []
        for t in list(self.time_rp_dict.keys()):
            errors.extend(self._compare_at_time(t))
        return errors


class RestoreTest(unittest.TestCase):
    """Test Restore class"""

    out_dir = os.path.join(TEST_BASE_DIR, b"output")

    def get_rfcs(self):
        """Return available RestoreFileComparer objects"""
        base_rf = _repo_shadow._RestoreFile(restore_base_rp, restore_base_rp, [])
        rfs = base_rf.yield_sub_rfs()
        rfcs = []
        for rf in rfs:
            if rf.mirror_rp.dirsplit()[1] in [b"dir"]:
                log.Log("skipping 'dir'", 5)
                continue

            rfc = RestoreFileComparer(rf)
            for inc in rf.inc_list:
                test_time = inc.getinctime()
                rfc.add_rpath(self.get_correct(rf.mirror_rp, test_time), test_time)
            rfc.add_rpath(rf.mirror_rp, mirror_time)
            rfcs.append(rfc)
        return rfcs

    def get_correct(self, mirror_rp, test_time):
        """Return correct version with base mirror_rp at time test_time"""
        self.assertGreater(test_time, -1)
        self.assertLess(test_time, 2000000000)
        dirname, basename = mirror_rp.dirsplit()
        for filename in restore_base_filenames:
            comps = filename.split(b".")
            base = b".".join(comps[:-1])
            t = Time.bytestotime(comps[-1])
            if t == test_time and basename == base:
                return restore_base_rp.append(filename)
        # Correct rp must be empty
        return restore_base_rp.append(
            b"%b.%b" % (basename, Time.timetobytes(test_time))
        )

    def testBothLocal(self):
        """Test directory restore everything local"""
        self.restore_dir_test(1, 1)

    def testMirrorRemote(self):
        """Test directory restore mirror is remote"""
        self.restore_dir_test(0, 1)

    def testDestRemote(self):
        """Test directory restore destination is remote"""
        self.restore_dir_test(1, 0)

    def testBothRemote(self):
        """Test directory restore everything is remote"""
        self.restore_dir_test(0, 0)

    def restore_dir_test(self, mirror_local, dest_local):
        """Run whole dir tests

        If any of the above tests don't work, try rerunning
        makerestoretest3.

        """
        comtst.remove_dir(self.out_dir)
        restore3_dir = os.path.join(comtst.old_test_dir, b"restoretest3")
        target_rp = rpath.RPath(specifics.local_connection, self.out_dir)
        inc1_rp = rpath.RPath(
            specifics.local_connection, os.path.join(comtst.old_test_dir, b"increment1")
        )
        inc2_rp = rpath.RPath(
            specifics.local_connection, os.path.join(comtst.old_test_dir, b"increment2")
        )
        inc3_rp = rpath.RPath(
            specifics.local_connection, os.path.join(comtst.old_test_dir, b"increment3")
        )
        inc4_rp = rpath.RPath(
            specifics.local_connection, os.path.join(comtst.old_test_dir, b"increment4")
        )

        comtst.InternalRestore(
            mirror_local, dest_local, restore3_dir, self.out_dir, 45000
        )
        self.assertTrue(comtst.compare_recursive(inc4_rp, target_rp))
        comtst.InternalRestore(
            mirror_local, dest_local, restore3_dir, self.out_dir, 35000
        )
        self.assertTrue(
            comtst.compare_recursive(inc3_rp, target_rp, compare_hardlinks=0)
        )
        comtst.InternalRestore(
            mirror_local, dest_local, restore3_dir, self.out_dir, 25000
        )
        self.assertTrue(
            comtst.compare_recursive(inc2_rp, target_rp, compare_hardlinks=0)
        )
        comtst.InternalRestore(
            mirror_local, dest_local, restore3_dir, self.out_dir, 5000
        )
        self.assertTrue(
            comtst.compare_recursive(inc1_rp, target_rp, compare_hardlinks=0)
        )

    def testRestoreNoincs(self):
        """Test restoring a directory with no increments, just mirror"""
        comtst.remove_dir(self.out_dir)
        comtst.InternalRestore(
            1,
            1,
            os.path.join(comtst.old_test_dir, b"restoretest5", b"regular_file"),
            self.out_dir,
            10000,
        )
        self.assertTrue(os.lstat(self.out_dir))


if __name__ == "__main__":
    unittest.main()
