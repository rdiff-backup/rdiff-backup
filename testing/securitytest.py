import os
import unittest
import time
import traceback
import sys
from commontest import old_test_dir, abs_output_dir, abs_restore_dir, Myrm, \
    rdiff_backup, RBBin, SetConnections
from rdiff_backup import Globals, rpath
import rdiff_backup.Security as Security


class SecurityTest(unittest.TestCase):
    various_files_dir = os.path.join(old_test_dir, b"various_file_types")

    def assert_exc_sec(self, exc):
        """Fudge - make sure exception is a security violation

        This is necessary because of some kind of pickling/module
        problem.

        """
        if not isinstance(exc, Security.Violation):
            type, value, tb = sys.exc_info()
            print("".join(traceback.format_tb(tb)))
            raise exc

    def test_vet_request_ro(self):
        """Test vetting of ConnectionRequests on read-only server"""
        remote_cmd = b"%s --server --restrict-read-only foo" % RBBin
        conn = SetConnections.init_connection(remote_cmd)
        assert isinstance(conn.os.getuid(), int), conn.os.getuid()
        try:
            conn.os.remove(b"/tmp/foobar")
        except Exception as e:
            self.assert_exc_sec(e)
        else:
            assert 0, "No exception raised"
        SetConnections.CloseConnections()

    def test_vet_request_minimal(self):
        """Test vetting of ConnectionRequests on minimal server"""
        remote_cmd = b"%s --server --restrict-update-only foo" % RBBin
        conn = SetConnections.init_connection(remote_cmd)
        assert isinstance(conn.os.getuid(), int), conn.os.getuid()
        try:
            conn.os.remove(b"/tmp/foobar")
        except Exception as e:
            self.assert_exc_sec(e)
        else:
            assert 0, "No exception raised"
        SetConnections.CloseConnections()

    def test_vet_rpath(self):
        """Test to make sure rpaths not in restricted path will be rejected"""
        remote_cmd = b"%s --server --restrict-update-only foo" % RBBin
        conn = SetConnections.init_connection(remote_cmd)

        for rp in [
                rpath.RPath(Globals.local_connection, b"blahblah"),
                rpath.RPath(conn, b"foo/bar")
        ]:
            conn.Globals.set("TEST_var", rp)
            assert conn.Globals.get("TEST_var").path == rp.path

        for path in [b"foobar", b"/usr/local", b"foo/../bar"]:
            try:
                rp = rpath.RPath(conn, path)
                conn.Globals.set("TEST_var", rp)
            except Exception as e:
                self.assert_exc_sec(e)
                continue
            assert 0, "No violation raised by rp %s" % str(rp)

        SetConnections.CloseConnections()

    def test_vet_rpath_root(self):
        """Test vetting when restricted to root"""
        remote_cmd = b"%s --server --restrict-update-only /" % RBBin
        conn = SetConnections.init_connection(remote_cmd)
        for rp in [
                rpath.RPath(Globals.local_connection, "blahblah"),
                rpath.RPath(conn, "foo/bar")
        ]:
            conn.Globals.set("TEST_var", rp)
            assert conn.Globals.get("TEST_var").path == rp.path
        SetConnections.CloseConnections()

    def secure_rdiff_backup(self,
                            in_dir,
                            out_dir,
                            in_local,
                            restrict_args,
                            extra_args=b"",
                            success=1,
                            current_time=None):
        """Run rdiff-backup locally, with given restrict settings"""
        if not current_time:
            current_time = int(time.time())
        # escape the %s of the remote schema with double %
        prefix = (b'%b --current-time %i --remote-schema %%s ' %
                  (RBBin, current_time))

        if in_local:
            out_dir = (b"'%b %b --server'::%b" %
                       (RBBin, restrict_args, out_dir))
        else:
            in_dir = (b"'%b %b --server'::%b" % (RBBin, restrict_args, in_dir))

        cmdline = b"%b %b %b %b" % (prefix, extra_args, in_dir, out_dir)
        print("Executing:", cmdline)
        exit_val = os.system(cmdline)
        if success:
            assert not exit_val
        else:
            assert exit_val, "Success when wanted failure"

    def test_restrict_positive(self):
        """Test that --restrict switch doesn't get in the way

        This makes sure that basic backups with the restrict operator
        work, (initial backup, incremental, restore).

        """
        Myrm(abs_output_dir)
        self.secure_rdiff_backup(self.various_files_dir,
                                 abs_output_dir,
                                 1,
                                 b'--restrict %b' % abs_output_dir,
                                 current_time=10000)
        # Note the backslash below -- eest for bug in path normalization
        self.secure_rdiff_backup(self.various_files_dir, abs_output_dir, 1,
                                 b'--restrict %b/' % abs_output_dir)

        Myrm(abs_restore_dir)
        self.secure_rdiff_backup(abs_output_dir,
                                 abs_restore_dir,
                                 1,
                                 b'--restrict %b' % abs_restore_dir,
                                 extra_args=b'-r now')

    def test_restrict_negative(self):
        """Test that --restrict switch denies certain operations"""
        # Backup to wrong directory
        output2_dir = abs_output_dir + b"2"
        Myrm(abs_output_dir)
        Myrm(output2_dir)
        self.secure_rdiff_backup(self.various_files_dir,
                                 output2_dir,
                                 1,
                                 b'--restrict %b' % abs_output_dir,
                                 success=0)

        # Restore to wrong directory
        Myrm(abs_output_dir)
        Myrm(abs_restore_dir)
        rdiff_backup(1, 1, self.various_files_dir, abs_output_dir)
        self.secure_rdiff_backup(abs_output_dir,
                                 abs_restore_dir,
                                 1,
                                 b'--restrict %b' % output2_dir,
                                 extra_args=b'-r now',
                                 success=0)

        # Backup from wrong directory
        Myrm(abs_output_dir)
        wrong_files_dir = os.path.join(old_test_dir, b"foobar")
        self.secure_rdiff_backup(self.various_files_dir,
                                 abs_output_dir,
                                 0,
                                 b'--restrict %b' % wrong_files_dir,
                                 success=0)

    def test_restrict_readonly_positive(self):
        """Test that --restrict-read-only switch doesn't impair normal ops"""
        Myrm(abs_output_dir)
        Myrm(abs_restore_dir)
        self.secure_rdiff_backup(
            self.various_files_dir, abs_output_dir, 0,
            b'--restrict-read-only %b' % self.various_files_dir)

        self.secure_rdiff_backup(abs_output_dir,
                                 abs_restore_dir,
                                 0,
                                 b'--restrict-read-only %b' % abs_output_dir,
                                 extra_args=b'-r now')

    def test_restrict_readonly_negative(self):
        """Test that --restrict-read-only doesn't allow too much"""
        # Backup to restricted directory
        Myrm(abs_output_dir)
        self.secure_rdiff_backup(self.various_files_dir,
                                 abs_output_dir,
                                 1,
                                 b'--restrict-read-only %b' % abs_output_dir,
                                 success=0)

        # Restore to restricted directory
        Myrm(abs_output_dir)
        Myrm(abs_restore_dir)
        rdiff_backup(1, 1, self.various_files_dir, abs_output_dir)
        self.secure_rdiff_backup(abs_output_dir,
                                 abs_restore_dir,
                                 1,
                                 b'--restrict-read-only %b' % abs_restore_dir,
                                 extra_args=b'-r now',
                                 success=0)

    def test_restrict_updateonly_positive(self):
        """Test that --restrict-update-only allows intended use"""
        Myrm(abs_output_dir)
        rdiff_backup(1,
                     1,
                     self.various_files_dir,
                     abs_output_dir,
                     current_time=10000)
        self.secure_rdiff_backup(self.various_files_dir, abs_output_dir, 1,
                                 b'--restrict-update-only %b' % abs_output_dir)

    def test_restrict_updateonly_negative(self):
        """Test that --restrict-update-only impairs unintended"""
        Myrm(abs_output_dir)
        self.secure_rdiff_backup(self.various_files_dir,
                                 abs_output_dir,
                                 1,
                                 b'--restrict-update-only %b' % abs_output_dir,
                                 success=0)

        Myrm(abs_output_dir)
        Myrm(abs_restore_dir)
        rdiff_backup(1, 1, self.various_files_dir, abs_output_dir)
        self.secure_rdiff_backup(abs_output_dir,
                                 abs_restore_dir,
                                 1,
                                 b'--restrict-update-only %b' %
                                 abs_restore_dir,
                                 extra_args=b'-r now',
                                 success=0)

    def test_restrict_bug(self):
        """Test for bug 14209 --- mkdir outside --restrict arg"""
        Myrm(abs_output_dir)
        self.secure_rdiff_backup(self.various_files_dir,
                                 abs_output_dir,
                                 1,
                                 b'--restrict foobar',
                                 success=0)
        output = rpath.RPath(Globals.local_connection, abs_output_dir)
        assert not output.lstat()

    def test_quoting_bug(self):
        """Test for bug 14545 --- quoting causes bad violation"""
        Myrm(abs_output_dir)
        self.secure_rdiff_backup(self.various_files_dir,
                                 abs_output_dir,
                                 1,
                                 b'',
                                 extra_args=b'--override-chars-to-quote e')


if __name__ == "__main__":
    unittest.main()
