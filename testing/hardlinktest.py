import os
import unittest
import time
from commontest import abs_test_dir, abs_output_dir, old_test_dir, re_init_rpath_dir, \
    CompareRecursive, BackupRestoreSeries, InternalBackup, InternalRestore, \
    MakeOutputDir, reset_hardlink_dicts
from rdiff_backup import Globals, Hardlink, selection, rpath


class HardlinkTest(unittest.TestCase):
    """Test cases for Hard links"""
    outputrp = rpath.RPath(Globals.local_connection, abs_output_dir)
    re_init_rpath_dir(outputrp)

    hlinks_dir = os.path.join(old_test_dir, b"hardlinks")
    hlinks_dir1 = os.path.join(hlinks_dir, b"dir1")
    hlinks_dir1copy = os.path.join(hlinks_dir, b"dir1copy")
    hlinks_dir2 = os.path.join(hlinks_dir, b"dir2")
    hlinks_dir3 = os.path.join(hlinks_dir, b"dir3")
    hlinks_rp1 = rpath.RPath(Globals.local_connection, hlinks_dir1)
    hlinks_rp1copy = rpath.RPath(Globals.local_connection, hlinks_dir1copy)
    hlinks_rp2 = rpath.RPath(Globals.local_connection, hlinks_dir2)
    hlinks_rp3 = rpath.RPath(Globals.local_connection, hlinks_dir3)

    def testEquality(self):
        """Test rorp_eq function in conjunction with CompareRecursive"""
        assert CompareRecursive(self.hlinks_rp1, self.hlinks_rp1copy)
        assert CompareRecursive(self.hlinks_rp1,
                                self.hlinks_rp2,
                                compare_hardlinks=None)
        assert not CompareRecursive(
            self.hlinks_rp1, self.hlinks_rp2, compare_hardlinks=1)

    def testBuildingDict(self):
        """See if the partial inode dictionary is correct"""
        Globals.preserve_hardlinks = 1
        reset_hardlink_dicts()
        for dsrp in selection.Select(self.hlinks_rp3).set_iter():
            Hardlink.add_rorp(dsrp)

        assert len(list(Hardlink._inode_index.keys())) == 3, \
            Hardlink._inode_index

    def testCompletedDict(self):
        """See if the hardlink dictionaries are built correctly"""
        reset_hardlink_dicts()
        for dsrp in selection.Select(self.hlinks_rp1).set_iter():
            Hardlink.add_rorp(dsrp)
            Hardlink.del_rorp(dsrp)
        assert Hardlink._inode_index == {}, Hardlink._inode_index

        reset_hardlink_dicts()
        for dsrp in selection.Select(self.hlinks_rp2).set_iter():
            Hardlink.add_rorp(dsrp)
            Hardlink.del_rorp(dsrp)
        assert Hardlink._inode_index == {}, Hardlink._inode_index

    def testSeries(self):
        """Test hardlink system by backing up and restoring a few dirs"""
        dirlist = [
            self.hlinks_dir1, self.hlinks_dir2, self.hlinks_dir3,
            os.path.join(old_test_dir, b'various_file_types')
        ]
        BackupRestoreSeries(None, None, dirlist, compare_hardlinks=1)
        BackupRestoreSeries(1, 1, dirlist, compare_hardlinks=1)

    def testInnerRestore(self):
        """Restore part of a dir, see if hard links preserved"""
        MakeOutputDir()
        output = rpath.RPath(Globals.local_connection, abs_output_dir)
        hlout1_dir = os.path.join(abs_test_dir, b"out_hardlink1")
        hlout2_dir = os.path.join(abs_test_dir, b"out_hardlink2")

        # Now set up directories out_hardlink1 and out_hardlink2
        hlout1 = rpath.RPath(Globals.local_connection, hlout1_dir)
        if hlout1.lstat():
            hlout1.delete()
        hlout1.mkdir()
        hlout1_sub = hlout1.append("subdir")
        hlout1_sub.mkdir()
        hl1_1 = hlout1_sub.append("hardlink1")
        hl1_2 = hlout1_sub.append("hardlink2")
        hl1_3 = hlout1_sub.append("hardlink3")
        hl1_4 = hlout1_sub.append("hardlink4")
        # 1 and 2 are hard linked, as are 3 and 4
        hl1_1.touch()
        hl1_2.hardlink(hl1_1.path)
        hl1_3.touch()
        hl1_4.hardlink(hl1_3.path)

        hlout2 = rpath.RPath(Globals.local_connection, hlout2_dir)
        if hlout2.lstat():
            hlout2.delete()
        assert not os.system(b"cp -a %s %s" % (hlout1_dir, hlout2_dir))
        hlout2_sub = hlout2.append("subdir")
        hl2_1 = hlout2_sub.append("hardlink1")
        hl2_2 = hlout2_sub.append("hardlink2")
        hl2_3 = hlout2_sub.append("hardlink3")
        hl2_4 = hlout2_sub.append("hardlink4")
        # Now 2 and 3 are hard linked, also 1 and 4
        rpath.copy_with_attribs(hl1_1, hl2_1)
        rpath.copy_with_attribs(hl1_2, hl2_2)
        hl2_3.delete()
        hl2_3.hardlink(hl2_2.path)
        hl2_4.delete()
        hl2_4.hardlink(hl2_1.path)
        rpath.copy_attribs(hlout1_sub, hlout2_sub)

        # Now try backing up twice, making sure hard links are preserved
        InternalBackup(1, 1, hlout1.path, output.path)
        out_subdir = output.append("subdir")
        assert out_subdir.append("hardlink1").getinode() == \
            out_subdir.append("hardlink2").getinode()
        assert out_subdir.append("hardlink3").getinode() == \
            out_subdir.append("hardlink4").getinode()
        assert out_subdir.append("hardlink1").getinode() != \
            out_subdir.append("hardlink3").getinode()

        time.sleep(1)
        InternalBackup(1, 1, hlout2.path, output.path)
        out_subdir.setdata()
        assert out_subdir.append("hardlink1").getinode() == \
            out_subdir.append("hardlink4").getinode()
        assert out_subdir.append("hardlink2").getinode() == \
            out_subdir.append("hardlink3").getinode()
        assert out_subdir.append("hardlink1").getinode() != \
            out_subdir.append("hardlink2").getinode()

        # Now try restoring, still checking hard links.
        sub_dir = os.path.join(abs_output_dir, b"subdir")
        out2_dir = os.path.join(abs_test_dir, b"out2")
        out2 = rpath.RPath(Globals.local_connection, out2_dir)
        hlout1 = out2.append("hardlink1")
        hlout2 = out2.append("hardlink2")
        hlout3 = out2.append("hardlink3")
        hlout4 = out2.append("hardlink4")

        if out2.lstat():
            out2.delete()
        InternalRestore(1, 1, sub_dir, out2_dir, 1)
        out2.setdata()
        for rp in [hlout1, hlout2, hlout3, hlout4]:
            rp.setdata()
        assert hlout1.getinode() == hlout2.getinode()
        assert hlout3.getinode() == hlout4.getinode()
        assert hlout1.getinode() != hlout3.getinode()

        if out2.lstat():
            out2.delete()
        InternalRestore(1, 1, sub_dir, out2_dir, int(time.time()))
        out2.setdata()
        for rp in [hlout1, hlout2, hlout3, hlout4]:
            rp.setdata()
        assert hlout1.getinode() == hlout4.getinode(), \
            "%a %a" % (hlout1.path, hlout4.path)
        assert hlout2.getinode() == hlout3.getinode()
        assert hlout1.getinode() != hlout2.getinode()


if __name__ == "__main__":
    unittest.main()
