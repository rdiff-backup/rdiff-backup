import unittest
import os
from commontest import rdiff_backup, abs_output_dir, abs_test_dir, \
    old_inc2_dir, old_inc3_dir, re_init_subdir
import commontest as comtst
from rdiff_backup import Globals, rpath
"""Test the compare.py module and overall compare functionality"""

# FIXME the remote comparison tests have to be skipped under Windows
# see https://github.com/rdiff-backup/rdiff-backup/issues/788


class CompareTest(unittest.TestCase):
    def setUp(self):
        self.outdir = re_init_subdir(abs_test_dir, b"output")
        rdiff_backup(1, 1, old_inc2_dir, self.outdir, current_time=10000)
        rdiff_backup(1, 1, old_inc3_dir, self.outdir, current_time=20000)

    def generic_test(self, local, compare_method):
        """Used for 6 tests below"""
        if not local:  # need a fix for Windows only present in API 201
            options = ("--api-version", "201")
        else:
            options = ()  # just to also test the old API
        compare_options = ("--method", compare_method)

        self.assertEqual(comtst.rdiff_backup_action(
            local, local, old_inc3_dir, self.outdir, options,
            b"compare", compare_options), Globals.RET_CODE_OK)
        self.assertNotEqual(comtst.rdiff_backup_action(
            local, local, old_inc2_dir, self.outdir, options,
            b"compare", compare_options), Globals.RET_CODE_OK)

        compare_options += ("--at", "10000")

        self.assertEqual(comtst.rdiff_backup_action(
            local, local, old_inc2_dir, self.outdir, options,
            b"compare", compare_options), Globals.RET_CODE_OK)
        self.assertNotEqual(comtst.rdiff_backup_action(
            local, local, old_inc3_dir, self.outdir, options,
            b"compare", compare_options), Globals.RET_CODE_OK)

    def testBasicLocal(self):
        """Test basic --compare and --compare-at-time modes"""
        self.generic_test(1, b"meta")

    def testBasicRemote(self):
        """Test basic --compare and --compare-at-time modes, both remote"""
        self.generic_test(0, b"meta")

    def testHashLocal(self):
        """Test --compare-hash and --compare-hash-at-time modes local"""
        self.generic_test(1, b"hash")

    def testHashRemote(self):
        """Test --compare-hash and -at-time remotely"""
        self.generic_test(0, b"hash")

    def testFullLocal(self):
        """Test --compare-full and --compare-full-at-time"""
        self.generic_test(1, b"full")

    def testFullRemote(self):
        """Test full file compare remotely"""
        self.generic_test(0, b"full")

    def generic_selective_test(self, local, compare_method):
        """Used for selective tests--just compare part of a backup"""
        if not local:  # need a fix for Windows only present in API 201
            options = ("--api-version", "201")
        else:
            options = ()  # just to also test the old API
        compare_options = ("--method", compare_method)

        self.assertEqual(comtst.rdiff_backup_action(
            local, local,
            os.path.join(old_inc3_dir, b'various_file_types'),
            os.path.join(abs_output_dir, b'various_file_types'),
            options, b"compare", compare_options), Globals.RET_CODE_OK)
        self.assertNotEqual(comtst.rdiff_backup_action(
            local, local,
            os.path.join(old_inc2_dir, b'increment1'),
            os.path.join(abs_output_dir, b'increment1'),
            options, b"compare", compare_options), Globals.RET_CODE_OK)

        compare_options += ("--at", "10000")

        self.assertEqual(comtst.rdiff_backup_action(
            local, local,
            os.path.join(old_inc2_dir, b'newdir'),
            os.path.join(abs_output_dir, b'newdir'),
            options, b"compare", compare_options), Globals.RET_CODE_OK)
        self.assertNotEqual(comtst.rdiff_backup_action(
            local, local,
            os.path.join(old_inc3_dir, b'newdir'),
            os.path.join(abs_output_dir, b'newdir'),
            options, b"compare", compare_options), Globals.RET_CODE_OK)

    def testSelLocal(self):
        """Test basic local compare of single subdirectory"""
        self.generic_selective_test(1, b"meta")

    def testSelRemote(self):
        """Test --compare of single directory, remote"""
        self.generic_selective_test(0, b"meta")

    def testSelHashLocal(self):
        """Test --compare-hash of subdirectory, local"""
        self.generic_selective_test(1, b"hash")

    def testSelHashRemote(self):
        """Test --compare-hash of subdirectory, remote"""
        self.generic_selective_test(0, b"hash")

    def testSelFullLocal(self):
        """Test --compare-full of subdirectory, local"""
        self.generic_selective_test(1, b"full")

    def testSelFullRemote(self):
        """Test --compare-full of subdirectory, remote"""
        self.generic_selective_test(0, b"full")

    def verify(self, local):
        """Used for the verify tests"""

        def change_file(rp):
            """Given rpath, open it, and change a byte in the middle"""
            fp = rp.open("rb")
            fp.seek(int(rp.getsize() / 2))
            char = fp.read(1)
            fp.close()

            fp = rp.open("wb")
            fp.seek(int(rp.getsize() / 2))
            if char == b'a':
                fp.write(b'b')
            else:
                fp.write(b'a')
            fp.close()

        def modify_diff():
            """Write to the stph_icons.h diff"""
            incs_dir = os.path.join(abs_output_dir, b'rdiff-backup-data',
                                    b'increments')
            templist = [
                filename for filename in os.listdir(incs_dir)
                if filename.startswith(b'stph_icons.h')
            ]
            self.assertEqual(
                len(templist), 1,
                "There should be only one diff file in '{diffs}'. "
                "Something is wrong with the test setup.".format(
                    diffs=templist))
            diff_rp = rpath.RPath(Globals.local_connection,
                                  os.path.join(incs_dir, templist[0]))
            change_file(diff_rp)

        rdiff_backup(local,
                     local,
                     abs_output_dir,
                     None,
                     extra_options=b"--verify")
        rdiff_backup(local,
                     local,
                     abs_output_dir,
                     None,
                     extra_options=b"--verify-at-time 10000")
        modify_diff()
        self.assertTrue(
            rdiff_backup(local,
                         local,
                         abs_output_dir,
                         None,
                         extra_options=b"--verify-at-time 10000",
                         expected_ret_code=None))
        change_file(
            rpath.RPath(Globals.local_connection,
                        os.path.join(abs_output_dir, b'stph_icons.h')))
        self.assertTrue(
            rdiff_backup(local,
                         local,
                         abs_output_dir,
                         None,
                         extra_options=b"--verify",
                         expected_ret_code=None))

    def testVerifyLocal(self):
        """Test --verify of directory, local"""
        self.verify(1)

    def testVerifyRemote(self):
        """Test --verify remotely"""
        self.verify(0)


if __name__ == "__main__":
    unittest.main()
