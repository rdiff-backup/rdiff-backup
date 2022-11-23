# Copyright 2003 Ben Escoto, 2021 Eric Lavarde
#
# This file is part of rdiff-backup.
#
# rdiff-backup is free software; you can redistribute it and/or modify
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.
#
# rdiff-backup is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with rdiff-backup; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA
"""Determine the capabilities of given file system

rdiff-backup needs to read and write to file systems with varying
abilities.  For instance, some file systems and not others have ACLs,
are case-sensitive, or can store ownership information.  The code in
this module tests the file system for various features, and returns an
FSAbilities object describing it.

"""

import errno
import os
from rdiff_backup import Globals, log, robust, selection, Time
from rdiffbackup.meta import acl_win  # FIXME there should be no dependency
from rdiffbackup.locations.map import filenames as map_filenames


class FSAbilities:
    """
    Store capabilities of given file system
    """
    extended_filenames = None  # True if filenames can have non-ASCII chars
    win_reserved_filenames = None  # True if filenames can't have ",*,: etc.
    case_sensitive = None  # True if "foobar" and "FoObAr" are different files
    ownership = None  # True if chown works on this filesystem
    acls = None  # True if access control lists supported
    eas = None  # True if extended attributes supported
    win_acls = None  # True if windows access control lists supported
    hardlinks = None  # True if hard linking supported
    fsync_dirs = None  # True if directories can be fsync'd
    dir_inc_perms = None  # True if regular files can have full permissions
    resource_forks = None  # True if system supports resource forks
    carbonfile = None  # True if Mac Carbon file data is supported.
    writable = None  # True if capabilities can be determined by writing
    high_perms = None  # True if suid etc perms are (read/write) supported
    escape_dos_devices = None
    # True if dos device files can't be created (e.g., aux, con, com1)
    escape_trailing_spaces = None
    # True if trailing spaces or periods at end of filenames aren't preserved
    symlink_perms = None  # True if symlink perms are affected by umask

    def __init__(self, root_rp, writable=True):
        """
        FSAbilities initializer.
        """
        assert root_rp.conn is Globals.local_connection, (
            "Action only foreseen locally and not over {conn}.".format(
                conn=root_rp.conn))
        self.root_rp = root_rp
        self.writable = writable
        if self.writable:
            self._init_readwrite()
        else:
            self._init_readonly()

    def __str__(self):
        """
        Return pretty printable version of file system abilities
        """
        s = ['-' * 65]

        def addline(desc, val_text):
            """Add description line to s"""
            s.append('  %s%s%s' % (desc, ' ' * (45 - len(desc)), val_text))

        def add_boolean_list(pair_list):
            """Add lines from list of (desc, boolean) pairs"""
            for desc, boolean in pair_list:
                if boolean:
                    val_text = 'On'
                elif boolean is None:
                    val_text = 'N/A'
                else:
                    val_text = 'Off'
                addline(desc, val_text)

        if self.writable:
            s.append("Detected abilities for read/write file system")
            add_boolean_list([
                ('Ownership changing', self.ownership),
                ('Hard linking', self.hardlinks),
                ('fsync() directories', self.fsync_dirs),
                ('Directory inc permissions', self.dir_inc_perms),
                ('High-bit permissions', self.high_perms),
                ('Symlink permissions', self.symlink_perms),
                ('Extended filenames', self.extended_filenames),
                ('Windows reserved filenames', self.win_reserved_filenames),
            ])
        else:
            s.append("Detected abilities for read-only file system")

        add_boolean_list(
            [('Access control lists', self.acls),
             ('Extended attributes', self.eas),
             ('Windows access control lists', self.win_acls),
             ('Case sensitivity', self.case_sensitive),
             ('Escape DOS devices', self.escape_dos_devices),
             ('Escape trailing spaces', self.escape_trailing_spaces),
             ('Mac OS X style resource forks', self.resource_forks),
             ('Mac OS X Finder information', self.carbonfile)])
        s.append(s[0])
        return '\n'.join(s)

    def _init_readonly(self):
        """
        Set variables using fs tested at RPath root_rp.

        This method does not write to the file system at all, and
        should be run on the file system when the file system will
        only need to be read.
        """
        self._detect_eas(self.root_rp, self.writable)
        self._detect_acls(self.root_rp)
        self._detect_win_acls(self.root_rp, self.writable)
        self._detect_resource_fork_readonly(self.root_rp)
        self._detect_carbonfile()
        self._detect_case_sensitive_readonly(self.root_rp)
        self._detect_escape_dos_devices(self.root_rp)
        self._detect_escape_trailing_spaces_readonly(self.root_rp)

    def _init_readwrite(self):
        """
        Set variables using fs tested at rp_base.  Run locally.

        This method creates a temp directory in rp_base and writes to
        it in order to test various features.  Use on a file system
        that will be written to.
        """
        if not self.root_rp.isdir():
            assert not self.root_rp.lstat(), (
                "Root path '{rp}' can't be writable, exist and not be "
                "a directory.".format(rp=self.root_rp))
            self.root_rp.mkdir()
        subdir = self.root_rp.get_temp_rpath()
        subdir.mkdir()

        self._detect_extended_filenames(subdir)
        self._detect_win_reserved_filenames(subdir)
        self._detect_case_sensitive_readwrite(subdir)
        self._detect_ownership(subdir)
        self._detect_hardlinks(subdir)
        self._detect_fsync_dirs(subdir)
        self._detect_eas(subdir, self.writable)
        self._detect_acls(subdir)
        self._detect_win_acls(subdir, self.writable)
        self._detect_dir_inc_perms(subdir)
        self._detect_resource_fork_readwrite(subdir)
        self._detect_carbonfile()
        self._detect_high_perms_readwrite(subdir)
        self._detect_symlink_perms(subdir)
        self._detect_escape_dos_devices(subdir)
        self._detect_escape_trailing_spaces_readwrite(subdir)

        subdir.delete()

    def _detect_ownership(self, testdir):
        """
        Set self.ownership to true if testdir's ownership can be changed
        """
        tmp_rp = testdir.append("foo")
        tmp_rp.touch()
        uid, gid = tmp_rp.getuidgid()
        try:  # just choose random uid/gid
            tmp_rp.chown(uid // 2 + 1, gid // 2 + 1)
            tmp_rp.chown(0, 0)
        except (OSError, AttributeError):
            self.ownership = False
        else:
            self.ownership = True
        tmp_rp.delete()

    def _detect_hardlinks(self, testdir):
        """
        Set self.hardlinks to true if hard linked files can be created
        """
        if not Globals.preserve_hardlinks:
            log.Log("Hard linking test skipped as rdiff-backup was started "
                    "with --no-hard-links option", log.INFO)
            self.hardlinks = None
            return
        hl_source = testdir.append("hardlinked_file1")
        hl_dir = testdir.append("hl")
        hl_dir.mkdir()
        hl_dest = hl_dir.append("hardlinked_file2")
        hl_source.touch()
        try:
            hl_dest.hardlink(hl_source.path)
            if hl_source.getinode() != hl_dest.getinode():
                raise OSError(errno.EOPNOTSUPP, "Hard links don't compare")
        except (OSError, AttributeError):
            log.Log("Hard linking not supported by filesystem at "
                    "path {pa}, hard links will be copied instead".format(
                        pa=self.root_rp), log.NOTE)
            self.hardlinks = False
        else:
            self.hardlinks = True

    def _detect_fsync_dirs(self, testdir):
        """
        Set self.fsync_dirs if directories can be fsync'd
        """
        try:
            testdir.fsync()
        except OSError:
            log.Log("Directories on file system at path {pa} are not "
                    "fsyncable. Assuming it's unnecessary.".format(pa=testdir),
                    log.INFO)
            self.fsync_dirs = False
        else:
            self.fsync_dirs = True

    def _detect_extended_filenames(self, subdir):
        """
        Set self.extended_filenames by trying to write a path
        """
        assert self.writable, "Detection method can only work read-write."

        # Make sure ordinary filenames ok
        try:
            ordinary_filename = b'5-_ a.snapshot.gz'
            ord_rp = subdir.append(ordinary_filename)
            ord_rp.touch()
            ord_rp.delete()
        except OSError as exc:
            log.Log.FatalError(
                "File with normal name '{nn}' couldn't be created, "
                "and failed with exception '{ex}'.".format(nn=ord_rp, ex=exc))

        # Try path with UTF-8 encoded character
        extended_filename = (
            'uni' + chr(225) + chr(132) + chr(137)).encode('utf-8')
        ext_rp = None
        try:
            ext_rp = subdir.append(extended_filename)
            ext_rp.touch()
        except OSError:
            if ext_rp and ext_rp.lstat():
                ext_rp.delete()  # just to be very sure
            self.extended_filenames = False
        else:
            try:
                ext_rp.delete()
            except OSError:
                # Broken CIFS setups will sometimes create UTF-8 files
                # and even stat them, but not let us perform file operations
                # on them. Test file cannot be deleted. UTF-8 chars not in the
                # underlying codepage get translated to '?'
                log.Log.FatalError(
                    "Could not delete extended filenames test file {tf}. "
                    "If you are using a CIFS share, please see the FAQ entry "
                    "about characters being transformed to a '?'".format(
                        tf=ext_rp))
            self.extended_filenames = True

    def _detect_win_reserved_filenames(self, subdir):
        """
        Set self.win_reserved_filenames by trying to write a path
        """
        assert self.writable, "Detection method can only work read-write."

        # Try Windows reserved characters
        win_reserved_filename = ':\\"'
        win_rp = None
        try:
            win_rp = subdir.append(win_reserved_filename)
            win_rp.touch()
        except OSError:
            if win_rp and win_rp.lstat():
                win_rp.delete()  # just to be very sure
            self.win_reserved_filenames = True
        else:
            try:
                win_rp.delete()
            except OSError:
                self.win_reserved_filenames = True
            else:
                self.win_reserved_filenames = False

    def _detect_acls(self, rp):
        """
        Set self.acls based on rp.

        Does not write. Needs to be local
        """
        if not Globals.acls_active:
            log.Log("POSIX ACLs test skipped as rdiff-backup was started "
                    "with --no-acls option", log.INFO)
            self.acls = None
            return

        try:
            import posix1e
        except ImportError:
            log.Log("Unable to import module posix1e from pylibacl package. "
                    "POSIX ACLs not supported on filesystem at "
                    "path {pa}".format(pa=rp), log.INFO)
            self.acls = False
            return

        try:
            posix1e.ACL(file=rp.path)
        except OSError as exc:
            log.Log("POSIX ACLs not supported by filesystem at path {pa} "
                    "due to exception '{ex}'".format(pa=rp, ex=exc), log.INFO)
            self.acls = False
        else:
            self.acls = True

    def _detect_case_sensitive_readwrite(self, subdir):
        """
        Determine if directory at rp is case sensitive by writing
        """
        assert self.writable, "Detection method can only work read-write."
        upper_a = subdir.append("A")
        upper_a.touch()
        lower_a = subdir.append("a")
        if lower_a.lstat():
            lower_a.delete()
            upper_a.setdata()
            if upper_a.lstat():
                # we know that (fuse-)exFAT 1.3.0 takes 1sec to register the
                # deletion (July 2020)
                log.Log.FatalError(
                    "We're sorry but the target file system at path '{pa}' "
                    "isn't deemed reliable enough for a backup. "
                    "It takes too long or doesn't register case insensitive "
                    "deletion of files.".format(pa=subdir))
            self.case_sensitive = False
        else:
            upper_a.delete()
            self.case_sensitive = True

    def _detect_case_sensitive_readonly(self, rp):
        """
        Determine if directory at rp is case sensitive without writing
        """

        def find_letter(subdir):
            """
            Find a (subdir_rp, dirlist) with a letter in it, or None

            Recurse down the directory, looking for any file that has
            a letter in it.  Return the pair (rp, [list of filenames])
            where the list is of the directory containing rp.
            """
            files_list = robust.listrp(subdir)
            for filename in files_list:
                file_rp = subdir.append(filename)
                if filename != filename.swapcase():
                    return (subdir, files_list, filename)
                elif file_rp.isdir():
                    subsearch = find_letter(file_rp)
                    if subsearch:
                        return subsearch
            return None

        def test_triple(dir_rp, dirlist, filename):
            """
            Return 1 if filename shows that file system is case sensitive,
            else 0
            """
            # TODO move check + lstat to find_letter
            swapped = filename.swapcase()
            if swapped in dirlist:
                return True

            swapped_rp = dir_rp.append(swapped)
            if swapped_rp.lstat():
                return False
            return True

        triple = find_letter(rp)
        if not triple:
            log.Log(
                "Could not determine case sensitivity of source directory {sd} "
                "because we can't find any files with letters in them. "
                "It will be treated as case sensitive: unnecessary but "
                "harmless quoting of capital letters might happen if the "
                "target repository is case insensitive".format(sd=rp), log.NOTE)
            self.case_sensitive = True
            return

        self.case_sensitive = test_triple(*triple)

    def _detect_eas(self, rp, write):
        """
        Set extended attributes from rp. Tests writing if write is true.
        """
        assert rp.conn is Globals.local_connection, (
            "Action only foreseen locally and not over {conn}.".format(
                conn=rp.conn))
        assert rp.lstat(), "Path '{rp}' must exist to test EAs.".format(rp=rp)
        if not Globals.eas_active:
            log.Log("Extended attributes test skipped as rdiff-backup was "
                    "started with --no-eas option", log.INFO)
            self.eas = None
            return
        try:
            import xattr.pyxattr_compat as xattr
        except ImportError:
            try:
                import xattr
            except ImportError:
                log.Log(
                    "Unable to import module (py)xattr. Extended attributes "
                    "not supported on filesystem at path {pa}".format(pa=rp),
                    log.INFO)
                self.eas = False
                return

        test_ea = b"test val"
        try:
            xattr.list(rp.path)
            if write:
                xattr.set(rp.path, b"user.test", test_ea)
                read_ea = xattr.get(rp.path, b"user.test")
                xattr.remove(rp.path, b"user.test")
        except OSError as exc:
            log.Log("Extended attributes not supported by filesystem at "
                    "path {pa} due to exception '{ex}'".format(pa=rp, ex=exc),
                    log.NOTE)
            self.eas = False
        else:
            if write and read_ea != test_ea:
                log.Log(
                    "Extended attributes support is broken on filesystem at "
                    "path {pa}. Please upgrade the filesystem driver, contact "
                    "the developers, or use the --no-eas option to disable "
                    "extended attributes support and suppress this "
                    "message".format(pa=rp), log.WARNING)
                self.eas = False
            else:
                self.eas = True

    def _detect_win_acls(self, dir_rp, write):
        """
        Test if windows access control lists are supported
        """
        assert dir_rp.conn is Globals.local_connection, (
            "Action only foreseen locally and not over {conn}.".format(
                conn=dir_rp.conn))
        assert dir_rp.lstat(), "Path '{rp}' must exist to test ACLs.".format(
            rp=dir_rp)
        if not Globals.win_acls_active:
            log.Log("Windows ACLs test skipped as rdiff-backup was started "
                    "with --no-acls option", log.INFO)
            self.win_acls = None
            return

        try:
            import win32security
            import pywintypes
        except ImportError:
            log.Log("Unable to import win32security module. Windows ACLs not "
                    "supported by filesystem at path {pa}".format(pa=dir_rp),
                    log.INFO)
            self.win_acls = False
            return
        try:
            sd = win32security.GetNamedSecurityInfo(
                os.fsdecode(dir_rp.path), win32security.SE_FILE_OBJECT,
                win32security.OWNER_SECURITY_INFORMATION
                | win32security.GROUP_SECURITY_INFORMATION
                | win32security.DACL_SECURITY_INFORMATION)
            acl = sd.GetSecurityDescriptorDacl()
            acl.GetAceCount()  # to verify that it works
            if write:
                win32security.SetNamedSecurityInfo(
                    os.fsdecode(dir_rp.path), win32security.SE_FILE_OBJECT,
                    win32security.OWNER_SECURITY_INFORMATION
                    | win32security.GROUP_SECURITY_INFORMATION
                    | win32security.DACL_SECURITY_INFORMATION,
                    sd.GetSecurityDescriptorOwner(),
                    sd.GetSecurityDescriptorGroup(),
                    sd.GetSecurityDescriptorDacl(), None)
        except (OSError, AttributeError, pywintypes.error):
            log.Log("Unable to load a Windows ACL. Windows ACLs not supported "
                    "by filesystem at path {pa}".format(pa=dir_rp), log.INFO)
            self.win_acls = False
            return

        try:
            acl_win.init_acls()  # FIXME there should be no cross-dependency
        except (OSError, AttributeError, pywintypes.error):
            log.Log("Unable to init win_acls. Windows ACLs not supported by "
                    "filesystem at path {pa}".format(pa=dir_rp), log.INFO)
            self.win_acls = False
            return
        self.win_acls = True

    def _detect_dir_inc_perms(self, rp):
        """
        See if increments can have full permissions like a directory
        """
        test_rp = rp.append('dir_inc_check')
        test_rp.touch()
        try:
            test_rp.chmod(0o7777, 4)
        except OSError:
            test_rp.delete()
            self.dir_inc_perms = False
            return
        test_rp.setdata()
        if test_rp.getperms() == 0o7777 or test_rp.getperms() == 0o6777:
            self.dir_inc_perms = True
        else:
            self.dir_inc_perms = False
        test_rp.delete()

    def _detect_carbonfile(self):
        """
        Test for support of the Mac Carbon library.

        This library can be used to obtain Finder info (creator/type).
        """
        try:
            import Carbon.File
        except (ImportError, AttributeError):
            self.carbonfile = False
            return

        try:
            Carbon.File.FSSpec('.')  # just to verify that it works
        except BaseException:
            self.carbonfile = False
            return

        self.carbonfile = True

    def _detect_resource_fork_readwrite(self, dir_rp):
        """
        Test for resource forks by writing to regular_file/..namedfork/rsrc
        """
        assert dir_rp.conn is Globals.local_connection, (
            "Action only foreseen locally and not over {conn}.".format(
                conn=dir_rp.conn))
        reg_rp = dir_rp.append('regfile')
        reg_rp.touch()

        s = b'test string---this should end up in resource fork'
        try:
            fp_write = open(
                os.path.join(reg_rp.path, b'..namedfork', b'rsrc'), 'wb')
            fp_write.write(s)
            fp_write.close()

            fp_read = open(
                os.path.join(reg_rp.path, b'..namedfork', b'rsrc'), 'rb')
            s_back = fp_read.read()
            fp_read.close()
        except OSError:
            self.resource_forks = False
        else:
            self.resource_forks = (s_back == s)
        reg_rp.delete()

    def _detect_resource_fork_readonly(self, dir_rp):
        """
        Test for resource fork support by testing an regular file

        Launches search for regular file in given directory.  If no
        regular file is found, resource_fork support will be turned
        off by default.
        """
        for rp in selection.Select(dir_rp).get_select_iter():
            if rp.isreg():
                try:
                    rfork = rp.append(b'..namedfork', b'rsrc')
                    fp = rfork.open('rb')
                    fp.read()
                    fp.close()
                except OSError:
                    self.resource_forks = False
                    return
                self.resource_forks = True
                return
        self.resource_forks = False

    def _detect_high_perms_readwrite(self, dir_rp):
        """
        Test for writing high-bit permissions like suid
        """
        tmpf_rp = dir_rp.append(b"high_perms_file")
        tmpf_rp.touch()
        tmpd_rp = dir_rp.append(b"high_perms_dir")
        tmpd_rp.touch()
        try:
            tmpf_rp.chmod(0o7000, 4)
            tmpf_rp.chmod(0o7777, 4)
            tmpd_rp.chmod(0o7000, 4)
            tmpd_rp.chmod(0o7777, 4)
        except OSError:
            self.high_perms = False
        else:
            self.high_perms = True
        tmpf_rp.delete()
        tmpd_rp.delete()

    def _detect_symlink_perms(self, dir_rp):
        """Test if symlink permissions are affected by umask"""
        sym_source = dir_rp.append(b"symlinked_file1")
        sym_source.touch()
        sym_dest = dir_rp.append(b"symlinked_file2")
        try:
            sym_dest.symlink(b"symlinked_file1")
        except (OSError, AttributeError):
            self.symlink_perms = False
        else:
            if sym_dest.getperms() == 0o700:
                self.symlink_perms = True
            else:
                self.symlink_perms = False
            sym_dest.delete()
        sym_source.delete()

    def _detect_escape_dos_devices(self, subdir):
        """Test if DOS device files can be used as filenames.

        This test must detect if the underlying OS is Windows, whether we are
        running under Cygwin or natively. Cygwin allows these special files to
        be stat'd from any directory. Native Windows returns OSError (like
        non-Cygwin POSIX), but we can check for that using os.name.

        Note that 'con' and 'aux' have some unusual behaviors as shown below.

        os.lstat()   |  con         aux         prn
        -------------+-------------------------------------
        Unix         |  OSError,2   OSError,2   OSError,2
        Cygwin/NTFS  |  -success-   -success-   -success-
        Cygwin/FAT32 |  -success-   -HANGS-
        Native Win   |  WinError,2  WinError,87 WinError,87
        """
        if os.name == "nt":
            self.escape_dos_devices = True
            return

        try:
            device_rp = subdir.append(b"con")
            if device_rp.lstat():
                self.escape_dos_devices = True
            else:
                self.escape_dos_devices = False
        except (OSError):
            self.escape_dos_devices = True

    def _detect_escape_trailing_spaces_readwrite(self, testdir):
        """
        Windows and Linux/FAT32 will not preserve trailing spaces or periods.
        Linux/FAT32 behaves inconsistently: It will give an OSError,22 if
        os.mkdir() is called on a directory name with a space at the end, but
        will give an OSError("invalid mode") if you attempt to create a filename
        with a space at the end. However, if a period is placed at the end of
        the name, Linux/FAT32 is consistent with Cygwin and Native Windows.
        """

        period_rp = testdir.append("foo.")
        if period_rp.lstat():
            log.Log.FatalError(
                "Test file '{tf}' already exists where it shouldn't, something "
                "is very wrong with your file system".format(tf=period_rp))

        tmp_rp = testdir.append("foo")
        tmp_rp.touch()
        if not tmp_rp.lstat():
            log.Log.FatalError(
                "Test file '{tf}' doesn't exist even though it's been created, "
                "something is very wrong with your file system".format(
                    tf=tmp_rp))

        period_rp.setdata()
        # either the foo and foo. files are the same, or foo. can't be created,
        # in both cases, we need to escape trailing blanks/periods.
        if period_rp.lstat():
            self.escape_trailing_spaces = True
        else:
            try:
                period_rp.touch()
                if period_rp.lstat():
                    self.escape_trailing_spaces = False
                else:
                    self.escape_trailing_spaces = True
            except (OSError):
                self.escape_trailing_spaces = True

        tmp_rp.delete()

    def _detect_escape_trailing_spaces_readonly(self, rp):
        """Determine if directory at rp permits filenames with trailing
        spaces or periods without writing."""

        # we check one file after the other in the given directory
        dirlist = robust.listrp(rp)
        for filename in dirlist:
            try:
                test_rp = rp.append(filename)
            except OSError:
                continue  # file is not fit for tests
            if not test_rp.lstat():
                continue  # file is not fit for tests
            if filename.endswith(b".") or filename.endswith(b" "):
                self.escape_trailing_spaces = False
                return
            # we test only periods and assume the same result for spaces
            period = filename + b'.'
            if period in dirlist:
                self.escape_trailing_spaces = False
                return
            try:
                period_rp = rp.append(period)
            except OSError:
                continue  # file is not fit for tests
            if period_rp.lstat():
                self.escape_trailing_spaces = True
                return

        # no file could be found to do any test
        log.Log("Could not determine if source directory {sd} permits "
                "trailing spaces or periods in filenames because we can't "
                "find any files with trailing dot/period. "
                "It will be treated as permitting such files, but none will "
                "exist if it doesn't, so it doesn't really matter and is "
                "harmless".format(sd=rp), log.INFO)
        self.escape_trailing_spaces = False


class SetGlobals:
    """
    Various functions for setting Globals vars given FSAbilities object(s)

    Factually it is an abstract class and shan't be instantiated but only
    derived.
    """

    def __init__(self, src_loc, dest_loc):
        """Just store some variables for use below"""
        self.in_conn = src_loc.base_dir.conn
        self.out_conn = dest_loc.base_dir.conn
        self.src_fsa = src_loc.fs_abilities
        self.dest_fsa = dest_loc.fs_abilities
        self.src_loc = src_loc
        self.dest_loc = dest_loc

    def set_eas(self):
        self._update_triple(self.src_fsa.eas, self.dest_fsa.eas,
                            ('eas_active', 'eas_write', 'eas_conn'))

    def set_acls(self):
        self._update_triple(self.src_fsa.acls, self.dest_fsa.acls,
                            ('acls_active', 'acls_write', 'acls_conn'))
        if Globals.never_drop_acls and not Globals.acls_active:
            log.Log.FatalError("--never-drop-acls specified, but ACL support "
                               "missing from source filesystem")

    def set_win_acls(self):
        self._update_triple(
            self.src_fsa.win_acls, self.dest_fsa.win_acls,
            ('win_acls_active', 'win_acls_write', 'win_acls_conn'))

    def set_resource_forks(self):
        self._update_triple(
            self.src_fsa.resource_forks, self.dest_fsa.resource_forks,
            ('resource_forks_active', 'resource_forks_write',
             'resource_forks_conn'))

    def set_carbonfile(self):
        self._update_triple(
            self.src_fsa.carbonfile, self.dest_fsa.carbonfile,
            ('carbonfile_active', 'carbonfile_write', 'carbonfile_conn'))

    def set_hardlinks(self):
        if Globals.preserve_hardlinks != 0:
            Globals.set_all('preserve_hardlinks', self.dest_fsa.hardlinks)

    def set_fsync_directories(self):
        Globals.set_all('fsync_directories', self.dest_fsa.fsync_dirs)

    def set_change_ownership(self):
        Globals.set_all('change_ownership', self.dest_fsa.ownership)

    def set_high_perms(self):
        if not self.dest_fsa.high_perms:
            Globals.set_all('permission_mask', 0o777)

    def set_symlink_perms(self):
        Globals.set_all('symlink_perms', self.dest_fsa.symlink_perms)

    def set_compatible_timestamps(self):
        if Globals.chars_to_quote.find(b":") > -1:
            Globals.set_all('use_compatible_timestamps', 1)
            # Update the current time string to new timestamp format
            Time.set_current_time(Time.getcurtime())
            log.Log("Enabled use_compatible_timestamps", log.INFO)


class Dir2RepoSetGlobals(SetGlobals):
    """
    Functions for setting fsa related globals for backup session
    """

    def __init__(self, src_dir, dest_repo):
        """Just store some variables for use below"""
        super().__init__(src_dir, dest_repo)
        self.repo = dest_repo

    def __call__(self):
        """
        Given rps for source filesystem and repository, set fsa globals
        """
        self.set_eas()
        self.set_acls()
        self.set_win_acls()
        self.set_resource_forks()
        self.set_carbonfile()
        self.set_hardlinks()
        self.set_fsync_directories()
        self.set_change_ownership()
        self.set_high_perms()
        self.set_symlink_perms()
        self.set_chars_to_quote(self.repo)
        self.set_special_escapes(self.repo)
        self.set_compatible_timestamps()

        return Globals.RET_CODE_OK

    def set_special_escapes(self, repo):
        """
        Escaping DOS devices and trailing periods/spaces works like
        regular filename escaping.

        If only the destination requires it, then we do it.
        Otherwise, it is not necessary, since the files
        couldn't have been created in the first place. We also record
        whether we have done it in order to handle the case where a
        volume which was escaped is later restored by an OS that does
        not require it.
        """

        suggested_edd = (self.dest_fsa.escape_dos_devices
                         and not self.src_fsa.escape_dos_devices)
        suggested_ets = (self.dest_fsa.escape_trailing_spaces
                         and not self.src_fsa.escape_trailing_spaces)

        se = repo.get_special_escapes()
        if se is None:
            actual_edd, actual_ets = suggested_edd, suggested_ets
            se = set()
            if actual_edd:
                se.add("escape_dos_devices")
            if actual_ets:
                se.add("escape_trailing_spaces")
            repo.set_special_escapes(se)
        else:
            actual_edd = ("escape_dos_devices" in se)
            actual_ets = ("escape_trailing_spaces" in se)

            if actual_edd != suggested_edd and not suggested_edd:
                log.Log("System no longer needs DOS devices to be escaped, "
                        "but we will retain for backwards compatibility",
                        log.WARNING)
            if actual_ets != suggested_ets and not suggested_ets:
                log.Log(
                    "System no longer needs trailing spaces or periods to be "
                    "escaped, but we will retain for backwards compatibility",
                    log.WARNING)

        Globals.set_all('escape_dos_devices', actual_edd)
        log.Log("Backup: escape_dos_devices = {dd}".format(dd=actual_edd),
                log.INFO)

        Globals.set_all('escape_trailing_spaces', actual_ets)
        log.Log("Backup: escape_trailing_spaces = {ts}".format(ts=actual_ets),
                log.INFO)

    def set_chars_to_quote(self, repo):
        """
        Set chars_to_quote setting for backup session

        Unlike most other options, the chars_to_quote setting also
        depends on the current settings in the rdiff-backup-data
        directory, not just the current fs features.
        """
        ctq = self._compare_ctq_file(repo, self._get_ctq_from_fsas())
        regexp, unregexp = map_filenames.get_quoting_regexps(
            ctq, Globals.quoting_char)

        Globals.set_all('chars_to_quote', ctq)
        Globals.set_all('chars_to_quote_regexp', regexp)
        Globals.set_all('chars_to_quote_unregexp', unregexp)

    def _update_triple(self, src_support, dest_support, attr_triple):
        """
        Many of the settings have a common form we can handle here
        """
        active_attr, write_attr, conn_attr = attr_triple
        if Globals.get(active_attr) == 0:
            return  # don't override 0
        for attr in attr_triple:
            Globals.set_all(attr, None)
        if not src_support:
            return  # if source doesn't support, nothing
        Globals.set_all(active_attr, 1)
        self.in_conn.Globals.set_local(conn_attr, 1)
        if dest_support:
            Globals.set_all(write_attr, 1)
            self.out_conn.Globals.set_local(conn_attr, 1)

    def _get_ctq_from_fsas(self):
        """
        Determine chars_to_quote just from filesystems, no ctq file
        """
        ctq = []

        if self.src_fsa.case_sensitive and not self.dest_fsa.case_sensitive:
            ctq.append(b"A-Z")  # Quote upper case
        # on a read-only file system, the variable would be None, to be ignored
        if self.dest_fsa.extended_filenames is False:
            ctq.append(b'\000-\037')  # Quote 0 - 31
            ctq.append(b'\200-\377')  # Quote non-ASCII characters 0x80 - 0xFF
        if self.dest_fsa.win_reserved_filenames:
            if self.dest_fsa.extended_filenames:
                ctq.append(b'\000-\037')  # Quote 0 - 31
            # Quote ", *, /, :, <, >, ?, \, |, and 127 (DEL)
            ctq.append(b'\"*/:<>?\\\\|\177')

        # Quote quoting char if quoting anything
        if ctq:
            ctq.append(Globals.quoting_char)
        return b"".join(ctq)

    def _compare_ctq_file(self, repo, suggested_ctq):
        """
        Compare chars_to_quote previous, enforced and suggested

        Returns the actual chars_to_quote string to be used
        """
        previous_ctq = repo.get_chars_to_quote()
        if previous_ctq is None:  # there was no previous chars_to_quote
            if Globals.chars_to_quote is None:
                actual_ctq = suggested_ctq
            else:
                actual_ctq = Globals.chars_to_quote
                if actual_ctq != suggested_ctq:
                    log.Log("File system at '{fs}' suggested quoting '{sq}' "
                            "but override quoting '{oq}' will be used. "
                            "Assuming you know what you are doing".format(
                                fs=repo, sq=suggested_ctq, oq=actual_ctq),
                            log.NOTE)
            repo.set_chars_to_quote(actual_ctq)
            return actual_ctq

        if Globals.chars_to_quote is None:
            if suggested_ctq and suggested_ctq != previous_ctq:
                # the file system has new specific requirements
                actual_ctq = suggested_ctq
            else:
                actual_ctq = previous_ctq
                if previous_ctq and not suggested_ctq:
                    log.Log("File system at '{fs}' no longer needs quoting "
                            "but we will retain for backwards "
                            "compatibility".format(fs=repo), log.NOTE)
        else:
            actual_ctq = Globals.chars_to_quote  # Globals override
            if actual_ctq != suggested_ctq:
                log.Log("File system at '{fs}' suggested quoting '{sq}' "
                        "but override quoting '{oq}' will be used. "
                        "Assuming you know what you are doing".format(
                            fs=repo, sq=suggested_ctq, oq=actual_ctq),
                        log.NOTE)

        # the quoting didn't change so all is good
        if actual_ctq == previous_ctq:
            return actual_ctq
        else:
            log.Log.FatalError(
                "The repository quoting '{rq}' would need to be migrated from "
                "old quoting chars '{oq}' to new quoting chars '{nq}'. "
                "This may mean that the repository has been moved between "
                "different file systems, and isn't supported".format(
                    rq=repo, oq=previous_ctq, nq=actual_ctq))


class Repo2DirSetGlobals(SetGlobals):
    """
    Functions for setting fsa-related globals for restore session
    """

    def __init__(self, src_repo, dest_dir):
        """Just store some variables for use below"""
        super().__init__(src_repo, dest_dir)
        self.repo = src_repo

    def __call__(self):
        """
        `Set fsa related globals for restore session, given in/out rps
        """
        self.set_eas()
        self.set_acls()
        self.set_win_acls()
        self.set_resource_forks()
        self.set_carbonfile()
        self.set_hardlinks()
        # No need to fsync anything when restoring
        self.set_change_ownership()
        self.set_high_perms()
        self.set_symlink_perms()
        self.set_chars_to_quote(self.repo)
        self.set_special_escapes(self.repo)
        self.set_compatible_timestamps()

        return Globals.RET_CODE_OK

    def set_special_escapes(self, repo):
        """
        Set escape_dos_devices and escape_trailing_spaces from
        rdiff-backup-data dir, just like chars_to_quote
        """
        se = repo.get_special_escapes()
        if se is not None:
            actual_edd = ("escape_dos_devices" in se)
            actual_ets = ("escape_trailing_spaces" in se)
        else:
            if getattr(self, "src_fsa", None) is not None:
                actual_edd = (self.src_fsa.escape_dos_devices
                              and not self.dest_fsa.escape_dos_devices)
                actual_ets = (self.src_fsa.escape_trailing_spaces
                              and not self.dest_fsa.escape_trailing_spaces)
            else:
                # Single filesystem operation
                actual_edd = self.dest_fsa.escape_dos_devices
                actual_ets = self.dest_fsa.escape_trailing_spaces

        Globals.set_all('escape_dos_devices', actual_edd)
        log.Log("Backup: escape_dos_devices = {dd}".format(dd=actual_edd),
                log.INFO)

        Globals.set_all('escape_trailing_spaces', actual_ets)
        log.Log("Backup: escape_trailing_spaces = {ts}".format(ts=actual_ets),
                log.INFO)

    def set_chars_to_quote(self, repo):
        """
        Set chars_to_quote from rdiff-backup-data dir
        """
        if Globals.chars_to_quote is not None:
            return  # already overridden

        ctq = repo.get_chars_to_quote()
        if ctq is not None:
            regexp, unregexp = map_filenames.get_quoting_regexps(
                ctq, Globals.quoting_char)
            Globals.set_all("chars_to_quote", ctq)
            Globals.set_all('chars_to_quote_regexp', regexp)
            Globals.set_all('chars_to_quote_unregexp', unregexp)
        else:
            log.Log("chars_to_quote config not found, assuming no quoting "
                    "required in backup repository".format(),
                    log.WARNING)
            Globals.set_all("chars_to_quote", b"")

    def _update_triple(self, src_support, dest_support, attr_triple):
        """
        Update global settings for feature based on fsa results

        This is slightly different from Dir2RepoSetGlobals._update_triple
        because (using the mirror_metadata file) rpaths from the
        source may have more information than the file system
        supports.
        """
        active_attr, write_attr, conn_attr = attr_triple
        if Globals.get(active_attr) == 0:
            return  # don't override 0
        for attr in attr_triple:
            Globals.set_all(attr, None)
        if not dest_support:
            return  # if dest doesn't support, do nothing
        Globals.set_all(active_attr, 1)
        self.out_conn.Globals.set_local(conn_attr, 1)
        self.out_conn.Globals.set_local(write_attr, 1)
        if src_support:
            self.in_conn.Globals.set_local(conn_attr, 1)


class SingleRepoSetGlobals(Repo2DirSetGlobals):
    """
    For setting globals when dealing only with one filesystem
    """

    def __init__(self, repo):
        self.conn = repo.base_dir.conn
        self.dest_fsa = repo.fs_abilities
        self.repo = repo

    def __call__(self):
        """
        Set fsa related globals for operation on single filesystem
        """
        self.set_eas()
        self.set_acls()
        self.set_win_acls()
        self.set_resource_forks()
        self.set_carbonfile()
        if self.repo.must_be_writable:
            self.set_hardlinks()
            self.set_fsync_directories()  # especially needed for regression
            self.set_change_ownership()
            self.set_high_perms()
            self.set_symlink_perms()
        self.set_chars_to_quote(self.repo)
        self.set_special_escapes(self.repo)
        self.set_compatible_timestamps()

        return Globals.RET_CODE_OK

    def set_eas(self):
        self._update_triple(
            self.dest_fsa.eas, ('eas_active', 'eas_write', 'eas_conn'))

    def set_acls(self):
        self._update_triple(
            self.dest_fsa.acls, ('acls_active', 'acls_write', 'acls_conn'))

    def set_win_acls(self):
        self._update_triple(
            self.dest_fsa.win_acls,
            ('win_acls_active', 'win_acls_write', 'win_acls_conn'))

    def set_resource_forks(self):
        self._update_triple(
            self.dest_fsa.resource_forks,
            ('resource_forks_active', 'resource_forks_write',
             'resource_forks_conn'))

    def set_carbonfile(self):
        self._update_triple(
            self.dest_fsa.carbonfile,
            ('carbonfile_active', 'carbonfile_write', 'carbonfile_conn'))

    def _update_triple(self, fsa_support, attr_triple):
        """
        Update global vars from single fsa test
        """
        active_attr, write_attr, conn_attr = attr_triple
        if Globals.get(active_attr) == 0:
            return  # don't override 0
        for attr in attr_triple:
            Globals.set_all(attr, None)
        if not fsa_support:
            return
        Globals.set_all(active_attr, 1)
        Globals.set_all(write_attr, 1)
        self.conn.Globals.set_local(conn_attr, 1)
