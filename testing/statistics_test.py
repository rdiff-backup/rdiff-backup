"""
Test the statistics function of rdiff-backup
"""

import os
import io
import time
import unittest

import commontest as comtst

from rdiff_backup import statistics, rpath
from rdiffbackup.singletons import generics, specifics

TEST_BASE_DIR = comtst.get_test_base_dir(__file__)


class SessionStatsCalcTest(unittest.TestCase):
    """Test SessionStatsCalc class"""

    out_dir = os.path.join(TEST_BASE_DIR, b"output")

    def set_obj(self, s):
        """Set values of s's statistics"""
        s.SourceFiles = 1
        s.SourceFileSize = 2
        s.MirrorFiles = 13
        s.MirrorFileSize = 14
        s.NewFiles = 3
        s.NewFileSize = 4
        s.DeletedFiles = 5
        s.DeletedFileSize = 6
        s.ChangedFiles = 7
        s.ChangedSourceSize = 8
        s.ChangedMirrorSize = 9
        s.IncrementFiles = 15
        s.IncrementFileSize = 10
        s.StartTime = 11
        s.EndTime = 12

    def test_get_stats(self):
        """Test reading and writing stat objects"""
        s = statistics.SessionStatsCalc()
        self.assertIsNone(s.SourceFiles)
        self.set_obj(s)
        self.assertEqual(s.SourceFiles, 1)

        s1 = statistics.SessionStatsTracker()
        self.assertEqual(s1.SourceFiles, 0)

    def test_get_stats_string(self):
        """Test conversion of stat object into string"""
        s = statistics.SessionStatsCalc()
        stats_string = s._get_stats_string()
        self.assertEqual(stats_string, "")

        self.set_obj(s)
        stats_string = s._get_stats_string()
        ss_list = stats_string.split("\n")
        tail = "\n".join(ss_list[2:])  # Time varies by time zone, don't check
        # """StartTime 11.00 (Wed Dec 31 16:00:11 1969)
        # EndTime 12.00 (Wed Dec 31 16:00:12 1969)"
        self.assertEqual(
            tail,
            """ElapsedTime 1.00 (1 second)
SourceFiles 1
SourceFileSize 2 (2 B)
MirrorFiles 13
MirrorFileSize 14 (14 B)
NewFiles 3
NewFileSize 4 (4 B)
DeletedFiles 5
DeletedFileSize 6 (6 B)
ChangedFiles 7
ChangedSourceSize 8 (8 B)
ChangedMirrorSize 9 (9 B)
IncrementFiles 15
IncrementFileSize 10 (10 B)
TotalDestinationSizeChange 7 (7 B)
""",
        )

    def test_line_string(self):
        """Test conversion to a single line"""
        s = statistics.SessionStatsCalc()
        self.set_obj(s)
        statline = s._get_stats_line(("sample", "index", "w", "new\nline"))
        self.assertEqual(
            statline, "sample/index/w/new\\nline 1 2 13 14 3 4 5 6 7 8 9 15 10"
        )

        statline = s._get_stats_line(())
        self.assertEqual(statline, ". 1 2 13 14 3 4 5 6 7 8 9 15 10")

        statline = s._get_stats_line(("file name with spaces",))
        self.assertEqual(
            statline, "file\\x20name\\x20with\\x20spaces 1 2 13 14 3 4 5 6 7 8 9 15 10"
        )

    def test_init_stats(self):
        """Test setting stat object from string"""
        s = statistics.SessionStatsCalc()
        s._set_stats_from_string("NewFiles 3 hello there")
        for attr in s._stat_attrs:
            if attr == "NewFiles":
                self.assertEqual(s.__getattribute__(attr), 3)
            else:
                self.assertIsNone(s.__getattribute__(attr))

        s1 = statistics.SessionStatsCalc()
        self.set_obj(s1)
        self.assertFalse(s1._stats_equal(s))

        s2 = statistics.SessionStatsCalc()
        s2._set_stats_from_string(s1._get_stats_string())
        self.assertTrue(s1._stats_equal(s2))

    def test_write_rp(self):
        """Test reading and writing of statistics object"""
        rp = rpath.RPath(
            specifics.local_connection, os.path.join(TEST_BASE_DIR, b"statstest")
        )
        if rp.lstat():
            rp.delete()
        s = statistics.SessionStatsCalc()
        self.set_obj(s)
        s.write_stats(rp.open("w"))

        s2 = statistics.SessionStatsCalc()
        self.assertFalse(s2._stats_equal(s))
        s2.read_stats(rp.open("r"))
        self.assertTrue(s2._stats_equal(s))

    def test_read_stats(self):
        """Test handling of badly formatted statistics"""
        stats_fd = io.StringIO("OnePart")
        with self.assertRaises(statistics.StatsException):
            stats = statistics.SessionStatsCalc()
            stats.read_stats(stats_fd)
        stats_fd = io.StringIO("OnePart SomeValue")
        with self.assertRaises(statistics.StatsException):
            stats = statistics.SessionStatsCalc()
            stats.read_stats(stats_fd)
        stats_fd = io.StringIO("Errors SomeValue")
        with self.assertRaises(statistics.StatsException):
            stats = statistics.SessionStatsCalc()
            stats.read_stats(stats_fd)
        stats_fd = io.StringIO("Errors 123")
        stats = statistics.SessionStatsCalc()
        stats.read_stats(stats_fd)
        self.assertEqual(stats.Errors, 123)
        stats_fd = io.StringIO("Errors 12.3")
        stats = statistics.SessionStatsCalc()
        stats.read_stats(stats_fd)
        self.assertEqual(stats.Errors, 12.3)

    def test_average(self):
        """Test making an average statsobj"""
        s1 = statistics.SessionStatsCalc()
        s1.StartTime = 5
        s1.EndTime = 10
        s1.ElapsedTime = 5
        s1.ChangedFiles = 2
        s1.SourceFiles = 100
        s1.NewFileSize = 4

        s2 = statistics.SessionStatsCalc()
        s2.StartTime = 25
        s2.EndTime = 35
        s2.ElapsedTime = 10
        s2.ChangedFiles = 1
        s2.SourceFiles = 50
        s2.DeletedFiles = 0

        s3 = statistics.SessionStatsCalc().calc_average([s1, s2])
        self.assertIsNone(s3.StartTime)
        self.assertIsNone(s3.EndTime)
        self.assertEqual(s3.ElapsedTime, 7.5)
        self.assertIsNone(s3.DeletedFiles)
        self.assertIsNone(s3.NewFileSize)
        self.assertEqual(s3.ChangedFiles, 1.5)
        self.assertEqual(s3.SourceFiles, 75)

    def test_session_stats_time(self):
        """Make sure start and end time are correctly set"""
        # Else old time could be used as start time
        generics.set("current_time", None)
        generics.set("current_time_string", None)

        start_time_1 = time.time()
        stats = statistics.SessionStatsTracker()
        start_time_2 = time.time()
        self.assertLessEqual(start_time_1, stats.StartTime)
        self.assertGreaterEqual(start_time_2, stats.StartTime)
        end_time_1 = time.time()
        stats.finish()
        end_time_2 = time.time()
        self.assertLessEqual(end_time_1, stats.EndTime)
        self.assertGreaterEqual(end_time_2, stats.EndTime)

        stats = statistics.SessionStatsTracker(10_000)
        stats.finish(20_000)
        self.assertEqual(stats.StartTime, 10_000)
        self.assertEqual(stats.EndTime, 20_000)


class IncStatTest(unittest.TestCase):
    """Test statistics as produced by actual backup"""

    out_dir = os.path.join(TEST_BASE_DIR, b"output")

    def stats_check_initial(self, s):
        """Make sure stats object s compatible with initial mirroring

        A lot of the off by one stuff is because the root directory
        exists in the below examples.

        """
        self.assertIn(s.MirrorFiles, (0, 1))
        self.assertLess(s.MirrorFileSize, 20000)
        self.assertLessEqual(s.NewFiles, s.SourceFiles)
        self.assertLessEqual(s.SourceFiles, s.NewFiles + 1)
        self.assertLessEqual(s.NewFileSize, s.SourceFileSize)
        self.assertLessEqual(s.SourceFileSize, s.NewFileSize + 20000)
        self.assertIn(s.ChangedFiles, (0, 1))
        self.assertLess(s.ChangedSourceSize, 20000)
        self.assertLess(s.ChangedMirrorSize, 20000)
        self.assertEqual(s.DeletedFiles, 0)
        self.assertEqual(s.DeletedFileSize, 0)
        self.assertEqual(s.IncrementFileSize, 0)

    def test_statistics(self):
        """
        Test the writing of statistics

        The file sizes are approximate because the size of directories
        could change with different file systems...
        """

        def sorti(inclist):
            templist = [(inc.getinctime(), inc) for inc in inclist]
            templist.sort()
            return [inc for (t, inc) in templist]

        generics.compression = True
        comtst.remove_dir(self.out_dir)
        comtst.InternalBackup(
            1, 1, os.path.join(comtst.old_test_dir, b"stattest1"), self.out_dir
        )
        comtst.InternalBackup(
            1,
            1,
            os.path.join(comtst.old_test_dir, b"stattest2"),
            self.out_dir,
            int(time.time()) + 1,
        )

        rbdir = rpath.RPath(
            specifics.local_connection, os.path.join(self.out_dir, b"rdiff-backup-data")
        )

        incs = sorti(rbdir.append("session_statistics").get_incfiles_list())
        self.assertEqual(len(incs), 2)
        s2 = statistics.SessionStatsCalc().read_stats(incs[0].open("r"))
        self.assertEqual(s2.SourceFiles, 7)
        self.assertLessEqual(700000, s2.SourceFileSize)
        self.assertLess(s2.SourceFileSize, 750000)
        self.stats_check_initial(s2)

        root_stats = statistics.SessionStatsCalc().read_stats(incs[1].open("r"))
        self.assertEqual(root_stats.SourceFiles, 7)
        self.assertLessEqual(550000, root_stats.SourceFileSize)
        self.assertLess(root_stats.SourceFileSize, 570000)
        self.assertEqual(root_stats.MirrorFiles, 7)
        self.assertLessEqual(700000, root_stats.MirrorFileSize)
        self.assertLess(root_stats.MirrorFileSize, 750000)
        self.assertEqual(root_stats.NewFiles, 1)
        self.assertEqual(root_stats.NewFileSize, 0)
        self.assertEqual(root_stats.DeletedFiles, 1)
        self.assertEqual(root_stats.DeletedFileSize, 200000)
        self.assertLessEqual(3, root_stats.ChangedFiles)
        self.assertLessEqual(root_stats.ChangedFiles, 4)
        self.assertLessEqual(450000, root_stats.ChangedSourceSize)
        self.assertLess(root_stats.ChangedSourceSize, 470000)
        self.assertLessEqual(400000, root_stats.ChangedMirrorSize)
        self.assertLess(root_stats.ChangedMirrorSize, 420000)
        self.assertLess(10, root_stats.IncrementFileSize)
        self.assertLess(root_stats.IncrementFileSize, 30000)


class FileStatsTrackerTest(unittest.TestCase):
    """Test FileStatsTracker class"""

    def test_filestats_tracker_write(self):
        """Test the tracking of file statistics"""
        tracker = statistics.FileStatsTracker()
        writer = io.BytesIO()
        tracker.open_stats_file(writer, b"|")
        compare_str = b"|".join(tracker._HEADER) + b"|"
        tracker.flush()  # we need to flush before we can compare
        self.assertEqual(writer.getvalue(), compare_str)
        src = rpath.RORPath(["s", "r", "c"], {"size": 1234, "type": "reg"})
        dst = rpath.RORPath(["d", "s", "t"], {"size": 2468, "type": "reg"})
        inc1 = rpath.RORPath(["i", "n", "c"], {"size": 999, "type": "reg"})
        inc2 = rpath.RORPath(["i", "n", "c"], {"size": 999, "type": "sym"})
        tracker.add_stats(src, dst, True, inc1)
        compare_str += b"s/r/c True 1234 2468 999|"
        tracker.add_stats(None, dst, False, inc2)
        compare_str += b"d/s/t False NA 2468 0|"
        tracker.flush()  # we need to flush before we can compare
        self.assertEqual(writer.getvalue(), compare_str)
        tracker.close()


if __name__ == "__main__":
    unittest.main()
