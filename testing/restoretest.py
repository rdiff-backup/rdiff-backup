import unittest
import os
from commontest import abs_output_dir, old_test_dir, Myrm, MakeOutputDir, \
    InternalRestore, compare_recursive
from rdiff_backup import restore, Globals, rpath, Time, log

lc = Globals.local_connection
tempdir = rpath.RPath(Globals.local_connection, abs_output_dir)
restore_base_rp = rpath.RPath(Globals.local_connection,
                              os.path.join(old_test_dir, b"restoretest"))
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

    def add_rpath(self, rp, t):
        """Add rp, which represents what rf should be at given time t"""
        if t in self.time_rp_dict:
            raise KeyError(
                "Time {time} is already registered in {tdict}".format(
                    time=t, tdict=self.time_rp_dict))
        self.time_rp_dict[t] = rp

    def _compare_at_time(self, t):
        """Restore file, make sure it is the same at time t"""
        log.Log("Checking result at time %s" % (t, ), 7)
        tf = tempdir.get_temp_rpath()
        restore.MirrorStruct._mirror_time = mirror_time
        restore.MirrorStruct._rest_time = t
        self.rf.set_relevant_incs()
        out_rorpath = self.rf.get_attribs().getRORPath()
        correct_result = self.time_rp_dict[t]

        if out_rorpath.isreg():
            out_rorpath.setfile(self.rf.get_restore_fp())
        rpath.copy_with_attribs(out_rorpath, tf)
        if not tf._equal_verbose(correct_result, check_index=0):
            return ("Restored file {rest!s} isn't same "
                    "as original file {orig!s}.".format(
                        rest=tf, orig=correct_result))
        if tf.isreg():
            with tf.open("rb") as tf_fd, correct_result.open("rb") as corr_fd:
                if not rpath._cmp_file_obj(tf_fd, corr_fd):
                    return ("Content of restored file {rest!s} isn't same "
                            "as original file {orig!s}.".format(
                                rest=tf, orig=correct_result))
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


class RestoreTimeTest(unittest.TestCase):
    def test_time_from_session(self):
        """Test getting time from session number (as in Time._time_from_session)

        Test here instead of in timetest because it depends on an
        rdiff-backup-data directory already being laid out.

        """
        restore.MirrorStruct._mirror_time = None  # Reset
        Globals.rbdir = rpath.RPath(
            lc,
            os.path.join(old_test_dir, b"restoretest3", b"rdiff-backup-data"))
        self.assertEqual(Time.genstrtotime("0B"), Time._time_from_session(0))
        self.assertEqual(Time.genstrtotime("2B"), Time._time_from_session(2))
        self.assertEqual(Time.genstrtotime("23B"), Time._time_from_session(23))

        self.assertEqual(Time._time_from_session(0), 40000)
        self.assertEqual(Time._time_from_session(2), 20000)
        self.assertEqual(Time._time_from_session(5), 10000)


class RestoreTest(unittest.TestCase):
    """Test Restore class"""

    def get_rfcs(self):
        """Return available RestoreFileComparer objects"""
        base_rf = restore.RestoreFile(restore_base_rp, restore_base_rp, [])
        rfs = base_rf.yield_sub_rfs()
        rfcs = []
        for rf in rfs:
            if rf.mirror_rp.dirsplit()[1] in [b"dir"]:
                log.Log("skipping 'dir'", 5)
                continue

            rfc = RestoreFileComparer(rf)
            for inc in rf.inc_list:
                test_time = inc.getinctime()
                rfc.add_rpath(self.get_correct(rf.mirror_rp, test_time),
                              test_time)
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
        return restore_base_rp.append(b"%b.%b" %
                                      (basename, Time.timetobytes(test_time)))

    def testRestoreSingle(self):
        """Test restoring files one at at a time"""
        MakeOutputDir()
        for rfc in self.get_rfcs():
            if rfc.rf.inc_rp.isincfile():
                continue
            log.Log("Comparing %a" % (rfc.rf.inc_rp.path, ), 5)
            # compare all returns an empty list if everything is OK
            self.assertFalse(rfc.compare_all())

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
        Myrm(abs_output_dir)
        restore3_dir = os.path.join(old_test_dir, b"restoretest3")
        target_rp = rpath.RPath(Globals.local_connection, abs_output_dir)
        inc1_rp = rpath.RPath(Globals.local_connection,
                              os.path.join(old_test_dir, b"increment1"))
        inc2_rp = rpath.RPath(Globals.local_connection,
                              os.path.join(old_test_dir, b"increment2"))
        inc3_rp = rpath.RPath(Globals.local_connection,
                              os.path.join(old_test_dir, b"increment3"))
        inc4_rp = rpath.RPath(Globals.local_connection,
                              os.path.join(old_test_dir, b"increment4"))

        InternalRestore(mirror_local, dest_local, restore3_dir, abs_output_dir,
                        45000)
        self.assertTrue(
            compare_recursive(inc4_rp, target_rp))
        InternalRestore(mirror_local, dest_local, restore3_dir, abs_output_dir,
                        35000)
        self.assertTrue(
            compare_recursive(inc3_rp, target_rp, compare_hardlinks=0))
        InternalRestore(mirror_local, dest_local, restore3_dir, abs_output_dir,
                        25000)
        self.assertTrue(
            compare_recursive(inc2_rp, target_rp, compare_hardlinks=0))
        InternalRestore(mirror_local, dest_local, restore3_dir, abs_output_dir,
                        5000)
        self.assertTrue(
            compare_recursive(inc1_rp, target_rp, compare_hardlinks=0))

    def testRestoreNoincs(self):
        """Test restoring a directory with no increments, just mirror"""
        Myrm(abs_output_dir)
        InternalRestore(
            1, 1, os.path.join(old_test_dir, b'restoretest5', b'regular_file'),
            abs_output_dir, 10000)
        self.assertTrue(os.lstat(abs_output_dir))


if __name__ == "__main__":
    unittest.main()
