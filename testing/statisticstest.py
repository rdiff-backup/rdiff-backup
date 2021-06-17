import unittest
import time
import os
from commontest import abs_test_dir, Myrm, InternalBackup, old_test_dir, abs_output_dir
from rdiff_backup import Globals, statistics, rpath


class StatsObjTest(unittest.TestCase):
    """Test StatsObj class"""

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
        s = statistics.StatsObj()
        self.assertIsNone(s.get_stat('SourceFiles'))
        self.set_obj(s)
        self.assertEqual(s.get_stat('SourceFiles'), 1)

        s1 = statistics.StatFileObj()
        self.assertEqual(s1.get_stat('SourceFiles'), 0)

    def test_get_stats_string(self):
        """Test conversion of stat object into string"""
        s = statistics.StatsObj()
        stats_string = s._get_stats_string()
        self.assertEqual(stats_string, "")

        self.set_obj(s)
        stats_string = s._get_stats_string()
        ss_list = stats_string.split("\n")
        tail = "\n".join(ss_list[2:])  # Time varies by time zone, don't check
        # """StartTime 11.00 (Wed Dec 31 16:00:11 1969)
        # EndTime 12.00 (Wed Dec 31 16:00:12 1969)"
        self.assertEqual(tail, """ElapsedTime 1.00 (1 second)
SourceFiles 1
SourceFileSize 2 (2 bytes)
MirrorFiles 13
MirrorFileSize 14 (14 bytes)
NewFiles 3
NewFileSize 4 (4 bytes)
DeletedFiles 5
DeletedFileSize 6 (6 bytes)
ChangedFiles 7
ChangedSourceSize 8 (8 bytes)
ChangedMirrorSize 9 (9 bytes)
IncrementFiles 15
IncrementFileSize 10 (10 bytes)
TotalDestinationSizeChange 7 (7 bytes)
""")

    def test_line_string(self):
        """Test conversion to a single line"""
        s = statistics.StatsObj()
        self.set_obj(s)
        statline = s._get_stats_line(("sample", "index", "w", "new\nline"))
        self.assertEqual(
            statline,
            "sample/index/w/new\\nline 1 2 13 14 3 4 5 6 7 8 9 15 10")

        statline = s._get_stats_line(())
        self.assertEqual(statline, ". 1 2 13 14 3 4 5 6 7 8 9 15 10")

        statline = s._get_stats_line(("file name with spaces", ))
        self.assertEqual(
            statline,
            "file\\x20name\\x20with\\x20spaces 1 2 13 14 3 4 5 6 7 8 9 15 10")

    def test_byte_summary(self):
        """Test conversion of bytes to strings like 7.23MB"""
        s = statistics.StatsObj()
        f = s.get_byte_summary_string
        self.assertEqual(f(1), "1 byte")
        self.assertEqual(f(234.34), "234 bytes")
        self.assertEqual(f(2048), "2.00 KB")
        self.assertEqual(f(3502243), "3.34 MB")
        self.assertEqual(f(314992230), "300 MB")
        self.assertEqual(f(36874871216), "34.3 GB")
        self.assertEqual(f(3775986812573450), "3434 TB")

    def test_init_stats(self):
        """Test setting stat object from string"""
        s = statistics.StatsObj()
        s._set_stats_from_string("NewFiles 3 hello there")
        for attr in s._stat_attrs:
            if attr == 'NewFiles':
                self.assertEqual(s.get_stat(attr), 3)
            else:
                self.assertIsNone(s.get_stat(attr))

        s1 = statistics.StatsObj()
        self.set_obj(s1)
        self.assertFalse(s1._stats_equal(s))

        s2 = statistics.StatsObj()
        s2._set_stats_from_string(s1._get_stats_string())
        self.assertTrue(s1._stats_equal(s2))

    def test_write_rp(self):
        """Test reading and writing of statistics object"""
        rp = rpath.RPath(Globals.local_connection,
                         os.path.join(abs_test_dir, b"statstest"))
        if rp.lstat():
            rp.delete()
        s = statistics.StatsObj()
        self.set_obj(s)
        s.write_stats_to_rp(rp)

        s2 = statistics.StatsObj()
        self.assertFalse(s2._stats_equal(s))
        s2.read_stats_from_rp(rp)
        self.assertTrue(s2._stats_equal(s))

    def testAverage(self):
        """Test making an average statsobj"""
        s1 = statistics.StatsObj()
        s1.StartTime = 5
        s1.EndTime = 10
        s1.ElapsedTime = 5
        s1.ChangedFiles = 2
        s1.SourceFiles = 100
        s1.NewFileSize = 4

        s2 = statistics.StatsObj()
        s2.StartTime = 25
        s2.EndTime = 35
        s2.ElapsedTime = 10
        s2.ChangedFiles = 1
        s2.SourceFiles = 50
        s2.DeletedFiles = 0

        s3 = statistics.StatsObj().set_to_average([s1, s2])
        self.assertIsNone(s3.StartTime)
        self.assertIsNone(s3.EndTime)
        self.assertEqual(s3.ElapsedTime, 7.5)
        self.assertIsNone(s3.DeletedFiles)
        self.assertIsNone(s3.NewFileSize)
        self.assertEqual(s3.ChangedFiles, 1.5)
        self.assertEqual(s3.SourceFiles, 75)


class IncStatTest(unittest.TestCase):
    """Test statistics as produced by actual backup"""

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

    def testStatistics(self):
        """
        Test the writing of statistics

        The file sizes are approximate because the size of directories
        could change with different file systems...
        """

        def sorti(inclist):
            templist = [(inc.getinctime(), inc) for inc in inclist]
            templist.sort()
            return [inc for (t, inc) in templist]

        Globals.compression = 1
        Myrm(abs_output_dir)
        InternalBackup(1, 1, os.path.join(old_test_dir, b"stattest1"),
                       abs_output_dir)
        InternalBackup(1, 1, os.path.join(old_test_dir, b"stattest2"),
                       abs_output_dir,
                       int(time.time()) + 1)

        rbdir = rpath.RPath(Globals.local_connection,
                            os.path.join(abs_output_dir, b"rdiff-backup-data"))

        incs = sorti(rbdir.append("session_statistics").get_incfiles_list())
        self.assertEqual(len(incs), 2)
        s2 = statistics.StatsObj().read_stats_from_rp(incs[0])
        self.assertEqual(s2.SourceFiles, 7)
        self.assertLessEqual(700000, s2.SourceFileSize)
        self.assertLess(s2.SourceFileSize, 750000)
        self.stats_check_initial(s2)

        root_stats = statistics.StatsObj().read_stats_from_rp(incs[1])
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


if __name__ == "__main__":
    unittest.main()
