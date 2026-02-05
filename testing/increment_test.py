"""
Test increment functions
"""

import os
import unittest

import commontest as comtst

from rdiff_backup import rpath, Time, Rdiff
from rdiffbackup import actions
from rdiffbackup.locations import increment
from rdiffbackup.singletons import specifics

TEST_BASE_DIR = comtst.get_test_base_dir(__file__)

lc = specifics.local_connection


def getrp(ending):
    return increment.StoredRPath(
        lc, os.path.join(comtst.old_test_dir, b"various_file_types", ending)
    )


base_dir = getrp(b".")
rf = getrp(b"regular_file")
rf2 = getrp(b"two_hardlinked_files1")
exec1 = getrp(b"executable")
sym = getrp(b"symbolic_link")
nothing = getrp(b"nothing")

target = increment.StoredRPath(lc, os.path.join(TEST_BASE_DIR, b"out"))
out2 = rpath.RPath(lc, os.path.join(TEST_BASE_DIR, b"out2"))
out_gz = rpath.RPath(lc, os.path.join(TEST_BASE_DIR, b"out.gz"))

Time.set_current_time(1000000000)
prevtime = 999424113
if os.name == "nt":
    prevtimestr = b"2001-09-02T02-48-33-07-00"
else:
    prevtimestr = b"2001-09-02T02:48:33-07:00"
t_diff = os.path.join(TEST_BASE_DIR, b"out.%s.diff" % prevtimestr)


class IncrementTest(unittest.TestCase):
    """Test the incrementRP function"""

    def setUp(self):
        specifics.set("is_backup_writer", 1)

    def check_time(self, rp):
        """Make sure that rp is an inc file, and time is prevtime"""
        self.assertTrue(rp.isincfile())
        t = rp.getinctime()
        self.assertEqual(t, prevtime)

    def testreg(self):
        """Test increment of regular files"""
        increment.init(False, actions.DEFAULT_NOT_COMPRESSED_REGEXP)
        target.setdata()
        if target.lstat():
            target.delete()
        rpd = rpath.RPath(lc, t_diff)
        if rpd.lstat():
            rpd.delete()

        diffrp = increment.make_increment(rf, exec1, target, prevtime)
        self.assertTrue(diffrp.isreg())
        self.assertTrue(diffrp._equal_verbose(exec1, check_index=0, compare_size=0))
        self.check_time(diffrp)
        self.assertEqual(diffrp.getinctype(), b"diff")
        diffrp.delete()

    def testmissing(self):
        """Test creation of missing files"""
        missing_rp = increment.make_increment(rf, nothing, target, prevtime)
        self.check_time(missing_rp)
        self.assertEqual(missing_rp.getinctype(), b"missing")
        missing_rp.delete()

    @unittest.skipIf(os.name == "nt", "Symlinks not supported under Windows")
    def testsnapshot(self):
        """Test making of a snapshot"""
        increment.init(False, actions.DEFAULT_NOT_COMPRESSED_REGEXP)
        snap_rp = increment.make_increment(rf, sym, target, prevtime)
        self.check_time(snap_rp)
        self.assertTrue(rpath._cmp_file_attribs(snap_rp, sym))
        self.assertTrue(rpath.cmp(snap_rp, sym))
        snap_rp.delete()

        snap_rp2 = increment.make_increment(sym, rf, target, prevtime)
        self.check_time(snap_rp2)
        self.assertTrue(snap_rp2._equal_verbose(rf, check_index=0))
        self.assertTrue(rpath.cmp(snap_rp2, rf))
        snap_rp2.delete()

    @unittest.skipIf(os.name == "nt", "Symlinks not supported under Windows")
    def testGzipsnapshot(self):
        """Test making a compressed snapshot"""
        increment.init(True, actions.DEFAULT_NOT_COMPRESSED_REGEXP)
        rp = increment.make_increment(rf, sym, target, prevtime)
        self.check_time(rp)
        self.assertTrue(rp._equal_verbose(sym, check_index=0, compare_size=0))
        self.assertTrue(rpath.cmp(rp, sym))
        rp.delete()

        rp = increment.make_increment(sym, rf, target, prevtime)
        self.check_time(rp)
        self.assertTrue(rp._equal_verbose(rf, check_index=0, compare_size=0))
        with rp.open("rb", 1) as rp_fd, rf.open("rb") as rf_fd:
            self.assertTrue(rpath._cmp_file_obj(rp_fd, rf_fd))
        self.assertTrue(rp.isinccompressed())
        rp.delete()

    @unittest.skipIf(os.name == "nt", "Symlinks not supported under Windows")
    def testdir(self):
        """Test increment on base_dir"""
        rp = increment.make_increment(sym, base_dir, target, prevtime)
        self.check_time(rp)
        self.assertTrue(rp.lstat())
        self.assertTrue(target.isdir())
        self.assertTrue(
            base_dir._equal_verbose(rp, check_index=0, compare_size=0, compare_type=0)
        )
        self.assertTrue(rp.isreg())
        rp.delete()
        target.delete()

    def testDiff(self):
        """Test making diffs"""
        increment.init(False, actions.DEFAULT_NOT_COMPRESSED_REGEXP)
        rp = increment.make_increment(rf, rf2, target, prevtime)
        self.check_time(rp)
        self.assertTrue(rp._equal_verbose(rf2, check_index=0, compare_size=0))
        Rdiff.patch_local(rf, rp, out2)
        self.assertTrue(rpath.cmp(rf2, out2))
        rp.delete()
        out2.delete()

    def testGzipDiff(self):
        """Test making gzipped diffs"""
        increment.init(True, actions.DEFAULT_NOT_COMPRESSED_REGEXP)
        rp = increment.make_increment(rf, rf2, target, prevtime)
        self.check_time(rp)
        self.assertTrue(rp._equal_verbose(rf2, check_index=0, compare_size=0))
        Rdiff.patch_local(rf, rp, out2, delta_compressed=1)
        self.assertTrue(rpath.cmp(rf2, out2))
        rp.delete()
        out2.delete()

    def testGzipRegexp(self):
        """Here a .gz file shouldn't be compressed"""
        increment.init(True, actions.DEFAULT_NOT_COMPRESSED_REGEXP)
        rpath.copy(rf, out_gz)
        self.assertTrue(out_gz.lstat())

        rp = increment.make_increment(rf, out_gz, target, prevtime)
        self.check_time(rp)
        self.assertTrue(rp._equal_verbose(out_gz, check_index=0, compare_size=0))
        Rdiff.patch_local(rf, rp, out2)
        self.assertTrue(rpath.cmp(out_gz, out2))
        rp.delete()
        out2.delete()
        out_gz.delete()

    def test_parse_increment_name(self):
        """Test parsing multiple name combinations"""
        increment_names = {
            b"a.b.gz": None,  # too short
            b"a.b": None,
            b"a.b.c.gz": None,  # wrong extension
            b"a.b.c": None,
            b"a.b.missing.gz": None,  # wrong time string
            b"a.b.data": None,
            b"a.1970-01-01T03:46:40+01:00.missing.gz": (  # happy path
                True,
                b"1970-01-01T03:46:40+01:00",
                10_000,
                b"missing",
                b"a",
            ),
            b"a.1970-01-01T03:46:40-01:00.data": (
                False,
                b"1970-01-01T03:46:40-01:00",
                17_200,
                b"data",
                b"a",
            ),
            b"a.b.c.1970-01-01T03:46:40+00:00.dir.gz": (  # with superfluous dots
                True,
                b"1970-01-01T03:46:40+00:00",
                13_600,
                b"dir",
                b"a.b.c",
            ),
            b"a.b.c.1970-01-01T03:46:40-05:30.snapshot": (
                False,
                b"1970-01-01T03:46:40-05:30",
                29_800,
                b"snapshot",
                b"a.b.c",
            ),
        }
        for inc_name, output in increment_names.items():
            self.assertEqual(increment._parse_increment_name(inc_name), output)


if __name__ == "__main__":
    unittest.main()
