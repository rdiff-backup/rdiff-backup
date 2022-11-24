# DEPRECATED compat200
# Copyright 2003 Ben Escoto
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
"""
Determine the capabilities of given file system

rdiff-backup needs to read and write to file systems with varying
abilities.  For instance, some file systems and not others have ACLs,
are case-sensitive, or can store ownership information.  The code in
this module tests the file system for various features, and returns an
FSAbilities object describing it.
"""

import errno
import os
from rdiff_backup import (
    FilenameMapping, Globals, log, robust, selection, Time
)
from rdiffbackup.meta import acl_win  # FIXME there should be no dependency


class FSAbilities:
    """Store capabilities of given file system"""
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
    name = None  # Short string, not used for any technical purpose
    read_only = None  # True if capabilities were determined non-destructively
    high_perms = None  # True if suid etc perms are (read/write) supported
    escape_dos_devices = None  # True if dos device files can't be created (e.g.,
    # aux, con, com1, etc)
    escape_trailing_spaces = None  # True if trailing spaces or periods at the
    # end of filenames aren't preserved
    symlink_perms = None  # True if symlink perms are affected by umask

    def __init__(self, name, root_rp, read_only=False):
        """FSAbilities initializer.  name is only used in logging"""
        assert root_rp.conn is Globals.local_connection, (
            "Action only foreseen locally and not over {conn}.".format(
                conn=root_rp.conn))
        self.name = name
        self.root_rp = root_rp
        self.read_only = read_only
        if self.read_only:
            self._init_readonly()
        else:
            self._init_readwrite()

    def __str__(self):
        """Return pretty printable version of self"""
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

        def get_title_line():
            """Add the first line, mostly for decoration"""
            read_string = self.read_only and "read only" or "read/write"
            if self.name:
                return ('Detected abilities for %s (%s) file system:' %
                        (self.name, read_string))
            else:
                return (
                    'Detected abilities for %s file system' % (read_string, ))

        s.append(get_title_line())
        if not self.read_only:
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
        """Set variables using fs tested at RPath root_rp.

        This method does not write to the file system at all, and
        should be run on the file system when the file system will
        only need to be read.

        Only self.acls and self.eas are set.

        """
        self._detect_eas(self.root_rp, not self.read_only)
        self._detect_acls(self.root_rp)
        self._detect_win_acls(self.root_rp, not self.read_only)
        self._detect_resource_fork_readonly(self.root_rp)
        self._detect_carbonfile()
        self._detect_case_sensitive_readonly(self.root_rp)
        self._detect_escape_dos_devices(self.root_rp)
        self._detect_escape_trailing_spaces_readonly(self.root_rp)

    def _init_readwrite(self):
        """Set variables using fs tested at rp_base.  Run locally.

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
        self._detect_eas(subdir, not self.read_only)
        self._detect_acls(subdir)
        self._detect_win_acls(subdir, not self.read_only)
        self._detect_dir_inc_perms(subdir)
        self._detect_resource_fork_readwrite(subdir)
        self._detect_carbonfile()
        self._detect_high_perms_readwrite(subdir)
        self._detect_symlink_perms(subdir)
        self._detect_escape_dos_devices(subdir)
        self._detect_escape_trailing_spaces_readwrite(subdir)

        subdir.delete()

    def _detect_ownership(self, testdir):
        """Set self.ownership to true iff testdir's ownership can be changed"""
        tmp_rp = testdir.append("foo")
        tmp_rp.touch()
        uid, gid = tmp_rp.getuidgid()
        try:
            tmp_rp.chown(uid // 2 + 1, gid // 2 + 1)  # just choose random uid/gid
            tmp_rp.chown(0, 0)
        except (OSError, AttributeError):
            self.ownership = 0
        else:
            self.ownership = 1
        tmp_rp.delete()

    def _detect_hardlinks(self, testdir):
        """Set self.hardlinks to true iff hard linked files can be made"""
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
            if Globals.preserve_hardlinks != 0:
                log.Log("Hard linking not supported by filesystem at "
                        "path {pa}, hard links will be copied instead".format(
                            pa=self.root_rp), log.NOTE)
            self.hardlinks = None
        else:
            self.hardlinks = 1

    def _detect_fsync_dirs(self, testdir):
        """Set self.fsync_dirs if directories can be fsync'd"""
        try:
            testdir.fsync()
        except OSError:
            log.Log("Directories on file system at path {pa} are not "
                    "fsyncable. Assuming it's unnecessary.".format(pa=testdir),
                    log.INFO)
            self.fsync_dirs = 0
        else:
            self.fsync_dirs = 1

    def _detect_extended_filenames(self, subdir):
        """Set self.extended_filenames by trying to write a path"""
        assert not self.read_only, "Detection method can only work read-write."

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
            self.extended_filenames = 0
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
            self.extended_filenames = 1

    def _detect_win_reserved_filenames(self, subdir):
        """Set self.win_reserved_filenames by trying to write a path"""
        assert not self.read_only, "Detection method can only work read-write."

        # Try Windows reserved characters
        win_reserved_filename = ':\\"'
        win_rp = None
        try:
            win_rp = subdir.append(win_reserved_filename)
            win_rp.touch()
        except OSError:
            if win_rp and win_rp.lstat():
                win_rp.delete()  # just to be very sure
            self.win_reserved_filenames = 1
        else:
            try:
                win_rp.delete()
            except OSError:
                self.win_reserved_filenames = 1
            else:
                self.win_reserved_filenames = 0

    def _detect_acls(self, rp):
        """Set self.acls based on rp.  Does not write.  Needs to be local"""
        if Globals.acls_active == 0:
            log.Log("POSIX ACLs test skipped as rdiff-backup was started "
                    "with --no-acls option", log.INFO)
            self.acls = 0
            return

        try:
            import posix1e
        except ImportError:
            log.Log("Unable to import module posix1e from pylibacl package. "
                    "POSIX ACLs not supported on filesystem at "
                    "path {pa}".format(pa=rp), log.INFO)
            self.acls = 0
            return

        try:
            posix1e.ACL(file=rp.path)
        except OSError as exc:
            log.Log("POSIX ACLs not supported by filesystem at path {pa} "
                    "due to exception '{ex}'".format(pa=rp, ex=exc), log.INFO)
            self.acls = 0
        else:
            self.acls = 1

    def _detect_case_sensitive_readwrite(self, subdir):
        """Determine if directory at rp is case sensitive by writing"""
        assert not self.read_only, "Detection method can only work read-write."
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
            self.case_sensitive = 0
        else:
            upper_a.delete()
            self.case_sensitive = 1

    def _detect_case_sensitive_readonly(self, rp):
        """Determine if directory at rp is case sensitive without writing"""

        def find_letter(subdir):
            """Find a (subdir_rp, dirlist) with a letter in it, or None

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
                return 1

            swapped_rp = dir_rp.append(swapped)
            if swapped_rp.lstat():
                return 0
            return 1

        triple = find_letter(rp)
        if not triple:
            log.Log(
                "Could not determine case sensitivity of source directory {sd} "
                "because we can't find any files with letters in them. "
                "It will be treated as case sensitive: unnecessary but "
                "harmless quoting of capital letters might happen if the "
                "target repository is case insensitive".format(sd=rp), log.NOTE)
            self.case_sensitive = 1
            return

        self.case_sensitive = test_triple(*triple)

    def _detect_eas(self, rp, write):
        """Set extended attributes from rp. Tests writing if write is true."""
        assert rp.conn is Globals.local_connection, (
            "Action only foreseen locally and not over {conn}.".format(
                conn=rp.conn))
        assert rp.lstat(), "Path '{rp}' must exist to test EAs.".format(rp=rp)
        if Globals.eas_active == 0:
            log.Log("Extended attributes test skipped as rdiff-backup was "
                    "started with --no-eas option", log.INFO)
            self.eas = 0
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
                self.eas = 0
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
            self.eas = 0
        else:
            if write and read_ea != test_ea:
                log.Log(
                    "Extended attributes support is broken on filesystem at "
                    "path {pa}. Please upgrade the filesystem driver, contact "
                    "the developers, or use the --no-eas option to disable "
                    "extended attributes support and suppress this "
                    "message".format(pa=rp), log.WARNING)
                self.eas = 0
            else:
                self.eas = 1

    def _detect_win_acls(self, dir_rp, write):
        """Test if windows access control lists are supported"""
        assert dir_rp.conn is Globals.local_connection, (
            "Action only foreseen locally and not over {conn}.".format(
                conn=dir_rp.conn))
        assert dir_rp.lstat(), "Path '{rp}' must exist to test ACLs.".format(
            rp=dir_rp)
        if Globals.win_acls_active == 0:
            log.Log("Windows ACLs test skipped as rdiff-backup was started "
                    "with --no-acls option", log.INFO)
            self.win_acls = 0
            return

        try:
            import win32security
            import pywintypes
        except ImportError:
            log.Log("Unable to import win32security module. Windows ACLs not "
                    "supported by filesystem at path {pa}".format(pa=dir_rp),
                    log.INFO)
            self.win_acls = 0
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
            self.win_acls = 0
            return

        try:
            acl_win.init_acls()  # FIXME there should be no cross-dependency
        except (OSError, AttributeError, pywintypes.error):
            log.Log("Unable to init win_acls. Windows ACLs not supported by "
                    "filesystem at path {pa}".format(pa=dir_rp), log.INFO)
            self.win_acls = 0
            return
        self.win_acls = 1

    def _detect_dir_inc_perms(self, rp):
        """See if increments can have full permissions like a directory"""
        test_rp = rp.append('dir_inc_check')
        test_rp.touch()
        try:
            test_rp.chmod(0o7777, 4)
        except OSError:
            test_rp.delete()
            self.dir_inc_perms = 0
            return
        test_rp.setdata()
        if test_rp.getperms() == 0o7777 or test_rp.getperms() == 0o6777:
            self.dir_inc_perms = 1
        else:
            self.dir_inc_perms = 0
        test_rp.delete()

    def _detect_carbonfile(self):
        """Test for support of the Mac Carbon library.  This library
        can be used to obtain Finder info (creator/type)."""
        try:
            import Carbon.File
        except (ImportError, AttributeError):
            self.carbonfile = 0
            return

        try:
            Carbon.File.FSSpec('.')  # just to verify that it works
        except BaseException:
            self.carbonfile = 0
            return

        self.carbonfile = 1

    def _detect_resource_fork_readwrite(self, dir_rp):
        """Test for resource forks by writing to regular_file/..namedfork/rsrc"""
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
            self.resource_forks = 0
        else:
            self.resource_forks = (s_back == s)
        reg_rp.delete()

    def _detect_resource_fork_readonly(self, dir_rp):
        """Test for resource fork support by testing an regular file

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
                    self.resource_forks = 0
                    return
                self.resource_forks = 1
                return
        self.resource_forks = 0

    def _detect_high_perms_readwrite(self, dir_rp):
        """Test for writing high-bit permissions like suid"""
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
            self.high_perms = 0
        else:
            self.high_perms = 1
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
            self.symlink_perms = 0
        else:
            if sym_dest.getperms() == 0o700:
                self.symlink_perms = 1
            else:
                self.symlink_perms = 0
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
            self.escape_dos_devices = 1
            return

        try:
            device_rp = subdir.append(b"con")
            if device_rp.lstat():
                self.escape_dos_devices = 1
            else:
                self.escape_dos_devices = 0
        except (OSError):
            self.escape_dos_devices = 1

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
            self.escape_trailing_spaces = 1
        else:
            try:
                period_rp.touch()
                if period_rp.lstat():
                    self.escape_trailing_spaces = 0
                else:
                    self.escape_trailing_spaces = 1
            except (OSError):
                self.escape_trailing_spaces = 1

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
                self.escape_trailing_spaces = 0
                return
            # we test only periods and assume the same result for spaces
            period = filename + b'.'
            if period in dirlist:
                self.escape_trailing_spaces = 0
                return
            try:
                period_rp = rp.append(period)
            except OSError:
                continue  # file is not fit for tests
            if period_rp.lstat():
                self.escape_trailing_spaces = 1
                return

        # no file could be found to do any test
        log.Log("Could not determine if source directory {sd} permits "
                "trailing spaces or periods in filenames because we can't "
                "find any files with trailing dot/period. "
                "It will be treated as permitting such files, but none will "
                "exist if it doesn't, so it doesn't really matter and is "
                "harmless".format(sd=rp), log.INFO)
        self.escape_trailing_spaces = 0


class SetGlobals:
    """Various functions for setting Globals vars given FSAbilities above

    Container for BackupSetGlobals and RestoreSetGlobals (don't use directly)

    """

    def __init__(self, in_conn, out_conn, src_fsa, dest_fsa):
        """Just store some variables for use below"""
        self.in_conn, self.out_conn = in_conn, out_conn
        self.src_fsa, self.dest_fsa = src_fsa, dest_fsa

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


class BackupSetGlobals(SetGlobals):
    """Functions for setting fsa related globals for backup session"""

    def set_special_escapes(self, rbdir):
        """Escaping DOS devices and trailing periods/spaces works like
        regular filename escaping. If only the destination requires it,
        then we do it. Otherwise, it is not necessary, since the files
        couldn't have been created in the first place. We also record
        whether we have done it in order to handle the case where a
        volume which was escaped is later restored by an OS that does
        not require it.

        """

        suggested_edd = (self.dest_fsa.escape_dos_devices
                         and not self.src_fsa.escape_dos_devices)
        suggested_ets = (self.dest_fsa.escape_trailing_spaces
                         and not self.src_fsa.escape_trailing_spaces)

        se_rp = rbdir.append("special_escapes")
        if not se_rp.lstat():
            actual_edd, actual_ets = suggested_edd, suggested_ets
            se = ""
            if actual_edd:
                se = se + "escape_dos_devices\n"
            if actual_ets:
                se = se + "escape_trailing_spaces\n"
            se_rp.write_string(se)
        else:
            se = se_rp.get_string().split("\n")
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

    def set_chars_to_quote(self, rbdir):
        """Set chars_to_quote setting for backup session

        Unlike most other options, the chars_to_quote setting also
        depends on the current settings in the rdiff-backup-data
        directory, not just the current fs features.

        """
        ctq = self._compare_ctq_file(rbdir, self._get_ctq_from_fsas())

        Globals.set_all('chars_to_quote', ctq)
        if Globals.chars_to_quote:
            FilenameMapping.set_init_quote_vals()

    def _update_triple(self, src_support, dest_support, attr_triple):
        """Many of the settings have a common form we can handle here"""
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
        """Determine chars_to_quote just from filesystems, no ctq file"""
        ctq = []

        if self.src_fsa.case_sensitive and not self.dest_fsa.case_sensitive:
            ctq.append(b"A-Z")  # Quote upper case
        if not self.dest_fsa.extended_filenames:
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

    def _compare_ctq_file(self, rbdir, suggested_ctq):
        """
        Compare chars_to_quote previous, enforced and suggested

        Returns the actual quoting to be used
        """
        ctq_rp = rbdir.append(b"chars_to_quote")
        if not ctq_rp.lstat():  # the chars_to_quote file doesn't exist
            if Globals.chars_to_quote is None:
                actual_ctq = suggested_ctq
            else:
                actual_ctq = Globals.chars_to_quote
                if actual_ctq != suggested_ctq:
                    log.Log("File system at '{fs}' suggested quoting '{sq}' "
                            "but override quoting '{oq}' will be used. "
                            "Assuming you know what you are doing".format(
                                fs=ctq_rp, sq=suggested_ctq, oq=actual_ctq),
                            log.NOTE)
            ctq_rp.write_bytes(actual_ctq)
            return actual_ctq

        previous_ctq = ctq_rp.get_bytes()

        if Globals.chars_to_quote is None:
            if suggested_ctq and suggested_ctq != previous_ctq:
                # the file system has new specific requirements
                actual_ctq = suggested_ctq
            else:
                actual_ctq = previous_ctq
                if previous_ctq and not suggested_ctq:
                    log.Log("File system at '{fs}' no longer needs quoting "
                            "but we will retain for backwards "
                            "compatibility".format(fs=ctq_rp), log.NOTE)
        else:
            actual_ctq = Globals.chars_to_quote  # Globals override
            if actual_ctq != suggested_ctq:
                log.Log("File system at '{fs}' suggested quoting '{sq}' "
                        "but override quoting '{oq}' will be used. "
                        "Assuming you know what you are doing".format(
                            fs=ctq_rp, sq=suggested_ctq, oq=actual_ctq),
                        log.NOTE)

        # the quoting didn't change so all is good
        if actual_ctq == previous_ctq:
            return actual_ctq
        else:
            log.Log.FatalError(
                "The repository quoting '{rq}' would need to be migrated from "
                "old quoting chars '{oq}' to new quoting chars '{nq}'. "
                "This may mean that the repository has been moved between "
                "different file systems.".format(
                    rq=ctq_rp, oq=previous_ctq, nq=actual_ctq))


class RestoreSetGlobals(SetGlobals):
    """Functions for setting fsa-related globals for restore session"""

    def set_special_escapes(self, rbdir):
        """Set escape_dos_devices and escape_trailing_spaces from
        rdiff-backup-data dir, just like chars_to_quote"""
        se_rp = rbdir.append("special_escapes")
        if se_rp.lstat():
            se = se_rp.get_string().split("\n")
            actual_edd = ("escape_dos_devices" in se)
            actual_ets = ("escape_trailing_spaces" in se)
        else:
            log.Log("The special escapes file '{ef}' was not found, "
                    "will assume need to escape DOS devices and trailing "
                    "spaces based on file systems".format(ef=se_rp),
                    log.WARNING)
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

    def set_chars_to_quote(self, rbdir):
        """Set chars_to_quote from rdiff-backup-data dir"""
        if Globals.chars_to_quote is not None:
            return  # already overridden

        ctq_rp = rbdir.append(b"chars_to_quote")
        if ctq_rp.lstat():
            Globals.set_all("chars_to_quote", ctq_rp.get_bytes())
        else:
            log.Log("chars_to_quote file '{qf}' not found, assuming no quoting "
                    "required in backup repository".format(qf=ctq_rp),
                    log.WARNING)
            Globals.set_all("chars_to_quote", b"")

    def _update_triple(self, src_support, dest_support, attr_triple):
        """Update global settings for feature based on fsa results

        This is slightly different from BackupSetGlobals._update_triple
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


class SingleSetGlobals(RestoreSetGlobals):
    """For setting globals when dealing only with one filesystem"""

    def __init__(self, conn, fsa):
        self.conn = conn
        self.dest_fsa = fsa

    def set_eas(self):
        self._update_triple(
            self.dest_fsa.eas, ('eas_active', 'eas_write', 'eas_conn'))

    def set_acls(self):
        self._update_triple(
            self.dest_fsa.acls, ('acls_active', 'acls_write', 'acls_conn'))

    def set_win_acls(self):
        self._update_triple(
            self.src_fsa.win_acls, self.dest_fsa.win_acls,
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
        """Update global vars from single fsa test"""
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


# @API(get_readonly_fsa, 200, 200)
def get_readonly_fsa(desc_string, rp):
    """Return an fsa with given description_string

    Will be initialized read_only with given RPath rp.  We separate
    this out into a separate function so the request can be vetted by
    the security module.

    """
    if os.name == "nt":
        log.Log("Hardlinks disabled by default on Windows", log.INFO)
        Globals.set_all('preserve_hardlinks', 0)
    return FSAbilities(desc_string, rp, read_only=True)


# @API(backup_set_globals, 200, 200)
def backup_set_globals(rpin, force):
    """Given rps for source filesystem and repository, set fsa globals

    This should be run on the destination connection, because we may
    need to write a new chars_to_quote file.

    """
    assert Globals.rbdir.conn is Globals.local_connection, (
        "Action only foreseen locally and not over {conn}.".format(
            conn=Globals.rbdir.conn))
    src_fsa = rpin.conn.fs_abilities.get_readonly_fsa('source', rpin)
    log.Log(str(src_fsa), log.INFO)
    dest_fsa = FSAbilities('destination', Globals.rbdir)
    log.Log(str(dest_fsa), log.INFO)

    bsg = BackupSetGlobals(rpin.conn, Globals.rbdir.conn, src_fsa, dest_fsa)
    bsg.set_eas()
    bsg.set_acls()
    bsg.set_win_acls()
    bsg.set_resource_forks()
    bsg.set_carbonfile()
    bsg.set_hardlinks()
    bsg.set_fsync_directories()
    bsg.set_change_ownership()
    bsg.set_high_perms()
    bsg.set_symlink_perms()
    bsg.set_chars_to_quote(Globals.rbdir)
    bsg.set_special_escapes(Globals.rbdir)
    bsg.set_compatible_timestamps()


# @API(restore_set_globals, 200, 200)
def restore_set_globals(rpout):
    """Set fsa related globals for restore session, given in/out rps"""
    assert rpout.conn is Globals.local_connection, (
        "Action only foreseen locally and not over {conn}.".format(
            conn=rpout.conn))
    src_fsa = Globals.rbdir.conn.fs_abilities.get_readonly_fsa(
        'rdiff-backup repository', Globals.rbdir)
    log.Log(str(src_fsa), log.INFO)
    dest_fsa = FSAbilities('restore target', rpout)
    log.Log(str(dest_fsa), log.INFO)

    rsg = RestoreSetGlobals(Globals.rbdir.conn, rpout.conn, src_fsa, dest_fsa)
    rsg.set_eas()
    rsg.set_acls()
    rsg.set_win_acls()
    rsg.set_resource_forks()
    rsg.set_carbonfile()
    rsg.set_hardlinks()
    # No need to fsync anything when restoring
    rsg.set_change_ownership()
    rsg.set_high_perms()
    rsg.set_symlink_perms()
    rsg.set_chars_to_quote(Globals.rbdir)
    rsg.set_special_escapes(Globals.rbdir)
    rsg.set_compatible_timestamps()


# @API(single_set_globals, 200, 200)
def single_set_globals(rp, read_only=None):
    """Set fsa related globals for operation on single filesystem"""
    if read_only:
        fsa = rp.conn.fs_abilities.get_readonly_fsa(rp.path, rp)
    else:
        fsa = FSAbilities(rp.path, rp)
    log.Log(str(fsa), log.INFO)

    ssg = SingleSetGlobals(rp.conn, fsa)
    ssg.set_eas()
    ssg.set_acls()
    ssg.set_resource_forks()
    ssg.set_carbonfile()
    if not read_only:
        ssg.set_hardlinks()
        ssg.set_change_ownership()
        ssg.set_high_perms()
        ssg.set_symlink_perms()
    ssg.set_chars_to_quote(Globals.rbdir)
    ssg.set_special_escapes(Globals.rbdir)
    ssg.set_compatible_timestamps()
