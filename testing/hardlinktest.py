import os
import unittest
import time
from commontest import (
    abs_test_dir, abs_output_dir, old_test_dir, re_init_rpath_dir,
    compare_recursive, BackupRestoreSeries, InternalBackup, InternalRestore,
    MakeOutputDir, reset_hardlink_dicts, xcopytree
)
from rdiff_backup import Globals, Hardlink, rpath, selection
from rdiffbackup.meta import stdattr


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
    hello_str = "Hello, world!"
    hello_str_hash = "943a702d06f34599aee1f8da8ef9f7296031d699"

    def testEquality(self):
        """Test rorp_eq function in conjunction with compare_recursive"""
        self.assertTrue(compare_recursive(self.hlinks_rp1, self.hlinks_rp1copy))
        self.assertTrue(compare_recursive(self.hlinks_rp1,
                                          self.hlinks_rp2,
                                          compare_hardlinks=None))
        self.assertFalse(compare_recursive(
            self.hlinks_rp1, self.hlinks_rp2, compare_hardlinks=1))

    def testBuildingDict(self):
        """See if the partial inode dictionary is correct"""
        Globals.preserve_hardlinks = 1
        reset_hardlink_dicts()
        for dsrp in selection.Select(self.hlinks_rp3).get_select_iter():
            Hardlink.add_rorp(dsrp)

        self.assertEqual(len(list(Hardlink._inode_index.keys())), 3)

    def testCompletedDict(self):
        """See if the hardlink dictionaries are built correctly"""
        reset_hardlink_dicts()
        for dsrp in selection.Select(self.hlinks_rp1).get_select_iter():
            Hardlink.add_rorp(dsrp)
            Hardlink.del_rorp(dsrp)
        self.assertEqual(Hardlink._inode_index, {})

        reset_hardlink_dicts()
        for dsrp in selection.Select(self.hlinks_rp2).get_select_iter():
            Hardlink.add_rorp(dsrp)
            Hardlink.del_rorp(dsrp)
        self.assertEqual(Hardlink._inode_index, {})

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
        xcopytree(hlout1_dir, hlout2_dir)
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
        self.assertEqual(out_subdir.append("hardlink1").getinode(),
                         out_subdir.append("hardlink2").getinode())
        self.assertEqual(out_subdir.append("hardlink3").getinode(),
                         out_subdir.append("hardlink4").getinode())
        self.assertNotEqual(out_subdir.append("hardlink1").getinode(),
                            out_subdir.append("hardlink3").getinode())

        time.sleep(1)
        InternalBackup(1, 1, hlout2.path, output.path)
        out_subdir.setdata()
        self.assertEqual(out_subdir.append("hardlink1").getinode(),
                         out_subdir.append("hardlink4").getinode())
        self.assertEqual(out_subdir.append("hardlink2").getinode(),
                         out_subdir.append("hardlink3").getinode())
        self.assertNotEqual(out_subdir.append("hardlink1").getinode(),
                            out_subdir.append("hardlink2").getinode())

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
        self.assertEqual(hlout1.getinode(), hlout2.getinode())
        self.assertEqual(hlout3.getinode(), hlout4.getinode())
        self.assertNotEqual(hlout1.getinode(), hlout3.getinode())

        if out2.lstat():
            out2.delete()
        InternalRestore(1, 1, sub_dir, out2_dir, int(time.time()))
        out2.setdata()
        for rp in [hlout1, hlout2, hlout3, hlout4]:
            rp.setdata()
        self.assertEqual(hlout1.getinode(), hlout4.getinode())
        self.assertEqual(hlout2.getinode(), hlout3.getinode())
        self.assertNotEqual(hlout1.getinode(), hlout2.getinode())

    def extract_metadata(self, metadata_rp):
        """Return lists of hashes and hardlink counts in the metadata_rp"""
        hashes = []
        link_counts = []
        comp = metadata_rp.isinccompressed()
        extractor = stdattr.AttrExtractor(metadata_rp.open("r", comp))
        for rorp in extractor.iterate():
            link_counts.append(rorp.getnumlinks())
            if rorp.has_sha1():
                hashes.append(rorp.get_sha1())
            else:
                hashes.append(None)
        return (hashes, link_counts)

    def test_adding_hardlinks(self):
        """Test the addition of a new hardlinked file.

        This test is directed at some previously buggy code that 1) failed to
        keep the correct number of hardlinks in the mirror metadata, and 2)
        failed to restore hardlinked files so that they are linked the same as
        when they were backed up. One of the conditions that triggered these
        bugs included adding a new hardlinked file somewhere in the middle of a
        list of previously linked files.  The bug was originally reported here:
        https://savannah.nongnu.org/bugs/?26848
        """

        # Setup initial backup
        MakeOutputDir()
        output = rpath.RPath(Globals.local_connection, abs_output_dir)
        hlsrc_dir = os.path.join(abs_test_dir, b"src_hardlink")

        hlsrc = rpath.RPath(Globals.local_connection, hlsrc_dir)
        if hlsrc.lstat():
            hlsrc.delete()
        hlsrc.mkdir()
        hlsrc_sub = hlsrc.append("subdir")
        hlsrc_sub.mkdir()
        hl_file1 = hlsrc_sub.append("hardlink1")
        hl_file1.write_string(self.hello_str)
        hl_file3 = hlsrc_sub.append("hardlink3")
        hl_file3.hardlink(hl_file1.path)

        InternalBackup(1, 1, hlsrc.path, output.path, 10000)
        out_subdir = output.append("subdir")
        self.assertEqual(out_subdir.append("hardlink1").getinode(),
                         out_subdir.append("hardlink3").getinode())

        # validate that hashes and link counts are correctly saved in metadata
        meta_prefix = rpath.RPath(
            Globals.local_connection,
            os.path.join(abs_output_dir, b"rdiff-backup-data",
                         b"mirror_metadata"))
        incs = meta_prefix.get_incfiles_list()
        self.assertEqual(len(incs), 1)
        metadata_rp = incs[0]
        hashes, link_counts = self.extract_metadata(metadata_rp)
        # hashes for ., ./subdir, ./subdir/hardlink1, ./subdir/hardlink3
        expected_hashes = [None, None, self.hello_str_hash, None]
        self.assertEqual(expected_hashes, hashes)
        expected_link_counts = [1, 1, 2, 2]
        self.assertEqual(expected_link_counts, link_counts)

        # Create a new hardlinked file between "hardlink1" and "hardlink3" and perform another backup
        hl_file2 = hlsrc_sub.append("hardlink2")
        hl_file2.hardlink(hl_file1.path)

        InternalBackup(1, 1, hlsrc.path, output.path, 20000)
        self.assertEqual(out_subdir.append("hardlink1").getinode(),
                         out_subdir.append("hardlink2").getinode())
        self.assertEqual(out_subdir.append("hardlink1").getinode(),
                         out_subdir.append("hardlink3").getinode())

        # validate that hashes and link counts are correctly saved in metadata
        incs = meta_prefix.get_incfiles_list()
        self.assertEqual(len(incs), 2)
        if incs[0].getinctype() == b'snapshot':
            metadata_rp = incs[0]
        else:
            metadata_rp = incs[1]
        hashes, link_counts = self.extract_metadata(metadata_rp)
        # hashes for ., ./subdir/, ./subdir/hardlink1, ./subdir/hardlink2, ./subdir/hardlink3
        expected_hashes = [None, None, self.hello_str_hash, None, None]
        self.assertEqual(expected_hashes, hashes)
        expected_link_counts = [1, 1, 3, 3, 3]
        # The following assertion would fail as a result of bugs that are now fixed
        self.assertEqual(expected_link_counts, link_counts)

        # Now try restoring, still checking hard links.
        sub_path = os.path.join(abs_output_dir, b"subdir")
        restore_path = os.path.join(abs_test_dir, b"hl_restore")
        restore_dir = rpath.RPath(Globals.local_connection, restore_path)
        hlrestore_file1 = restore_dir.append("hardlink1")
        hlrestore_file2 = restore_dir.append("hardlink2")
        hlrestore_file3 = restore_dir.append("hardlink3")

        if restore_dir.lstat():
            restore_dir.delete()
        InternalRestore(1, 1, sub_path, restore_path, 10000)
        for rp in [hlrestore_file1, hlrestore_file3]:
            rp.setdata()
        self.assertEqual(hlrestore_file1.getinode(), hlrestore_file3.getinode())

        if restore_dir.lstat():
            restore_dir.delete()
        InternalRestore(1, 1, sub_path, restore_path, 20000)
        for rp in [hlrestore_file1, hlrestore_file2, hlrestore_file3]:
            rp.setdata()
        self.assertEqual(hlrestore_file1.getinode(), hlrestore_file2.getinode())
        # The following assertion would fail as a result of bugs that are now fixed
        self.assertEqual(hlrestore_file1.getinode(), hlrestore_file3.getinode())

    def test_moving_hardlinks(self):
        """Test moving the first hardlinked file in a series to later place in the series.

        This test is directed at some previously buggy code that failed to
        always keep a sha1 hash in the metadata for the first (and only the
        first) file among a series of linked files. The condition that
        triggered this bug involved removing the first file from a list of
        linked files, while also adding a new file at some later position in
        the list. The total number of hardlinked files in the list remains
        unchanged.  None of the files had a sha1 hash saved in its metadata.
        The bug was originally reported here:
        https://savannah.nongnu.org/bugs/?26848
        """

        # Setup initial backup
        MakeOutputDir()
        output = rpath.RPath(Globals.local_connection, abs_output_dir)
        hlsrc_dir = os.path.join(abs_test_dir, b"src_hardlink")

        hlsrc = rpath.RPath(Globals.local_connection, hlsrc_dir)
        if hlsrc.lstat():
            hlsrc.delete()
        hlsrc.mkdir()
        hlsrc_sub = hlsrc.append("subdir")
        hlsrc_sub.mkdir()
        hl_file1 = hlsrc_sub.append("hardlink1")
        hl_file1.write_string(self.hello_str)
        hl_file2 = hlsrc_sub.append("hardlink2")
        hl_file2.hardlink(hl_file1.path)

        InternalBackup(1, 1, hlsrc.path, output.path, 10000)
        out_subdir = output.append("subdir")
        self.assertEqual(out_subdir.append("hardlink1").getinode(),
                         out_subdir.append("hardlink2").getinode())

        # validate that hashes and link counts are correctly saved in metadata
        meta_prefix = rpath.RPath(
            Globals.local_connection,
            os.path.join(abs_output_dir, b"rdiff-backup-data",
                         b"mirror_metadata"))
        incs = meta_prefix.get_incfiles_list()
        self.assertEqual(len(incs), 1)
        metadata_rp = incs[0]
        hashes, link_counts = self.extract_metadata(metadata_rp)
        # hashes for ., ./subdir, ./subdir/hardlink1, ./subdir/hardlink3
        expected_hashes = [None, None, self.hello_str_hash, None]
        self.assertEqual(expected_hashes, hashes)
        expected_link_counts = [1, 1, 2, 2]
        self.assertEqual(expected_link_counts, link_counts)

        # Move the first hardlinked file to be last
        hl_file3 = hlsrc_sub.append("hardlink3")
        rpath.rename(hl_file1, hl_file3)

        InternalBackup(1, 1, hlsrc.path, output.path, 20000)
        self.assertEqual(out_subdir.append("hardlink2").getinode(),
                         out_subdir.append("hardlink3").getinode())

        # validate that hashes and link counts are correctly saved in metadata
        incs = meta_prefix.get_incfiles_list()
        self.assertEqual(len(incs), 2)
        if incs[0].getinctype() == b'snapshot':
            metadata_rp = incs[0]
        else:
            metadata_rp = incs[1]
        hashes, link_counts = self.extract_metadata(metadata_rp)
        # hashes for ., ./subdir/, ./subdir/hardlink2, ./subdir/hardlink3
        expected_hashes = [None, None, self.hello_str_hash, None]
        # The following assertion would fail as a result of bugs that are now fixed
        self.assertEqual(expected_hashes, hashes)
        expected_link_counts = [1, 1, 2, 2]
        self.assertEqual(expected_link_counts, link_counts)

        # Now try restoring, still checking hard links.
        sub_path = os.path.join(abs_output_dir, b"subdir")
        restore_path = os.path.join(abs_test_dir, b"hl_restore")
        restore_dir = rpath.RPath(Globals.local_connection, restore_path)
        hlrestore_file1 = restore_dir.append("hardlink1")
        hlrestore_file2 = restore_dir.append("hardlink2")
        hlrestore_file3 = restore_dir.append("hardlink3")

        if restore_dir.lstat():
            restore_dir.delete()
        InternalRestore(1, 1, sub_path, restore_path, 10000)
        for rp in [hlrestore_file1, hlrestore_file2]:
            rp.setdata()
        self.assertEqual(hlrestore_file1.getinode(), hlrestore_file2.getinode())

        if restore_dir.lstat():
            restore_dir.delete()
        InternalRestore(1, 1, sub_path, restore_path, 20000)
        for rp in [hlrestore_file2, hlrestore_file3]:
            rp.setdata()
        self.assertEqual(hlrestore_file2.getinode(), hlrestore_file3.getinode())


if __name__ == "__main__":
    unittest.main()
