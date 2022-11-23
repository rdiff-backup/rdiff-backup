import unittest
import os
import re
import time
import pathlib
from commontest import rdiff_backup, Myrm, compare_recursive, \
    old_test_dir, abs_test_dir, get_increment_rp, xcopytree
from rdiff_backup import Globals, log, rpath, robust, FilenameMapping, Time, selection
"""Regression tests"""

Globals.exclude_mirror_regexps = [re.compile(b".*/rdiff-backup-data")]

lc = Globals.local_connection


class Local:
    """This is just a place to put increments relative to the local
    connection"""

    def get_src_local_rp(extension):
        return rpath.RPath(Globals.local_connection,
                           os.path.join(old_test_dir, os.fsencode(extension)))

    def get_tgt_local_rp(extension):
        return rpath.RPath(Globals.local_connection,
                           os.path.join(abs_test_dir, os.fsencode(extension)))

    vftrp = get_src_local_rp('various_file_types')
    emptyrp = get_src_local_rp('empty')
    inc1rp = get_src_local_rp('increment1')
    inc2rp = get_src_local_rp('increment2')
    inc3rp = get_src_local_rp('increment3')
    inc4rp = get_src_local_rp('increment4')
    backup1rp = get_src_local_rp('restoretest')
    backup2rp = get_src_local_rp('restoretest2')
    backup3rp = get_src_local_rp('restoretest3')
    backup4rp = get_src_local_rp('restoretest4')
    backup5rp = get_src_local_rp('restoretest5')

    rpout = get_tgt_local_rp('output')
    rpout_inc = get_tgt_local_rp('output_inc')
    rpout1 = get_tgt_local_rp('restoretarget1')
    rpout2 = get_tgt_local_rp('restoretarget2')
    rpout3 = get_tgt_local_rp('restoretarget3')
    rpout4 = get_tgt_local_rp('restoretarget4')

    vft_in = get_src_local_rp('increment2/various_file_types')
    vft_out = get_tgt_local_rp('vft_out')
    vft_recover = get_tgt_local_rp('vft2_out')

    timbar_in = get_src_local_rp('increment1/timbar.pyc')
    timbar_out = get_tgt_local_rp('timbar.pyc')  # in cur directory

    # these directories are actually source directories but will be created
    # on the fly from the incrementX directories (without win-)
    wininc2 = get_tgt_local_rp('win-increment2')
    wininc3 = get_tgt_local_rp('win-increment3')


class PathSetter(unittest.TestCase):
    def refresh(self, *rp_list):
        """Reread data for the given rps"""
        for rp in rp_list:
            rp.setdata()

    def delete_tmpdirs(self):
        """Remove any temp directories created by previous tests"""
        self.refresh(Local.rpout, Local.rpout1, Local.rpout2, Local.rpout3,
                     Local.rpout4, Local.vft_recover, Local.timbar_out,
                     Local.vft_out)
        if Local.rpout.lstat():
            Local.rpout.delete()
        if Local.rpout1.lstat():
            Local.rpout1.delete()
        if Local.rpout2.lstat():
            Local.rpout2.delete()
        if Local.rpout3.lstat():
            Local.rpout3.delete()
        if Local.rpout4.lstat():
            Local.rpout4.delete()
        if Local.vft_recover.lstat():
            Local.vft_recover.delete()
        if Local.timbar_out.lstat():
            Local.timbar_out.delete()
        if Local.vft_out.lstat():
            Local.vft_out.delete()

    def runtest(self, from_local, to_local):
        self.delete_tmpdirs()

        # Backing up increment1
        rdiff_backup(from_local,
                     to_local,
                     Local.inc1rp.path,
                     Local.rpout.path,
                     current_time=10000)
        self.assertTrue(compare_recursive(Local.inc1rp, Local.rpout))
        time.sleep(1)

        # Backing up increment2
        rdiff_backup(from_local,
                     to_local,
                     Local.inc2rp.path,
                     Local.rpout.path,
                     current_time=20000)
        self.assertTrue(compare_recursive(Local.inc2rp, Local.rpout))
        time.sleep(1)

        # Backing up increment3
        rdiff_backup(from_local,
                     to_local,
                     Local.inc3rp.path,
                     Local.rpout.path,
                     current_time=30000)
        self.assertTrue(compare_recursive(Local.inc3rp, Local.rpout))
        time.sleep(1)

        # Backing up increment4
        rdiff_backup(from_local,
                     to_local,
                     Local.inc4rp.path,
                     Local.rpout.path,
                     current_time=40000)
        self.assertTrue(compare_recursive(Local.inc4rp, Local.rpout))

        # Getting restore rps
        inc_paths = self.getinc_paths(
            b"increments.", os.path.join(Local.rpout.path,
                                         b"rdiff-backup-data"))
        self.assertEqual(len(inc_paths), 3)

        # Restoring increment1
        rdiff_backup(from_local, to_local, inc_paths[0], Local.rpout1.path,
                     extra_options=b"--restore")
        self.assertTrue(compare_recursive(Local.inc1rp, Local.rpout1))

        # Restoring increment2
        rdiff_backup(from_local, to_local, inc_paths[1], Local.rpout2.path,
                     extra_options=b"--restore")
        self.assertTrue(compare_recursive(Local.inc2rp, Local.rpout2))

        # Restoring increment3
        rdiff_backup(from_local, to_local, inc_paths[2], Local.rpout3.path,
                     extra_options=b"--restore")
        self.assertTrue(compare_recursive(Local.inc3rp, Local.rpout3))

        # Test restoration of a few random files
        vft_paths = self.getinc_paths(
            b"various_file_types.",
            os.path.join(Local.rpout.path, b"rdiff-backup-data",
                         b"increments"))
        rdiff_backup(from_local, to_local, vft_paths[1], Local.vft_out.path,
                     extra_options=b"--restore")
        self.refresh(Local.vft_in, Local.vft_out)
        self.assertTrue(compare_recursive(Local.vft_in, Local.vft_out))

        timbar_paths = self.getinc_paths(
            b"timbar.pyc.",
            os.path.join(Local.rpout.path, b"rdiff-backup-data",
                         b"increments"))
        rdiff_backup(from_local, to_local, timbar_paths[0],
                     Local.timbar_out.path,
                     extra_options=b"--restore")
        self.refresh(Local.timbar_in, Local.timbar_out)
        self.assertTrue(Local.timbar_in.equal_loose(Local.timbar_out))

        rdiff_backup(from_local,
                     to_local,
                     Local.rpout.append('various_file_types').path,
                     Local.vft_recover.path,
                     extra_options=b"--restore-as-of 25000")
        self.refresh(Local.vft_recover, Local.vft_in)
        self.assertTrue(compare_recursive(Local.vft_recover, Local.vft_in))

        # Make sure too many increment files not created
        self.assertEqual(len(self.getinc_paths(
            b"nochange.", os.path.join(Local.rpout.path, b"rdiff-backup-data",
                                       b"increments"))), 0)
        nochange_incs = len(self.getinc_paths(
            b"", os.path.join(Local.rpout.path, b"rdiff-backup-data",
                              b"increments", b"nochange")))
        self.assertIn(nochange_incs, (0, 1))

    def getinc_paths(self, basename, directory, quoted=0):
        """Returns a sorted list of files which starts with basename
        within a given directory."""

        if quoted:
            FilenameMapping.set_init_quote_vals()
            dirrp = FilenameMapping.QuotedRPath(Globals.local_connection,
                                                directory)
        else:
            dirrp = rpath.RPath(Globals.local_connection, directory)
        incbasenames = [
            filename for filename in robust.listrp(dirrp)
            if filename.startswith(basename)
        ]
        incbasenames.sort()
        incrps = list(map(dirrp.append, incbasenames))
        return [
            x.path for x in [incrp for incrp in incrps if incrp.isincfile()]
        ]


class Final(PathSetter):
    def testLocal(self):
        """Run test sequence everything local"""
        self.runtest(True, True)

    def testRemoteAll(self):
        """Run test sequence everything remote"""
        self.runtest(False, False)

    def testRemoteSource(self):
        """Run test sequence when remote side is source"""
        self.runtest(False, True)

    def testRemoteDest(self):
        """Run test sequence when remote side is destination"""
        self.runtest(True, False)

    # FIXME see issue #35 for backup of proc filesystems
    # https://github.com/ericzolf/rdiff-backup/issues/35
    @unittest.skip("Not sure it makes any sense to backup proc FIXME")
    def testProcLocal(self):
        """Test initial backup of /proc locally"""
        procout_dir = os.path.join(abs_test_dir, b"procoutput")
        Myrm(procout_dir)
        procout = rpath.RPath(Globals.local_connection, procout_dir)
        rdiff_backup(True, True, '/proc', procout.path, current_time=10000)
        time.sleep(1)
        rdiff_backup(True, True, '/proc', procout.path, current_time=20000)
        time.sleep(1)
        rdiff_backup(True,
                     True,
                     Local.inc1rp.path,
                     procout.path,
                     current_time=30000)
        self.assertTrue(compare_recursive(Local.inc1rp, procout))
        time.sleep(1)
        rdiff_backup(True, True, '/proc', procout.path, current_time=40000)

    @unittest.skip("Not sure it makes any sense to backup proc FIXME")
    def testProcLocalToRemote(self):
        """Test mirroring proc remote"""
        procout_dir = os.path.join(abs_test_dir, b"procoutput")
        Myrm(procout_dir)
        procout = rpath.RPath(Globals.local_connection, procout_dir)
        rdiff_backup(True, False, '/proc', procout.path, current_time=10000)
        time.sleep(1)
        rdiff_backup(True, False, '/proc', procout.path, current_time=20000)
        time.sleep(1)
        rdiff_backup(True,
                     False,
                     Local.inc1rp.path,
                     procout.path,
                     current_time=30000)
        self.assertTrue(compare_recursive(Local.inc1rp, procout))
        time.sleep(1)
        rdiff_backup(True, False, '/proc', procout.path, current_time=40000)

    @unittest.skip("Not sure it makes any sense to backup proc FIXME")
    def testProcRemoteToLocal(self):
        """Test mirroring proc, this time when proc is remote, dest local"""
        procout_dir = os.path.join(abs_test_dir, b"procoutput")
        Myrm(procout_dir)
        procout = rpath.RPath(Globals.local_connection, procout_dir)
        rdiff_backup(False, True, '/proc', procout.path)

    # FIXME: to be done later, Windows isn't yet priority
    @unittest.skipUnless(os.name == "nt", "Requires Windows support")
    def testWindowsMode(self):
        """Test backup with quoting enabled

        We need to delete from the increment? directories long file
        names, because quoting adds too many extra letters.

        """

        def delete_long(base_rp, length=100):
            """Delete filenames longer than length given"""
            for rp in selection.Select(base_rp).get_select_iter():
                if len(rp.dirsplit()[1]) > length:
                    rp.delete()

        if not Local.wininc2.lstat() or not Local.wininc3.lstat():
            xcopytree(b"testfiles/increment2", b"testfiles/win-increment2")
            xcopytree(b"testfiles/increment3", b"testfiles/win-increment3")
            delete_long(Local.wininc2)
            delete_long(Local.wininc3)

        old_schema = self.rb_schema
        self.rb_schema = old_schema + b" --override-chars-to-quote '^a-z0-9_ -.' "
        self.set_connections(None, None, None, None)

        self.delete_tmpdirs()
        # Back up increment2, this contains a file with colons
        self.exec_rb(20000, b'testfiles/win-increment2', b'testfiles/output')
        self.rb_schema = old_schema  # Quoting setting should now be saved
        time.sleep(1)

        # Back up increment3
        self.exec_rb(30000, b'testfiles/win-increment3', b'testfiles/output')

        # Now check to make sure no ":" in output directory
        popen_fp = os.popen(b"find testfiles/output -name '*:*' | wc")
        wc_output = popen_fp.read()
        popen_fp.close()
        self.assertEqual(wc_output.split(), [b"0", b"0", b"0"])

        # Start restore of increment 2
        Globals.chars_to_quote = b'^a-z0-9_ -.'
        inc_paths = self.getinc_paths(b"increments.",
                                      b"testfiles/output/rdiff-backup-data", 1)
        Globals.chars_to_quote = None
        self.assertEqual(len(inc_paths), 1)
        self.exec_rb(None, inc_paths[0], b'testfiles/restoretarget2')
        self.assertTrue(
            compare_recursive(Local.wininc2, Local.rpout2, compare_hardlinks=0))

        # Restore increment 3 again, using different syntax
        self.rb_schema = old_schema + b'-r 30000 '
        self.exec_rb(None, b'testfiles/output', b'testfiles/restoretarget3')
        self.assertTrue(
            compare_recursive(Local.wininc3, Local.rpout3, compare_hardlinks=0))
        self.rb_schema = old_schema

    @unittest.skipIf(os.name == "nt",
                     "Windows doesn't recognize case insensitivity")
    def testLegacy(self):
        """Test restoring directory with no mirror_metadata file"""
        self.delete_tmpdirs()
        rdiff_backup(True,
                     True,
                     Local.vftrp.path,
                     Local.rpout.path,
                     current_time=10000)
        rdiff_backup(True,
                     True,
                     Local.emptyrp.path,
                     Local.rpout.path,
                     current_time=20000)
        # remove mirror_metadata files to simulate old style backups
        # pathlib.Path doesn't work with bytes hence need to work with str path
        for mirror_file in pathlib.Path(
                os.fsdecode(Local.rpout.append(
                    b'rdiff-backup-data').path)).glob('mirror_metadata*'):
            mirror_file.unlink()
        rdiff_backup(True,
                     True,
                     Local.rpout.path,
                     Local.rpout1.path,
                     extra_options=b'-r0')
        self.assertTrue(
            compare_recursive(Local.vftrp, Local.rpout1, compare_hardlinks=0))


class FinalMisc(PathSetter):
    """Test miscellaneous operations like list-increments, etc.

    Many of these just run and make sure there were no errors; they
    don't verify the output.

    """

    def testListIncrementsLocal(self):
        """Test --list-increments switch.  Assumes restoretest3 valid rd dir"""
        rdiff_backup(True,
                     True,
                     Local.backup3rp.path,
                     None,
                     extra_options=b'--list-increments')

    def testListIncrementsRemote(self):
        """Test --list-increments mode remotely.  Uses restoretest3"""
        rdiff_backup(False,
                     True,
                     Local.backup3rp.path,
                     None,
                     extra_options=b'--list-increments')

    def testListChangeSinceLocal(self):
        """Test --list-changed-since mode locally.  Uses restoretest3"""
        rdiff_backup(True,
                     True,
                     Local.backup3rp.path,
                     None,
                     extra_options=b'--list-changed-since 10000')
        rdiff_backup(True,
                     True,
                     Local.backup3rp.path,
                     None,
                     extra_options=b'--list-changed-since 2B')

    def testListChangeSinceRemote(self):
        """Test --list-changed-since mode remotely.  Uses restoretest3"""
        rdiff_backup(False,
                     True,
                     Local.backup3rp.path,
                     None,
                     extra_options=b'--list-changed-since 10000')

    def testListAtTimeLocal(self):
        """Test --list-at-time mode locally.  Uses restoretest3"""
        rdiff_backup(True,
                     True,
                     Local.backup3rp.path,
                     None,
                     extra_options=b'--list-at-time 20000')

    def testListAtTimeRemote(self):
        """Test --list-at-time mode locally.  Uses restoretest3"""
        rdiff_backup(False,
                     True,
                     Local.backup3rp.path,
                     None,
                     extra_options=b'--list-at-time 20000')

    def testListIncrementSizesLocal(self):
        """Test --list-increment-sizes switch.  Uses restoretest3"""
        rdiff_backup(True,
                     True,
                     Local.backup3rp.path,
                     None,
                     extra_options=b'--list-increment-sizes')

    def testListIncrementSizesRemote(self):
        """Test --list-increment-sizes switch.  Uses restoretest3"""
        rdiff_backup(False,
                     True,
                     Local.backup3rp.path,
                     None,
                     extra_options=b'--list-increment-sizes')

    def get_all_increments(self, rp):
        """Iterate all increments at or below given directory"""
        self.assertTrue(rp.isdir())
        dirlist = rp.listdir()
        dirlist.sort()
        for filename in dirlist:
            subrp = rp.append(filename)
            if subrp.isincfile():
                yield subrp
            elif subrp.isdir():
                for subsubrp in self.get_all_increments(subrp):
                    yield subsubrp

    def testRemoveOlderThan(self):
        """Test --remove-older-than.  Uses restoretest3"""
        Myrm(Local.rpout.path)
        xcopytree(Local.backup3rp.path, Local.rpout.path)
        rdiff_backup(True,
                     True,
                     Local.rpout.path,
                     None,
                     extra_options=b"--remove-older-than 20000")
        rbdir = Local.rpout.append("rdiff-backup-data")
        for inc in self.get_all_increments(rbdir):
            self.assertGreaterEqual(inc.getinctime(), 20000)

    def testRemoveOlderThan2(self):
        """Test --remove-older-than, but '1B'.  Uses restoretest3"""
        Myrm(Local.rpout.path)
        xcopytree(Local.backup3rp.path, Local.rpout.path)
        rdiff_backup(True,
                     True,
                     Local.rpout.path,
                     None,
                     extra_options=b"--remove-older-than 1B --force")
        rbdir = Local.rpout.append("rdiff-backup-data")
        for inc in self.get_all_increments(rbdir):
            self.assertGreaterEqual(inc.getinctime(), 30000)

    def testRemoveOlderThanCurrent(self):
        """Make sure --remove-older-than doesn't delete current incs"""
        Myrm(Local.rpout.path)
        xcopytree(Local.backup3rp.path, Local.rpout.path)
        rdiff_backup(True,
                     True,
                     Local.rpout.path,
                     None,
                     extra_options=b"--remove-older-than now --force")
        rbdir = Local.rpout.append("rdiff-backup-data")

        has_cur_mirror, has_metadata = 0, 0
        for inc in self.get_all_increments(rbdir):
            if inc.getincbase().index[-1] == b'current_mirror':
                has_cur_mirror = 1
            elif inc.getincbase().index[-1] == b'mirror_metadata':
                has_metadata = 1
        self.assertTrue(has_cur_mirror)
        self.assertTrue(has_metadata)

    def testRemoveOlderThanQuoting(self):
        """Test --remove-older-than when dest directory is quoted"""
        Myrm(Local.rpout.path)
        rdiff_backup(True,
                     True,
                     Local.inc1rp.path,
                     Local.rpout.path,
                     extra_options=b"--override-chars-to-quote '^a-z0-9_ -.'"
                     b" --current-time 10000")
        rdiff_backup(True,
                     True,
                     Local.inc2rp.path,
                     Local.rpout.path,
                     extra_options=b"--override-chars-to-quote '^a-z0-9_ -.'"
                     b" --current-time 20000")
        rdiff_backup(True,
                     True,
                     Local.rpout.path,
                     None,
                     extra_options=b"--remove-older-than now")

    def testRemoveOlderThanRemote(self):
        """Test --remove-older-than remotely"""
        Myrm(Local.rpout.path)
        xcopytree(Local.backup3rp.path, Local.rpout.path)
        rdiff_backup(False,
                     True,
                     Local.rpout.path,
                     None,
                     extra_options=b"--remove-older-than 20000")
        rbdir = Local.rpout.append("rdiff-backup-data")
        for inc in self.get_all_increments(rbdir):
            self.assertGreaterEqual(inc.getinctime(), 20000)

    def testNonExistingTempDir(self):
        """Test that a missing tempdir is properly catched as an error"""
        Myrm(Local.rpout.path)
        rdiff_backup(True,
                     True,
                     Local.vftrp.path,
                     Local.rpout.path,
                     extra_options=b"--tempdir DoesSurelyNotExist",
                     expected_ret_code=Globals.RET_CODE_ERR)


class FinalSelection(PathSetter):
    """Test selection options"""

    def testSelLocal(self):
        """Quick backup testing a few selection options"""
        self.delete_tmpdirs()

        # create a few relative paths to check a different approach than absolute
        inc2_rel = os.path.relpath(Local.inc2rp.path)
        out_rel = os.path.relpath(Local.rpout.path)
        rest1_rel = os.path.relpath(Local.rpout1.path)

        # Test --include option
        rdiff_backup(
            True,
            True,
            inc2_rel,
            out_rel,
            extra_options=b"--current-time 10000 --include %b --exclude '**' " %
            os.path.join(inc2_rel, b"various_file_types"))

        # check that one included file exists and one excluded doesn't
        self.assertTrue(os.lstat(
            os.path.join(out_rel, b"various_file_types", b"regular_file")))
        self.assertRaises(OSError, os.lstat, os.path.join(out_rel, b"test.py"))

        # Now try reading list of files
        rdiff_backup(True,
                     True,
                     inc2_rel,
                     out_rel,
                     extra_options=b"--current-time 20000 --include-filelist-stdin --exclude '**' ",
                     input=b"\n%b\n%b" % (os.path.join(inc2_rel, b"test.py"),
                                          os.path.join(inc2_rel, b"changed_dir")))

        # check that two included files exist and two excluded don't
        self.assertTrue(os.lstat(os.path.join(out_rel, b"changed_dir")))
        self.assertTrue(os.lstat(os.path.join(out_rel, b"test.py")))
        self.assertRaises(OSError, os.lstat,
                          os.path.join(out_rel, b"various_file_types"))
        self.assertRaises(OSError, os.lstat,
                          os.path.join(out_rel, b"changed_dir", b"foo"))

        # Test selective restoring
        mirror_rp = rpath.RPath(Globals.local_connection, out_rel)
        restore_filename = get_increment_rp(mirror_rp, 10000).path

        rdiff_backup(
            True,
            True,
            restore_filename,
            rest1_rel,
            extra_options=b"--include-filelist-stdin --exclude '**' --restore",
            input=b"\n%b" % os.path.join(rest1_rel, b"various_file_types", b"regular_file"))

        self.assertTrue(os.lstat(
            os.path.join(rest1_rel, b"various_file_types", b"regular_file")))
        self.assertRaises(OSError, os.lstat,
                          os.path.join(rest1_rel, b"tester"))
        self.assertRaises(
            OSError, os.lstat,
            os.path.join(rest1_rel, b"various_file_types", b"executable"))

    def testSelFilesRemote(self):
        """Test for bug found in 0.7.[34] - filelist where source remote"""
        self.delete_tmpdirs()

        Local.vft_out.mkdir()
        # Make an exclude list
        excluderp = Local.vft_out.append("exclude")
        with excluderp.open("wb") as fp:
            fp.write(Local.vftrp.append('regular_file\n').path)
            fp.write(Local.vftrp.append('test\n').path)

        # Make an include list
        includerp = Local.vft_out.append("include")
        with includerp.open("wb") as fp:
            fp.write(Local.vftrp.append('executable\n').path)
            fp.write(Local.vftrp.append('symbolic_link\n').path)
            fp.write(Local.vftrp.append('regular_file\n').path)
            fp.write(Local.vftrp.append('test\n').path)

        rdiff_backup(False,
                     False,
                     Local.vftrp.path,
                     Local.rpout.path,
                     extra_options=b"--exclude-filelist %b --include-filelist %b"
                     b" --exclude '**'" % (excluderp.path, includerp.path))

        rdiff_backup(False,
                     False,
                     Local.rpout.path,
                     Local.rpout1.path,
                     extra_options=b"--restore-as-of now")
        self.assertTrue(os.lstat(Local.rpout1.append('executable').path))
        self.assertTrue(os.lstat(Local.rpout1.append('symbolic_link').path))
        self.assertRaises(OSError, os.lstat,
                          Local.rpout1.append('regular_file').path)
        self.assertRaises(OSError, os.lstat,
                          Local.rpout1.append('executable2').path)

    def testSelRestoreLocal(self):
        """Test selection options when restoring locally"""
        self.run_sel_restore_test(True, True)

    def testSelRestoreRemote(self):
        """Test selection options when both sides are remote"""
        self.run_sel_restore_test(False, False)

    def run_sel_restore_test(self, source_local, dest_local):
        """Test selection options with restore"""
        self.make_restore_sel_dir(source_local, dest_local)
        existing_file = self.make_restore_existing_target()
        file1_target = Local.rpout1.append("file1")
        file2_target = Local.rpout1.append("file2")
        excludes = (b"--exclude %b --exclude %b --force" %
                    (file1_target.path, existing_file.path))
        rdiff_backup(source_local,
                     dest_local,
                     Local.rpout.path,
                     Local.rpout1.path,
                     extra_options=b"--restore-as-of now " + excludes,
                     expected_ret_code=Globals.RET_CODE_WARN)
        for rp in (file1_target, file2_target, existing_file):
            rp.setdata()
        self.assertFalse(file1_target.lstat())
        self.assertTrue(file2_target.lstat())
        # excluded file shouldn't be deleted:
        self.assertTrue(existing_file.lstat())

    def make_restore_sel_dir(self, source_local, dest_local):
        """Create rdiff-backup repository at Local.rpout"""
        self.delete_tmpdirs()
        Local.vft_out.mkdir()
        rp1 = Local.vft_out.append("file1")
        rp2 = Local.vft_out.append("file2")
        rp1.touch()
        rp2.touch()
        rdiff_backup(source_local, dest_local, Local.vft_out.path,
                     Local.rpout.path)
        Myrm(Local.vft_out.path)

    def make_restore_existing_target(self):
        """Create an existing file in the restore target directory"""
        Local.rpout1.mkdir()
        existing_file = Local.rpout1.append("existing_file")
        existing_file.touch()
        return existing_file


class FinalCorrupt(PathSetter):
    """Test messing with things a bit and making sure they still work"""

    def make_dir(self):
        self.delete_tmpdirs()
        rp1 = Local.get_tgt_local_rp('final_deleted1')
        if rp1.lstat():
            Myrm(rp1.path)
        rp1.mkdir()
        rp1_1 = rp1.append('regfile')
        rp1_1.touch()
        rp1_2 = rp1.append('dir')
        rp1_2.mkdir()
        rp1_2_1 = rp1_2.append('regfile2')
        rp1_2_1.write_string('foo')

        rp2 = Local.get_tgt_local_rp('final_deleted2')
        if rp2.lstat():
            Myrm(rp2.path)
        xcopytree(rp1.path, rp2.path)
        rp2_2_1 = rp2.append('dir', 'regfile2')
        self.assertTrue(rp2_2_1.lstat())
        rp2_2_1.delete()
        rp2_2_1.touch()
        return rp1, rp1_2, rp2

    def test_dest_delete(self):
        """Test deleting a directory from the destination dir

        Obviously that directory can no longer be restored, but the
        rest of the files should be OK.  Just runs locally for now.

        """
        in_dir1, in_subdir, in_dir2 = self.make_dir()
        rdiff_backup(True,
                     True,
                     in_dir1.path,
                     Local.rpout.path,
                     current_time=10000)

        out_subdir = Local.rpout.append(in_subdir.index[-1])
        log.Log("Deleting {rp}".format(rp=out_subdir), 3)
        out_subdir.delete()
        rdiff_backup(True,
                     True,
                     Local.rpout.path,
                     Local.rpout1.path,
                     extra_options=b"--restore-as-of 10000")


class FinalBugs(PathSetter):
    """Test for specific bugs that have been reported"""

    def test_symlink_popple(self):
        """Test for Popple's symlink bug

        Earlier, certain symlinks could cause data loss in _source_
        directory when regressing.  See mailing lists around 4/2/05
        for more info.

        """
        self.delete_tmpdirs()

        # Make directories
        rp1 = Local.get_tgt_local_rp('sym_in1')
        if rp1.lstat():
            rp1.delete()
        rp1.mkdir()
        rp1_d = rp1.append('subdir')
        rp1_d.mkdir()
        rp1_d_f = rp1_d.append('file')
        rp1_d_f.touch()

        rp2 = Local.get_tgt_local_rp('sym_in2')
        if rp2.lstat():
            rp2.delete()
        rp2.mkdir()
        rp2_s = rp2.append('subdir')
        rp2_s.symlink("%s/%s" % (abs_test_dir, rp1_d.path))

        # Backup
        rdiff_backup(True,
                     True,
                     rp1.path,
                     Local.rpout.path,
                     current_time=10000)
        rdiff_backup(True,
                     True,
                     rp2.path,
                     Local.rpout.path,
                     current_time=20000)

        # Make failed backup
        rbdir = Local.rpout.append('rdiff-backup-data')
        curmir = rbdir.append('current_mirror.%s.data' %
                              (Time.timetostring(30000), ))
        curmir.touch()

        # Regress
        rdiff_backup(True,
                     True,
                     Local.rpout.path,
                     None,
                     current_time=30000,
                     extra_options=b'--check-destination-dir',
                     expected_ret_code=Globals.RET_CODE_WARN)

        # Check to see if file still there
        rp1_d_f.setdata()
        self.assertTrue(rp1_d_f.isreg())

    def test_CCPP_keyerror(self):
        """Test when no change until middle of a directory

        This tests CCPP, to make sure it isn't asked to provide rorps
        for indices that are out of the cache.

        """
        self.delete_tmpdirs()
        bigrp = Local.get_src_local_rp('bigdir')
        rdiff_backup(True, True, bigrp.path, Local.rpout.path)
        rp = bigrp.append('subdir3', 'subdir49', 'file49')
        self.assertTrue(rp.isreg())
        rp.touch()
        rdiff_backup(True, True, bigrp.path, Local.rpout.path)


if __name__ == "__main__":
    unittest.main()
