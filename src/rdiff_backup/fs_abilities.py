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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
# USA
"""Determine the capabilities of given file system

rdiff-backup needs to read and write to file systems with varying
abilities.  For instance, some file systems and not others have ACLs,
are case-sensitive, or can store ownership information.  The code in
this module tests the file system for various features, and returns an
FSAbilities object describing it.

"""

import errno
import os
from . import Globals, log, TempFile, selection, robust, SetConnections, \
    FilenameMapping, win_acls, Time


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

    def __init__(self, name=None):
        """FSAbilities initializer.  name is only used in logging"""
        self.name = name

    def __str__(self):
        """Return pretty printable version of self"""
        assert self.read_only == 0 or self.read_only == 1, self.read_only
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
                    assert boolean == 0
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

    def init_readonly(self, rp):
        """Set variables using fs tested at RPath rp.  Run locally.

        This method does not write to the file system at all, and
        should be run on the file system when the file system will
        only need to be read.

        Only self.acls and self.eas are set.

        """
        assert rp.conn is Globals.local_connection
        self.root_rp = rp
        self.read_only = 1
        self.set_eas(rp, 0)
        self.set_acls(rp)
        self.set_win_acls(rp, 0)
        self.set_resource_fork_readonly(rp)
        self.set_carbonfile()
        self.set_case_sensitive_readonly(rp)
        self.set_escape_dos_devices(rp)
        self.set_escape_trailing_spaces_readonly(rp)
        return self

    def init_readwrite(self, rbdir):
        """Set variables using fs tested at rp_base.  Run locally.

        This method creates a temp directory in rp_base and writes to
        it in order to test various features.  Use on a file system
        that will be written to.

        """
        assert rbdir.conn is Globals.local_connection
        if not rbdir.isdir():
            assert not rbdir.lstat(), (rbdir.path, rbdir.lstat())
            rbdir.mkdir()
        self.root_rp = rbdir
        self.read_only = 0
        subdir = TempFile.new_in_dir(rbdir)
        subdir.mkdir()

        self.set_extended_filenames(subdir)
        self.set_win_reserved_filenames(subdir)
        self.set_case_sensitive_readwrite(subdir)
        self.set_ownership(subdir)
        self.set_hardlinks(subdir)
        self.set_fsync_dirs(subdir)
        self.set_eas(subdir, 1)
        self.set_acls(subdir)
        self.set_win_acls(subdir, 1)
        self.set_dir_inc_perms(subdir)
        self.set_resource_fork_readwrite(subdir)
        self.set_carbonfile()
        self.set_high_perms_readwrite(subdir)
        self.set_symlink_perms(subdir)
        self.set_escape_dos_devices(subdir)
        self.set_escape_trailing_spaces_readwrite(subdir)

        subdir.delete()
        return self

    def set_ownership(self, testdir):
        """Set self.ownership to true iff testdir's ownership can be changed"""
        tmp_rp = testdir.append("foo")
        tmp_rp.touch()
        uid, gid = tmp_rp.getuidgid()
        try:
            tmp_rp.chown(uid + 1, gid + 1)  # just choose random uid/gid
            tmp_rp.chown(0, 0)
        except (IOError, OSError, AttributeError):
            self.ownership = 0
        else:
            self.ownership = 1
        tmp_rp.delete()

    def set_hardlinks(self, testdir):
        """Set self.hardlinks to true iff hard linked files can be made"""
        hl_source = testdir.append("hardlinked_file1")
        hl_dir = testdir.append("hl")
        hl_dir.mkdir()
        hl_dest = hl_dir.append("hardlinked_file2")
        hl_source.touch()
        try:
            hl_dest.hardlink(hl_source.path)
            if hl_source.getinode() != hl_dest.getinode():
                raise IOError(errno.EOPNOTSUPP, "Hard links don't compare")
        except (IOError, OSError, AttributeError):
            if Globals.preserve_hardlinks != 0:
                log.Log(
                    "Warning: hard linking not supported by filesystem "
                    "at %s" % self.root_rp.get_safepath(), 3)
            self.hardlinks = None
        else:
            self.hardlinks = 1

    def set_fsync_dirs(self, testdir):
        """Set self.fsync_dirs if directories can be fsync'd"""
        assert testdir.conn is Globals.local_connection
        try:
            testdir.fsync()
        except (IOError, OSError):
            log.Log(
                "Directories on file system at %s are not fsyncable.\n"
                "Assuming it's unnecessary." % testdir.get_safepath(), 4)
            self.fsync_dirs = 0
        else:
            self.fsync_dirs = 1

    def set_extended_filenames(self, subdir):
        """Set self.extended_filenames by trying to write a path"""
        assert not self.read_only

        # Make sure ordinary filenames ok
        ordinary_filename = b'5-_ a.snapshot.gz'
        ord_rp = subdir.append(ordinary_filename)
        ord_rp.touch()
        assert ord_rp.lstat()
        ord_rp.delete()

        # Try path with UTF-8 encoded character
        extended_filename = (
            'uni' + chr(225) + chr(132) + chr(137)).encode('utf-8')
        ext_rp = None
        try:
            ext_rp = subdir.append(extended_filename)
            ext_rp.touch()
        except (IOError, OSError):
            if ext_rp:
                assert not ext_rp.lstat()
            self.extended_filenames = 0
        else:
            assert ext_rp.lstat()
            try:
                ext_rp.delete()
            except (IOError, OSError):
                # Broken CIFS setups will sometimes create UTF-8 files
                # and even stat them, but not let us perform file operations
                # on them. Test file cannot be deleted. UTF-8 chars not in the
                # underlying codepage get translated to '?'
                log.Log.FatalError(
                    "Could not delete extended filenames test "
                    "file. If you are using a CIFS share, please"
                    " see the FAQ entry about characters being "
                    "transformed to a '?'")
            self.extended_filenames = 1

    def set_win_reserved_filenames(self, subdir):
        """Set self.win_reserved_filenames by trying to write a path"""
        assert not self.read_only

        # Try Windows reserved characters
        win_reserved_filename = ':\\"'
        win_rp = None
        try:
            win_rp = subdir.append(win_reserved_filename)
            win_rp.touch()
        except (IOError, OSError):
            if win_rp:
                assert not win_rp.lstat()
            self.win_reserved_filenames = 1
        else:
            assert win_rp.lstat()
            try:
                win_rp.delete()
            except (IOError, OSError):
                self.win_reserved_filenames = 1
            else:
                self.win_reserved_filenames = 0

    def set_acls(self, rp):
        """Set self.acls based on rp.  Does not write.  Needs to be local"""
        assert Globals.local_connection is rp.conn
        assert rp.lstat()
        if Globals.acls_active == 0:
            log.Log(
                "POSIX ACLs test skipped. rdiff-backup run "
                "with --no-acls option.", 4)
            self.acls = 0
            return

        try:
            import posix1e
        except ImportError:
            log.Log(
                "Unable to import module posix1e from pylibacl "
                "package.\nPOSIX ACLs not supported on filesystem at %s" %
                rp.get_safepath(), 4)
            self.acls = 0
            return

        try:
            posix1e.ACL(file=rp.path)
        except IOError:
            log.Log(
                "POSIX ACLs not supported by filesystem at %s" %
                rp.get_safepath(), 4)
            self.acls = 0
        else:
            self.acls = 1

    def set_case_sensitive_readwrite(self, subdir):
        """Determine if directory at rp is case sensitive by writing"""
        assert not self.read_only
        upper_a = subdir.append("A")
        upper_a.touch()
        lower_a = subdir.append("a")
        if lower_a.lstat():
            lower_a.delete()
            upper_a.setdata()
            assert not upper_a.lstat()
            self.case_sensitive = 0
        else:
            upper_a.delete()
            self.case_sensitive = 1

    def set_case_sensitive_readonly(self, rp):
        """Determine if directory at rp is case sensitive without writing"""

        def find_letter(subdir):
            """Find a (subdir_rp, dirlist) with a letter in it, or None

            Recurse down the directory, looking for any file that has
            a letter in it.  Return the pair (rp, [list of filenames])
            where the list is of the directory containing rp.

            """
            files_list = robust.listrp(subdir)
            for filename in files_list:
                if filename != filename.swapcase():
                    return (subdir, files_list, filename)
            for filename in files_list:
                dir_rp = subdir.append(filename)
                if dir_rp.isdir():
                    subsearch = find_letter(dir_rp)
                    if subsearch:
                        return subsearch
            return None

        def test_triple(dir_rp, dirlist, filename):
            """Return 1 if filename shows system case sensitive"""
            try:
                letter_rp = dir_rp.append(filename)
            except OSError:
                return 0
            assert letter_rp.lstat(), letter_rp
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
                "Warning: could not determine case sensitivity of "
                "source directory at\n  %s\n"
                "because we can't find any files with letters in them.\n"
                "It will be treated as case sensitive." % rp.get_safepath(), 2)
            self.case_sensitive = 1
            return

        self.case_sensitive = test_triple(*triple)

    def set_eas(self, rp, write):
        """Set extended attributes from rp. Tests writing if write is true."""
        assert Globals.local_connection is rp.conn
        assert rp.lstat()
        if Globals.eas_active == 0:
            log.Log(
                "Extended attributes test skipped. rdiff-backup run "
                "with --no-eas option.", 4)
            self.eas = 0
            return
        try:
            import xattr
        except ImportError:
            log.Log(
                "Unable to import module xattr.\nExtended attributes not "
                "supported on filesystem at %s" % (rp.get_safepath(), ), 4)
            self.eas = 0
            return

        try:
            ver = xattr.__version__
        except AttributeError:
            ver = 'unknown'
        if ver < '0.2.2' or ver == 'unknown':
            log.Log(
                "Warning: Your version of pyxattr (%s) has broken support "
                "for extended\nattributes on symlinks. If you choose not "
                "to upgrade to a more recent version,\nyou may see many "
                "warning messages from listattr().\n" % (ver, ), 3)

        try:
            xattr.listxattr(rp.path)
            if write:
                xattr.setxattr(rp.path, b"user.test", b"test val")
                assert xattr.getxattr(rp.path, b"user.test") == b"test val"
        except IOError:
            log.Log(
                "Extended attributes not supported by "
                "filesystem at %s" % (rp.get_safepath(), ), 4)
            self.eas = 0
        except AssertionError:
            log.Log(
                "Extended attributes support is broken on filesystem at "
                "%s.\nPlease upgrade the filesystem driver, contact the "
                "developers,\nor use the --no-eas option to disable "
                "extended attributes\nsupport and suppress this message." %
                (rp.get_safepath(), ), 1)
            self.eas = 0
        else:
            self.eas = 1

    def set_win_acls(self, dir_rp, write):
        """Test if windows access control lists are supported"""
        assert Globals.local_connection is dir_rp.conn
        assert dir_rp.lstat()
        if Globals.win_acls_active == 0:
            log.Log(
                "Windows ACLs test skipped. rdiff-backup run "
                "with --no-acls option.", 4)
            self.win_acls = 0
            return

        try:
            import win32security
            import pywintypes
        except ImportError:
            log.Log(
                "Unable to import win32security module. Windows ACLs\n"
                "not supported by filesystem at %s" % dir_rp.get_safepath(), 4)
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
            log.Log(
                "Unable to load a Windows ACL.\nWindows ACLs not supported "
                "by filesystem at %s" % dir_rp.get_safepath(), 4)
            self.win_acls = 0
            return

        try:
            win_acls.init_acls()
        except (OSError, AttributeError, pywintypes.error):
            log.Log(
                "Unable to init win_acls.\nWindows ACLs not supported by "
                "filesystem at %s" % dir_rp.get_safepath(), 4)
            self.win_acls = 0
            return
        self.win_acls = 1

    def set_dir_inc_perms(self, rp):
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
        assert test_rp.isreg()
        if test_rp.getperms() == 0o7777 or test_rp.getperms() == 0o6777:
            self.dir_inc_perms = 1
        else:
            self.dir_inc_perms = 0
        test_rp.delete()

    def set_carbonfile(self):
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

    def set_resource_fork_readwrite(self, dir_rp):
        """Test for resource forks by writing to regular_file/..namedfork/rsrc"""
        assert dir_rp.conn is Globals.local_connection
        reg_rp = dir_rp.append('regfile')
        reg_rp.touch()

        s = 'test string---this should end up in resource fork'
        try:
            fp_write = open(
                os.path.join(reg_rp.path, b'..namedfork', b'rsrc'), 'wb')
            fp_write.write(s)
            assert not fp_write.close()

            fp_read = open(
                os.path.join(reg_rp.path, b'..namedfork', b'rsrc'), 'rb')
            s_back = fp_read.read()
            assert not fp_read.close()
        except (OSError, IOError):
            self.resource_forks = 0
        else:
            self.resource_forks = (s_back == s)
        reg_rp.delete()

    def set_resource_fork_readonly(self, dir_rp):
        """Test for resource fork support by testing an regular file

        Launches search for regular file in given directory.  If no
        regular file is found, resource_fork support will be turned
        off by default.

        """
        for rp in selection.Select(dir_rp).set_iter():
            if rp.isreg():
                try:
                    rfork = rp.append(b'..namedfork', b'rsrc')
                    fp = rfork.open('rb')
                    fp.read()
                    assert not fp.close()
                except (OSError, IOError):
                    self.resource_forks = 0
                    return
                self.resource_forks = 1
                return
        self.resource_forks = 0

    def set_high_perms_readwrite(self, dir_rp):
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
        except (OSError, IOError):
            self.high_perms = 0
        else:
            self.high_perms = 1
        tmpf_rp.delete()
        tmpd_rp.delete()

    def set_symlink_perms(self, dir_rp):
        """Test if symlink permissions are affected by umask"""
        sym_source = dir_rp.append(b"symlinked_file1")
        sym_source.touch()
        sym_dest = dir_rp.append(b"symlinked_file2")
        try:
            sym_dest.symlink(b"symlinked_file1")
        except (OSError, AttributeError):
            self.symlink_perms = 0
        else:
            sym_dest.setdata()
            assert sym_dest.issym()
            if sym_dest.getperms() == 0o700:
                self.symlink_perms = 1
            else:
                self.symlink_perms = 0
            sym_dest.delete()
        sym_source.delete()

    def set_escape_dos_devices(self, subdir):
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

    def set_escape_trailing_spaces_readwrite(self, testdir):
        """
        Windows and Linux/FAT32 will not preserve trailing spaces or periods.
        Linux/FAT32 behaves inconsistently: It will give an OSError,22 if
        os.mkdir() is called on a directory name with a space at the end, but
        will give an IOError("invalid mode") if you attempt to create a filename
        with a space at the end. However, if a period is placed at the end of
        the name, Linux/FAT32 is consistent with Cygwin and Native Windows.
        """

        period_rp = testdir.append("foo.")
        assert not period_rp.lstat()

        tmp_rp = testdir.append("foo")
        tmp_rp.touch()
        assert tmp_rp.lstat()

        period_rp.setdata()
        if period_rp.lstat():
            self.escape_trailing_spaces = 1
        else:
            self.escape_trailing_spaces = 0

        tmp_rp.delete()

    def set_escape_trailing_spaces_readonly(self, rp):
        """Determine if directory at rp permits filenames with trailing
        spaces or periods without writing."""

        def test_period(dir_rp, dirlist):
            """Return 1 if trailing spaces and periods should be escaped"""
            filename = dirlist[0]
            try:
                test_rp = dir_rp.append(filename)
            except OSError:
                return 0
            assert test_rp.lstat(), test_rp
            period = filename + b'.'
            if period in dirlist:
                return 0

            return 0  # FIXME the following lines fail if filename is almost too long
            period_rp = dir_rp.append(period)
            if period_rp.lstat():
                return 1
            return 0

        dirlist = robust.listrp(rp)
        if len(dirlist):
            self.escape_trailing_spaces = test_period(rp, dirlist)
        else:
            log.Log(
                "Warning: could not determine if source directory at\n"
                "  %s\npermits trailing spaces or periods in "
                "filenames because we can't find any files.\n"
                "It will be treated as permitting such files." %
                rp.get_safepath(), 2)
            self.escape_trailing_spaces = 0


def get_readonly_fsa(desc_string, rp):
    """Return an fsa with given description_string

    Will be initialized read_only with given RPath rp.  We separate
    this out into a separate function so the request can be vetted by
    the security module.

    """
    if os.name == 'nt':
        log.Log("Hardlinks disabled by default on Windows", 4)
        SetConnections.UpdateGlobal('preserve_hardlinks', 0)
    return FSAbilities(desc_string).init_readonly(rp)


class SetGlobals:
    """Various functions for setting Globals vars given FSAbilities above

    Container for BackupSetGlobals and RestoreSetGlobals (don't use directly)

    """

    def __init__(self, in_conn, out_conn, src_fsa, dest_fsa):
        """Just store some variables for use below"""
        self.in_conn, self.out_conn = in_conn, out_conn
        self.src_fsa, self.dest_fsa = src_fsa, dest_fsa

    def set_eas(self):
        self.update_triple(self.src_fsa.eas, self.dest_fsa.eas,
                           ('eas_active', 'eas_write', 'eas_conn'))

    def set_acls(self):
        self.update_triple(self.src_fsa.acls, self.dest_fsa.acls,
                           ('acls_active', 'acls_write', 'acls_conn'))
        if Globals.never_drop_acls and not Globals.acls_active:
            log.Log.FatalError("--never-drop-acls specified, but ACL support\n"
                               "missing from source filesystem")

    def set_win_acls(self):
        self.update_triple(
            self.src_fsa.win_acls, self.dest_fsa.win_acls,
            ('win_acls_active', 'win_acls_write', 'win_acls_conn'))

    def set_resource_forks(self):
        self.update_triple(self.src_fsa.resource_forks,
                           self.dest_fsa.resource_forks,
                           ('resource_forks_active', 'resource_forks_write',
                            'resource_forks_conn'))

    def set_carbonfile(self):
        self.update_triple(
            self.src_fsa.carbonfile, self.dest_fsa.carbonfile,
            ('carbonfile_active', 'carbonfile_write', 'carbonfile_conn'))

    def set_hardlinks(self):
        if Globals.preserve_hardlinks != 0:
            SetConnections.UpdateGlobal('preserve_hardlinks',
                                        self.dest_fsa.hardlinks)

    def set_fsync_directories(self):
        SetConnections.UpdateGlobal('fsync_directories',
                                    self.dest_fsa.fsync_dirs)

    def set_change_ownership(self):
        SetConnections.UpdateGlobal('change_ownership',
                                    self.dest_fsa.ownership)

    def set_high_perms(self):
        if not self.dest_fsa.high_perms:
            SetConnections.UpdateGlobal('permission_mask', 0o777)

    def set_symlink_perms(self):
        SetConnections.UpdateGlobal('symlink_perms',
                                    self.dest_fsa.symlink_perms)

    def set_compatible_timestamps(self):
        if Globals.chars_to_quote.find(b":") > -1:
            SetConnections.UpdateGlobal('use_compatible_timestamps', 1)
            Time.setcurtime(
                Time.curtime)  # update Time.curtimestr on all conns
            log.Log("Enabled use_compatible_timestamps", 4)


class BackupSetGlobals(SetGlobals):
    """Functions for setting fsa related globals for backup session"""

    def update_triple(self, src_support, dest_support, attr_triple):
        """Many of the settings have a common form we can handle here"""
        active_attr, write_attr, conn_attr = attr_triple
        if Globals.get(active_attr) == 0:
            return  # don't override 0
        for attr in attr_triple:
            SetConnections.UpdateGlobal(attr, None)
        if not src_support:
            return  # if source doesn't support, nothing
        SetConnections.UpdateGlobal(active_attr, 1)
        self.in_conn.Globals.set_local(conn_attr, 1)
        if dest_support:
            SetConnections.UpdateGlobal(write_attr, 1)
            self.out_conn.Globals.set_local(conn_attr, 1)

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
                log.Log(
                    "Warning: System no longer needs DOS devices escaped, "
                    "but we will retain for backwards compatibility.", 2)
            if actual_ets != suggested_ets and not suggested_ets:
                log.Log(
                    "Warning: System no longer needs trailing spaces or "
                    "periods escaped, but we will retain for backwards "
                    "compatibility.", 2)

        SetConnections.UpdateGlobal('escape_dos_devices', actual_edd)
        log.Log("Backup: escape_dos_devices = %d" % actual_edd, 4)

        SetConnections.UpdateGlobal('escape_trailing_spaces', actual_ets)
        log.Log("Backup: escape_trailing_spaces = %d" % actual_ets, 4)

    def set_chars_to_quote(self, rbdir, force):
        """Set chars_to_quote setting for backup session

        Unlike most other options, the chars_to_quote setting also
        depends on the current settings in the rdiff-backup-data
        directory, not just the current fs features.

        """
        (ctq, update) = self.compare_ctq_file(rbdir, self.get_ctq_from_fsas(),
                                              force)

        SetConnections.UpdateGlobal('chars_to_quote', ctq)
        if Globals.chars_to_quote:
            FilenameMapping.set_init_quote_vals()
        return update

    def get_ctq_from_fsas(self):
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

    def compare_ctq_file(self, rbdir, suggested_ctq, force):
        """Compare ctq file with suggested result, return actual ctq"""
        ctq_rp = rbdir.append(b"chars_to_quote")
        if not ctq_rp.lstat():
            if Globals.chars_to_quote is None:
                actual_ctq = suggested_ctq
            else:
                actual_ctq = Globals.chars_to_quote
            ctq_rp.write_bytes(actual_ctq)
            return (actual_ctq, None)

        if Globals.chars_to_quote is None:
            actual_ctq = ctq_rp.get_bytes()
        else:
            actual_ctq = Globals.chars_to_quote  # Globals override

        if actual_ctq == suggested_ctq:
            return (actual_ctq, None)
        if suggested_ctq == b"":
            log.Log(
                "Warning: File system no longer needs quoting, "
                "but we will retain for backwards compatibility.", 2)
            return (actual_ctq, None)
        if Globals.chars_to_quote is None:
            if force:
                log.Log(
                    "Warning: migrating rdiff-backup repository from"
                    "old quoting chars %r to new quoting chars %r" %
                    (actual_ctq, suggested_ctq), 2)
                ctq_rp.delete()
                ctq_rp.write_bytes(suggested_ctq)
                return (suggested_ctq, 1)
            else:
                log.Log.FatalError(
                    """New quoting requirements!

The quoting chars this session needs %r do not match
the repository settings %r listed in

%s

This may be caused when you copy an rdiff-backup repository from a
normal file system onto a windows one that cannot support the same
characters, or if you backup a case-sensitive file system onto a
case-insensitive one that previously only had case-insensitive ones
backed up onto it.

By specifying the --force option, rdiff-backup will migrate the
repository from the old quoting chars to the new ones.""" %
                    (suggested_ctq, actual_ctq, ctq_rp.get_safepath()))
        return (actual_ctq, None)  # Maintain Globals override


class RestoreSetGlobals(SetGlobals):
    """Functions for setting fsa-related globals for restore session"""

    def update_triple(self, src_support, dest_support, attr_triple):
        """Update global settings for feature based on fsa results

        This is slightly different from BackupSetGlobals.update_triple
        because (using the mirror_metadata file) rpaths from the
        source may have more information than the file system
        supports.

        """
        active_attr, write_attr, conn_attr = attr_triple
        if Globals.get(active_attr) == 0:
            return  # don't override 0
        for attr in attr_triple:
            SetConnections.UpdateGlobal(attr, None)
        if not dest_support:
            return  # if dest doesn't support, do nothing
        SetConnections.UpdateGlobal(active_attr, 1)
        self.out_conn.Globals.set_local(conn_attr, 1)
        self.out_conn.Globals.set_local(write_attr, 1)
        if src_support:
            self.in_conn.Globals.set_local(conn_attr, 1)

    def set_special_escapes(self, rbdir):
        """Set escape_dos_devices and escape_trailing_spaces from
        rdiff-backup-data dir, just like chars_to_quote"""
        se_rp = rbdir.append("special_escapes")
        if se_rp.lstat():
            se = se_rp.get_string().split("\n")
            actual_edd = ("escape_dos_devices" in se)
            actual_ets = ("escape_trailing_spaces" in se)
        else:
            log.Log(
                "Warning: special_escapes file not found,\n"
                "will assume need to escape DOS devices and trailing "
                "spaces based on file systems.", 2)
            if getattr(self, "src_fsa", None) is not None:
                actual_edd = (self.src_fsa.escape_dos_devices
                              and not self.dest_fsa.escape_dos_devices)
                actual_ets = (self.src_fsa.escape_trailing_spaces
                              and not self.dest_fsa.escape_trailing_spaces)
            else:
                # Single filesystem operation
                actual_edd = self.dest_fsa.escape_dos_devices
                actual_ets = self.dest_fsa.escape_trailing_spaces

        SetConnections.UpdateGlobal('escape_dos_devices', actual_edd)
        log.Log("Backup: escape_dos_devices = %d" % actual_edd, 4)

        SetConnections.UpdateGlobal('escape_trailing_spaces', actual_ets)
        log.Log("Backup: escape_trailing_spaces = %d" % actual_ets, 4)

    def set_chars_to_quote(self, rbdir):
        """Set chars_to_quote from rdiff-backup-data dir"""
        if Globals.chars_to_quote is not None:
            return  # already overridden

        ctq_rp = rbdir.append(b"chars_to_quote")
        if ctq_rp.lstat():
            SetConnections.UpdateGlobal("chars_to_quote", ctq_rp.get_bytes())
        else:
            log.Log(
                "Warning: chars_to_quote file not found,\n"
                "assuming no quoting in backup repository.", 2)
            SetConnections.UpdateGlobal("chars_to_quote", b"")


class SingleSetGlobals(RestoreSetGlobals):
    """For setting globals when dealing only with one filesystem"""

    def __init__(self, conn, fsa):
        self.conn = conn
        self.dest_fsa = fsa

    def update_triple(self, fsa_support, attr_triple):
        """Update global vars from single fsa test"""
        active_attr, write_attr, conn_attr = attr_triple
        if Globals.get(active_attr) == 0:
            return  # don't override 0
        for attr in attr_triple:
            SetConnections.UpdateGlobal(attr, None)
        if not fsa_support:
            return
        SetConnections.UpdateGlobal(active_attr, 1)
        SetConnections.UpdateGlobal(write_attr, 1)
        self.conn.Globals.set_local(conn_attr, 1)

    def set_eas(self):
        self.update_triple(self.dest_fsa.eas,
                           ('eas_active', 'eas_write', 'eas_conn'))

    def set_acls(self):
        self.update_triple(self.dest_fsa.acls,
                           ('acls_active', 'acls_write', 'acls_conn'))

    def set_win_acls(self):
        self.update_triple(
            self.src_fsa.win_acls, self.dest_fsa.win_acls,
            ('win_acls_active', 'win_acls_write', 'win_acls_conn'))

    def set_resource_forks(self):
        self.update_triple(self.dest_fsa.resource_forks,
                           ('resource_forks_active', 'resource_forks_write',
                            'resource_forks_conn'))

    def set_carbonfile(self):
        self.update_triple(
            self.dest_fsa.carbonfile,
            ('carbonfile_active', 'carbonfile_write', 'carbonfile_conn'))


def backup_set_globals(rpin, force):
    """Given rps for source filesystem and repository, set fsa globals

    This should be run on the destination connection, because we may
    need to write a new chars_to_quote file.

    """
    assert Globals.rbdir.conn is Globals.local_connection
    src_fsa = rpin.conn.fs_abilities.get_readonly_fsa('source', rpin)
    log.Log(str(src_fsa), 4)
    dest_fsa = FSAbilities('destination').init_readwrite(Globals.rbdir)
    log.Log(str(dest_fsa), 4)

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
    update_quoting = bsg.set_chars_to_quote(Globals.rbdir, force)
    bsg.set_special_escapes(Globals.rbdir)
    bsg.set_compatible_timestamps()

    if update_quoting and force:
        FilenameMapping.update_quoting(Globals.rbdir)


def restore_set_globals(rpout):
    """Set fsa related globals for restore session, given in/out rps"""
    assert rpout.conn is Globals.local_connection
    src_fsa = Globals.rbdir.conn.fs_abilities.get_readonly_fsa(
        'rdiff-backup repository', Globals.rbdir)
    log.Log(str(src_fsa), 4)
    dest_fsa = FSAbilities('restore target').init_readwrite(rpout)
    log.Log(str(dest_fsa), 4)

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


def single_set_globals(rp, read_only=None):
    """Set fsa related globals for operation on single filesystem"""
    if read_only:
        fsa = rp.conn.fs_abilities.get_readonly_fsa(rp.path, rp)
    else:
        fsa = FSAbilities(rp.path).init_readwrite(rp)
    log.Log(str(fsa), 4)

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
