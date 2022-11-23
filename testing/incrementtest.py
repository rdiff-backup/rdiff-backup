import unittest
import os
import re
from commontest import old_test_dir, abs_output_dir, MakeOutputDir
from rdiff_backup import Globals, rpath, increment, Time, Rdiff
from rdiffbackup import actions

lc = Globals.local_connection
Globals.change_source_perms = 1


def getrp(ending):
    return rpath.RPath(
        lc, os.path.join(old_test_dir, b"various_file_types", ending))


base_dir = getrp(b".")
rf = getrp(b"regular_file")
rf2 = getrp(b"two_hardlinked_files1")
exec1 = getrp(b"executable")
sym = getrp(b"symbolic_link")
nothing = getrp(b"nothing")

target = rpath.RPath(lc, os.path.join(abs_output_dir, b"out"))
out2 = rpath.RPath(lc, os.path.join(abs_output_dir, b"out2"))
out_gz = rpath.RPath(lc, os.path.join(abs_output_dir, b"out.gz"))

Time.set_current_time(1000000000)
Time.setprevtime_compat200(999424113)
if os.name == "nt":
    prevtimestr = b"2001-09-02T02-48-33-07-00"
else:
    prevtimestr = b"2001-09-02T02:48:33-07:00"
t_diff = os.path.join(abs_output_dir, b"out.%s.diff" % prevtimestr)

Globals.postset_regexp_local("no_compression_regexp",
                             actions.DEFAULT_NOT_COMPRESSED_REGEXP, re.I)


class inctest(unittest.TestCase):
    """Test the incrementRP function"""

    def setUp(self):
        Globals.set('isbackup_writer', 1)
        MakeOutputDir()

    def check_time(self, rp):
        """Make sure that rp is an inc file, and time is Time.prevtime"""
        self.assertTrue(rp.isincfile())
        t = rp.getinctime()
        self.assertEqual(t, Time.prevtime)

    def testreg(self):
        """Test increment of regular files"""
        Globals.compression = None
        target.setdata()
        if target.lstat():
            target.delete()
        rpd = rpath.RPath(lc, t_diff)
        if rpd.lstat():
            rpd.delete()

        diffrp = increment.Increment(rf, exec1, target)
        self.assertTrue(diffrp.isreg())
        self.assertTrue(
            diffrp._equal_verbose(exec1, check_index=0, compare_size=0))
        self.check_time(diffrp)
        self.assertEqual(diffrp.getinctype(), b'diff')
        diffrp.delete()

    def testmissing(self):
        """Test creation of missing files"""
        missing_rp = increment.Increment(rf, nothing, target)
        self.check_time(missing_rp)
        self.assertEqual(missing_rp.getinctype(), b'missing')
        missing_rp.delete()

    @unittest.skipIf(os.name == "nt", "Symlinks not supported under Windows")
    def testsnapshot(self):
        """Test making of a snapshot"""
        Globals.compression = None
        snap_rp = increment.Increment(rf, sym, target)
        self.check_time(snap_rp)
        self.assertTrue(rpath._cmp_file_attribs(snap_rp, sym))
        self.assertTrue(rpath.cmp(snap_rp, sym))
        snap_rp.delete()

        snap_rp2 = increment.Increment(sym, rf, target)
        self.check_time(snap_rp2)
        self.assertTrue(snap_rp2._equal_verbose(rf, check_index=0))
        self.assertTrue(rpath.cmp(snap_rp2, rf))
        snap_rp2.delete()

    @unittest.skipIf(os.name == "nt", "Symlinks not supported under Windows")
    def testGzipsnapshot(self):
        """Test making a compressed snapshot"""
        Globals.compression = 1
        rp = increment.Increment(rf, sym, target)
        self.check_time(rp)
        self.assertTrue(rp._equal_verbose(sym, check_index=0, compare_size=0))
        self.assertTrue(rpath.cmp(rp, sym))
        rp.delete()

        rp = increment.Increment(sym, rf, target)
        self.check_time(rp)
        self.assertTrue(rp._equal_verbose(rf, check_index=0, compare_size=0))
        with rp.open("rb", 1) as rp_fd, rf.open("rb") as rf_fd:
            self.assertTrue(rpath._cmp_file_obj(rp_fd, rf_fd))
        self.assertTrue(rp.isinccompressed())
        rp.delete()

    @unittest.skipIf(os.name == "nt", "Symlinks not supported under Windows")
    def testdir(self):
        """Test increment on base_dir"""
        rp = increment.Increment(sym, base_dir, target)
        self.check_time(rp)
        self.assertTrue(rp.lstat())
        self.assertTrue(target.isdir())
        self.assertTrue(base_dir._equal_verbose(rp, check_index=0,
                                                compare_size=0,
                                                compare_type=0))
        self.assertTrue(rp.isreg())
        rp.delete()
        target.delete()

    def testDiff(self):
        """Test making diffs"""
        Globals.compression = None
        rp = increment.Increment(rf, rf2, target)
        self.check_time(rp)
        self.assertTrue(rp._equal_verbose(rf2, check_index=0, compare_size=0))
        Rdiff.patch_local(rf, rp, out2)
        self.assertTrue(rpath.cmp(rf2, out2))
        rp.delete()
        out2.delete()

    def testGzipDiff(self):
        """Test making gzipped diffs"""
        Globals.compression = 1
        rp = increment.Increment(rf, rf2, target)
        self.check_time(rp)
        self.assertTrue(rp._equal_verbose(rf2, check_index=0, compare_size=0))
        Rdiff.patch_local(rf, rp, out2, delta_compressed=1)
        self.assertTrue(rpath.cmp(rf2, out2))
        rp.delete()
        out2.delete()

    def testGzipRegexp(self):
        """Here a .gz file shouldn't be compressed"""
        Globals.compression = 1
        rpath.copy(rf, out_gz)
        self.assertTrue(out_gz.lstat())

        rp = increment.Increment(rf, out_gz, target)
        self.check_time(rp)
        self.assertTrue(
            rp._equal_verbose(out_gz, check_index=0, compare_size=0))
        Rdiff.patch_local(rf, rp, out2)
        self.assertTrue(rpath.cmp(out_gz, out2))
        rp.delete()
        out2.delete()
        out_gz.delete()


if __name__ == '__main__':
    unittest.main()
