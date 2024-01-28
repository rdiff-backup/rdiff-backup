import errno
import os
import unittest

import commontest as comtst
from commontest import (
    abs_test_dir,
    old_test_dir,
    remove_dir,
    rdiff_backup,
    compare_recursive,
)

from rdiff_backup import Globals, rpath, Time

TEST_BASE_DIR = comtst.get_test_base_dir(__file__)

if os.name == "nt":
    NAME_MAX_LEN = 255
else:
    NAME_MAX_LEN = os.pathconf(abs_test_dir, "PC_NAME_MAX")


class LongNameTest(unittest.TestCase):
    """Test the longname module"""

    root_rp = rpath.RPath(Globals.local_connection, abs_test_dir)
    out_rp = root_rp.append_path("output")

    def test_length_limit(self):
        """Confirm that length limit is NAME_MAX_LEN

        Some of these tests depend on the length being at most
        NAME_MAX_LEN, so check to make sure it's accurate.

        """
        remove_dir(self.out_rp.path)
        self.out_rp.mkdir()

        really_long = self.out_rp.append("a" * NAME_MAX_LEN)
        really_long.touch()

        with self.assertRaises(
            OSError,
            msg="File name could exceed max length '{max}'.".format(max=NAME_MAX_LEN),
        ) as cm:
            self.out_rp.append("a" * (NAME_MAX_LEN + 1)).touch()
        self.assertEqual(cm.exception.errno, errno.ENAMETOOLONG)

    def make_input_dirs(self):
        """Create two input directories with long filename(s) in them"""
        dir1 = self.root_rp.append("longname1")
        dir2 = self.root_rp.append("longname2")
        remove_dir(dir1.path)
        remove_dir(dir2.path)

        dir1.mkdir()
        rp11 = dir1.append("A" * NAME_MAX_LEN)
        rp11.write_string("foobar")
        rp12 = dir1.append("B" * NAME_MAX_LEN)
        rp12.mkdir()
        rp121 = rp12.append("C" * NAME_MAX_LEN)
        rp121.touch()

        dir2.mkdir()
        rp21 = dir2.append("A" * NAME_MAX_LEN)
        rp21.write_string("Hello, world")
        rp22 = dir2.append("D" * NAME_MAX_LEN)
        rp22.mkdir()
        rp221 = rp22.append("C" * NAME_MAX_LEN)
        rp221.touch()

        return dir1, dir2

    def check_dir1(self, dirrp):
        """Make sure dirrp looks like dir1"""
        rp1 = dirrp.append("A" * NAME_MAX_LEN)
        self.assertEqual(rp1.get_string(), "foobar")
        rp2 = dirrp.append("B" * NAME_MAX_LEN)
        self.assertTrue(rp2.isdir())
        rp21 = rp2.append("C" * NAME_MAX_LEN)
        self.assertTrue(rp21.isreg())

    def check_dir2(self, dirrp):
        """Make sure dirrp looks like dir2"""
        rp1 = dirrp.append("A" * NAME_MAX_LEN)
        self.assertEqual(rp1.get_string(), "Hello, world")
        rp2 = dirrp.append("D" * NAME_MAX_LEN)
        self.assertTrue(rp2.isdir())
        rp21 = rp2.append("C" * NAME_MAX_LEN)
        self.assertTrue(rp21.isreg())

    def generic_test(self, inlocal, outlocal, extra_args, compare_back):
        """Used for some of the tests below"""
        in1, in2 = self.make_input_dirs()
        remove_dir(self.out_rp.path)
        restore_dir = self.root_rp.append("longname_out")

        # Test backing up
        rdiff_backup(
            inlocal,
            outlocal,
            in1.path,
            self.out_rp.path,
            10000,
            extra_options=extra_args + (b"backup",),
        )
        if compare_back:
            self.check_dir1(self.out_rp)
        rdiff_backup(
            inlocal,
            outlocal,
            in2.path,
            self.out_rp.path,
            20000,
            extra_options=extra_args + (b"backup",),
        )
        if compare_back:
            self.check_dir2(self.out_rp)

        # Now try restoring
        remove_dir(restore_dir.path)
        rdiff_backup(
            inlocal,
            outlocal,
            self.out_rp.path,
            restore_dir.path,
            30000,
            extra_options=extra_args + (b"restore", b"--at", b"now"),
        )
        self.check_dir2(restore_dir)
        remove_dir(restore_dir.path)
        rdiff_backup(
            1,
            1,
            self.out_rp.path,
            restore_dir.path,
            30000,
            extra_options=extra_args + (b"restore", b"--at", b"10000"),
        )
        self.check_dir1(restore_dir)

    def test_basic_local(self):
        """Test backup session when increment would be too long"""
        self.generic_test(1, 1, (), 1)

    def test_quoting_local(self):
        """Test backup session with quoting, so reg files also too long"""
        self.generic_test(1, 1, (b"--chars-to-quote", b"A-Z"), 0)

    def test_regress_basic(self):
        """Test regressing when increments would be too long"""
        in1, in2 = self.make_input_dirs()
        remove_dir(self.out_rp.path)
        restore_dir = self.root_rp.append("longname_out")
        remove_dir(restore_dir.path)

        rdiff_backup(
            1,
            1,
            in1.path,
            self.out_rp.path,
            10000,
        )
        rdiff_backup(
            1,
            1,
            in2.path,
            self.out_rp.path,
            20000,
        )

        # Regress repository back to in1 condition
        self.add_current_mirror(self.out_rp, 10000)
        comtst.rdiff_backup_action(True, True, self.out_rp, None, (), b"regress", ())

        # Restore in1 and compare
        rdiff_backup(
            1,
            1,
            self.out_rp.path,
            restore_dir.path,
            30000,
            extra_options=(b"restore", b"--at", b"now"),
        )
        self.check_dir1(restore_dir)

    def add_current_mirror(self, out_rp, time):
        """Add current_mirror marker at given time"""
        data_rp = self.out_rp.append_path("rdiff-backup-data")
        cur_mirror_rp = data_rp.append(
            "current_mirror.%s.data" % (Time.timetostring(time),)
        )
        cur_mirror_rp.touch()

    def test_long_socket_name(self):
        """Test when socket name is saved to a backup directory with a long name
        It addresses an issue where socket wasn't created with mknod but
        with socket.socket and bind, which has a limit at 107 characters."""
        input_dir = os.path.join(old_test_dir, b"select", b"filetypes")
        # create a target directory with a long name next to 107
        output_dir = os.path.join(abs_test_dir, b"tenletters" * 10)
        remove_dir(output_dir)
        restore_dir = os.path.join(abs_test_dir, b"restoresme" * 10)
        remove_dir(restore_dir)
        # backup and restore the input directory with socket, then compare
        rdiff_backup(True, True, input_dir, output_dir)
        rdiff_backup(
            True,
            True,
            output_dir,
            restore_dir,
            extra_options=(b"restore", b"--at", b"0"),
        )
        compare_recursive(
            rpath.RPath(Globals.local_connection, input_dir),
            rpath.RPath(Globals.local_connection, restore_dir),
        )


if __name__ == "__main__":
    unittest.main()
