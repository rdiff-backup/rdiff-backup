import unittest
from commontest import BackupRestoreSeries
from rdiff_backup import rpath, metadata, Globals
"""***NOTE***

None of these tests should work unless your system supports resource
forks.  So basically these tests should only be run on Mac OS X.

"""

Globals.read_resource_forks = Globals.write_resource_forks = 1


class ResourceForkTest(unittest.TestCase):
    """Test dealing with Mac OS X style resource forks"""
    tempdir = rpath.RPath(Globals.local_connection, 'testfiles/output')
    rf_testdir1 = rpath.RPath(Globals.local_connection,
                              'testfiles/resource_fork_test1')
    rf_testdir2 = rpath.RPath(Globals.local_connection,
                              'testfiles/resource_fork_test2')

    def make_temp(self):
        """Make temp directory testfiles/resource_fork_test"""
        if self.tempdir.lstat():
            self.tempdir.delete()
        self.tempdir.mkdir()

    def testBasic(self):
        """Test basic reading and writing of resource forks"""
        self.make_temp()
        rp = self.tempdir.append('test')
        rp.touch()
        self.assertEqual(rp.get_resource_fork(), '')

        s = 'new resource fork data'
        rp.write_resource_fork(s)
        self.assertEqual(rp.get_resource_fork(), s)

        rp2 = self.tempdir.append('test')
        self.assertTrue(rp2.isreg())
        self.assertEqual(rp2.get_resource_fork(), s)

    def testRecord(self):
        """Test reading, writing, and comparing of records with rforks"""
        self.make_temp()
        rp = self.tempdir.append('test')
        rp.touch()
        rp.set_resource_fork('hello')

        record = metadata.RORP2Record(rp)
        rorp_out = metadata.Record2RORP(record)
        self.assertEqual(rorp_out, rp)
        self.assertEqual(rorp_out.get_resource_fork(), 'hello')

    def make_backup_dirs(self):
        """Create testfiles/resource_fork_test[12] dirs for testing"""
        if self.rf_testdir1.lstat():
            self.rf_testdir1.delete()
        if self.rf_testdir2.lstat():
            self.rf_testdir2.delete()
        self.rf_testdir1.mkdir()
        rp1_1 = self.rf_testdir1.append('1')
        rp1_2 = self.rf_testdir1.append('2')
        rp1_3 = self.rf_testdir1.append('3')
        rp1_1.touch()
        rp1_2.touch()
        rp1_3.symlink('foo')
        rp1_1.write_resource_fork('This should appear in resource fork')
        rp1_1.chmod(0o400)  # test for bug changing resource forks after perms
        rp1_2.write_resource_fork('Data for the resource fork 2')

        self.rf_testdir2.mkdir()
        rp2_1 = self.rf_testdir2.append('1')
        rp2_2 = self.rf_testdir2.append('2')
        rp2_3 = self.rf_testdir2.append('3')
        rp2_1.touch()
        rp2_2.touch()
        rp2_3.touch()
        rp2_1.write_resource_fork('New data for resource fork 1')
        rp2_1.chmod(0o400)
        rp2_3.write_resource_fork('New fork')

    def testSeriesLocal(self):
        """Test backing up and restoring directories with ACLs locally"""
        Globals.read_resource_forks = Globals.write_resource_forks = 1
        self.make_backup_dirs()
        dirlist = [
            'testfiles/resource_fork_test1', 'testfiles/empty',
            'testfiles/resource_fork_test2', 'testfiles/resource_fork_test1'
        ]
        # BackupRestoreSeries(1, 1, dirlist, compare_resource_forks = 1)
        BackupRestoreSeries(1, 1, dirlist)

    def testSeriesRemote(self):
        """Test backing up and restoring directories with ACLs locally"""
        Globals.read_resource_forks = Globals.write_resource_forks = 1
        self.make_backup_dirs()
        dirlist = [
            'testfiles/resource_fork_test1', 'testfiles/resource_fork_test2',
            'testfiles/empty', 'testfiles/resource_fork_test1'
        ]
        # BackupRestoreSeries(1, 1, dirlist, compare_resource_forks = 1)
        BackupRestoreSeries(1, 1, dirlist)


if __name__ == "__main__":
    unittest.main()
