"""
Test the security functionality of rdiff-backup
"""

import os
import time
import unittest

import commontest as comtst

from rdiff_backup import Globals, rpath, Security, SetConnections

TEST_BASE_DIR = comtst.get_test_base_dir(__file__)


class SecurityTest(unittest.TestCase):
    various_files_dir = os.path.join(comtst.old_test_dir, b"various_file_types")
    out_dir = os.path.join(TEST_BASE_DIR, b"output")
    restore_dir = os.path.join(TEST_BASE_DIR, b"restore")

    def test_vet_request_ro(self):
        """Test vetting of ConnectionRequests on read-only server"""
        remote_cmd = (
            b"%s server --restrict-path foo --restrict-mode read-only" % comtst.RBBin
        )
        conn = SetConnections._init_connection(remote_cmd)
        self.assertIsInstance(conn.os.getuid(), int)
        with self.assertRaises(Security.Violation):
            conn.os.remove(b"/tmp/foobar")
        SetConnections.CloseConnections()

    def test_vet_request_minimal(self):
        """Test vetting of ConnectionRequests on minimal server"""
        remote_cmd = (
            b"%s server --restrict-path foo --restrict-mode update-only" % comtst.RBBin
        )
        conn = SetConnections._init_connection(remote_cmd)
        self.assertIsInstance(conn.os.getuid(), int)
        with self.assertRaises(Security.Violation):
            conn.os.remove(b"/tmp/foobar")
        SetConnections.CloseConnections()

    def test_vet_rpath(self):
        """Test to make sure rpaths not in restricted path will be rejected"""
        remote_cmd = (
            b"%s server --restrict-path foo --restrict-mode update-only" % comtst.RBBin
        )
        conn = SetConnections._init_connection(remote_cmd)

        for rp in [
            rpath.RPath(Globals.local_connection, b"blahblah"),
            rpath.RPath(conn, b"foo/bar"),
        ]:
            conn.Globals.set_local("TEST_var", rp)
            self.assertEqual(conn.Globals.get("TEST_var").path, rp.path)

        for path in [b"foobar", b"/usr/local", b"foo/../bar"]:
            with self.assertRaises(Security.Violation):
                rp = rpath.RPath(conn, path)
                conn.Globals.set_local("TEST_var", rp)

        SetConnections.CloseConnections()

    def test_vet_rpath_root(self):
        """Test vetting when restricted to root"""
        remote_cmd = (
            b"%s server --restrict-path / --restrict-mode update-only" % comtst.RBBin
        )
        conn = SetConnections._init_connection(remote_cmd)
        for rp in [
            rpath.RPath(Globals.local_connection, "blahblah"),
            rpath.RPath(conn, "foo/bar"),
        ]:
            conn.Globals.set_local("TEST_var", rp)
            self.assertEqual(conn.Globals.get("TEST_var").path, rp.path)
        SetConnections.CloseConnections()

    def secure_rdiff_backup(
        self,
        in_dir,
        out_dir,
        in_local,
        restrict_args,
        extra_args=(b"backup",),
        expected_ret_code=0,
        current_time=None,
    ):
        """Run rdiff-backup locally, with given restrict settings"""
        if not current_time:
            current_time = int(time.time())

        if in_local:
            out_dir = b"%b server %b::%b" % (comtst.RBBin, restrict_args, out_dir)
        else:
            in_dir = b"%b server %b::%b" % (comtst.RBBin, restrict_args, in_dir)

        cmdline = [
            comtst.RBBin,
            b"--current-time",
            b"%i" % current_time,
            b"--remote-schema",
            b"{h}",
        ]
        cmdline.extend(extra_args)
        cmdline.append(in_dir)
        cmdline.append(out_dir)
        print("Executing:", cmdline)
        exit_val = comtst.os_system(cmdline)
        if expected_ret_code is not None:
            self.assertEqual(exit_val, expected_ret_code)

    def test_restrict_positive(self):
        """Test that --restrict switch doesn't get in the way

        This makes sure that basic backups with the restrict operator
        work, (initial backup, incremental, restore).

        """
        comtst.remove_dir(self.out_dir)
        self.secure_rdiff_backup(
            self.various_files_dir,
            self.out_dir,
            1,
            b"--restrict-path %b" % self.out_dir,
            current_time=10000,
        )
        # Note the backslash below -- eest for bug in path normalization
        self.secure_rdiff_backup(
            self.various_files_dir,
            self.out_dir,
            1,
            b"--restrict-path %b/" % self.out_dir,
        )

        comtst.remove_dir(self.restore_dir)
        self.secure_rdiff_backup(
            self.out_dir,
            self.restore_dir,
            1,
            b"--restrict-path %b" % self.restore_dir,
            extra_args=(b"restore", b"--at", b"now"),
        )

    def test_restrict_negative(self):
        """Test that --restrict switch denies certain operations"""
        # Backup to wrong directory
        output2_dir = self.out_dir + b"2"
        comtst.remove_dir(self.out_dir)
        comtst.remove_dir(output2_dir)
        self.secure_rdiff_backup(
            self.various_files_dir,
            output2_dir,
            1,
            b"--restrict-path %b" % self.out_dir,
            expected_ret_code=Globals.RET_CODE_ERR,
        )

        # Restore to wrong directory
        comtst.remove_dir(self.out_dir)
        comtst.remove_dir(self.restore_dir)
        comtst.rdiff_backup(1, 1, self.various_files_dir, self.out_dir)
        self.secure_rdiff_backup(
            self.out_dir,
            self.restore_dir,
            1,
            b"--restrict-path %b" % output2_dir,
            extra_args=(b"restore", b"--at", b"now"),
            expected_ret_code=Globals.RET_CODE_ERR,
        )

        # Backup from wrong directory
        comtst.remove_dir(self.out_dir)
        wrong_files_dir = os.path.join(comtst.old_test_dir, b"foobar")
        self.secure_rdiff_backup(
            self.various_files_dir,
            self.out_dir,
            0,
            b"--restrict-path %b" % wrong_files_dir,
            expected_ret_code=Globals.RET_CODE_ERR,
        )

    def test_restrict_readonly_positive(self):
        """
        Test that --restrict-mode read-only switch doesn't impair normal ops
        """
        comtst.remove_dir(self.out_dir)
        comtst.remove_dir(self.restore_dir)
        self.secure_rdiff_backup(
            self.various_files_dir,
            self.out_dir,
            0,
            b"--restrict-path %b "
            b"--restrict-mode read-only" % self.various_files_dir,
        )

        self.secure_rdiff_backup(
            self.out_dir,
            self.restore_dir,
            0,
            b"--restrict-path %b --restrict-mode read-only" % self.out_dir,
            extra_args=(b"restore", b"--at", b"now"),
            expected_ret_code=Globals.RET_CODE_OK,
        )

    def test_restrict_readonly_negative(self):
        """Test that --restrict-mode read-only doesn't allow too much"""
        # Backup to restricted directory
        comtst.remove_dir(self.out_dir)
        self.secure_rdiff_backup(
            self.various_files_dir,
            self.out_dir,
            1,
            b"--restrict-path %b --restrict-mode read-only" % self.out_dir,
            expected_ret_code=Globals.RET_CODE_ERR,
        )

        # Restore to restricted directory
        comtst.remove_dir(self.out_dir)
        comtst.remove_dir(self.restore_dir)
        comtst.rdiff_backup(1, 1, self.various_files_dir, self.out_dir)
        self.secure_rdiff_backup(
            self.out_dir,
            self.restore_dir,
            1,
            b"--restrict-path %b --restrict-mode read-only" % self.restore_dir,
            extra_args=(b"restore", b"--at", b"now"),
            expected_ret_code=Globals.RET_CODE_ERR,
        )

    def test_restrict_updateonly_positive(self):
        """Test that --restrict-mode update-only allows intended use"""
        comtst.remove_dir(self.out_dir)
        comtst.rdiff_backup(
            1, 1, self.various_files_dir, self.out_dir, current_time=10000
        )
        self.secure_rdiff_backup(
            self.various_files_dir,
            self.out_dir,
            1,
            b"--restrict-path %b --restrict-mode update-only" % self.out_dir,
        )

    def test_restrict_updateonly_negative(self):
        """Test that --restrict-mode update-only impairs unintended"""
        comtst.remove_dir(self.out_dir)
        self.secure_rdiff_backup(
            self.various_files_dir,
            self.out_dir,
            1,
            b"--restrict-path %b --restrict-mode update-only" % self.out_dir,
            expected_ret_code=Globals.RET_CODE_OK,
            # FIXME following was the correct value under old versions
            # but the new concept doesn't differentiate update from r/w
            # expected_ret_code=Globals.RET_CODE_ERR,
        )

        comtst.remove_dir(self.out_dir)
        comtst.remove_dir(self.restore_dir)
        comtst.rdiff_backup(1, 1, self.various_files_dir, self.out_dir)
        self.secure_rdiff_backup(
            self.out_dir,
            self.restore_dir,
            1,
            b"--restrict-path %b --restrict-mode update-only" % self.restore_dir,
            extra_args=(b"restore", b"--at", b"now"),
            expected_ret_code=Globals.RET_CODE_ERR,
        )

    def test_restrict_bug(self):
        """Test for bug 14209 --- mkdir outside --restrict arg"""
        comtst.remove_dir(self.out_dir)
        self.secure_rdiff_backup(
            self.various_files_dir,
            self.out_dir,
            1,
            b"--restrict-path foobar",
            expected_ret_code=Globals.RET_CODE_ERR,
        )
        output = rpath.RPath(Globals.local_connection, self.out_dir)
        self.assertFalse(output.lstat())

    def test_quoting_bug(self):
        """Test for bug 14545 --- quoting causes bad violation"""
        comtst.remove_dir(self.out_dir)
        self.secure_rdiff_backup(
            self.various_files_dir,
            self.out_dir,
            1,
            b"",
            extra_args=(b"--chars-to-quote", b"e", b"backup"),
        )


if __name__ == "__main__":
    unittest.main()
