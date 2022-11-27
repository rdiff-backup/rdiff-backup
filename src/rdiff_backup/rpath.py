# Copyright 2002, 2003, 2004 Ben Escoto
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
"""Wrapper class around a real path like "/usr/bin/env"

The RPath (short for Remote Path) and associated classes make some
function calls more convenient and also make working with files on
remote systems transparent.

For instance, suppose

rp = RPath(connection_object, "/usr/bin/env")

Then rp.getperms() returns the permissions of that file, and
rp.delete() deletes that file.  Both of these will work the same even
if "usr/bin/env" is on a different computer.  So many rdiff-backup
functions use rpaths so they don't have to know whether the files they
are dealing with are local or remote.

"""

import errno
import gzip
import os
import re
import shutil
import stat
import tempfile
import time
from rdiff_backup import Globals, Time, log, C
from rdiffbackup.utils import usrgrp
from rdiffbackup.locations.map import owners as map_owners
from rdiffbackup.meta import acl_posix, acl_win, ea

try:
    import win32api
    import win32con
    import pywintypes
except ImportError:
    pass


class SkipFileException(Exception):
    """Signal that the current file should be skipped but then continue

    This exception will often be raised when there is problem reading
    an individual file, but it makes sense for the rest of the backup
    to keep going.

    """
    pass


class RPathException(Exception):
    pass


class RORPath:
    """Read Only RPath - carry information about a path

    These contain information about a file, and possible the file's
    data, but do not have a connection and cannot be written to or
    changed.  The advantage of these objects is that they can be
    communicated by encoding their index and data dictionary.

    """

    @staticmethod
    def _global_ignored_keys():
        """Returns a set of keys to be ignored during comparaison,
        based on global settings."""
        global_ignored_keys = set(())
        if not Globals.preserve_atime:
            global_ignored_keys.add('atime')
        if not Globals.eas_write:
            global_ignored_keys.add('ea')
        if not Globals.acls_write:
            global_ignored_keys.add('acl')
        if not Globals.win_acls_write:
            global_ignored_keys.add('win_acl')
        if not Globals.carbonfile_write:
            global_ignored_keys.add('carbonfile')
        if not Globals.resource_forks_write:
            global_ignored_keys.add('resource_forks')
        return global_ignored_keys

    @classmethod
    def path_join(self, *filenames):
        """Simulate the os.path.join function to have the same separator '/' on all platforms"""

        def abs_drive(filename):
            """Because os.path.join does make out of a tuple with a drive letter under Windows
            a path _relative_ to the current directory on the drive, we need to make it
            absolute ourselves by adding a slash at the end."""
            if re.match(b"^[A-Za-z]:$", filename):  # if filename is a drive
                return filename + b'/'  # os.path.join won't make a drive absolute for us
            else:
                return filename

        if os.path.altsep:  # only Windows has an alternative separator for paths
            filenames = tuple(map(abs_drive, filenames))
            return os.path.join(*filenames).replace(
                os.fsencode(os.path.sep), b'/')
        else:
            return os.path.join(*filenames)

    @classmethod
    def getcwdb(self):
        """A getcwdb function that makes sure that also under Windows '/' are used"""
        if os.path.altsep:  # only Windows has an alternative separator for paths
            return os.getcwdb().replace(os.fsencode(os.path.sep), b'/')
        else:
            return os.getcwdb()

    def __init__(self, index, data=None):
        self.index = tuple(map(os.fsencode, index))
        if data:
            self.data = data
        else:
            self.data = {'type': None}  # signify empty file
        self.file = None

    def __eq__(self, other):
        """True iff the two rorpaths are equivalent"""
        if self.index != other.index:
            return False

        # we build a set of keys to be ignored during loose comparaison
        ignored_keys = set(('ctime', 'nlink'))
        # add the keys to be globally ignored
        ignored_keys.update(self._global_ignored_keys())
        # global and self specific additions
        if (not self.isreg() or self.getnumlinks() == 1
                or not Globals.compare_inode
                or not Globals.preserve_hardlinks):
            ignored_keys.add('inode')
            ignored_keys.add('devloc')
        # self specific additions
        if not self.isreg():
            ignored_keys.add('size')
            if self.issym():
                # Don't compare gid/uid for symlinks
                ignored_keys.update(
                    frozenset(('uid', 'gid', 'uname', 'gname')))
        # self and other specific additions
        if (self.isspecial() and other.isreg() and other.getsize() == 0):
            # Special files may be replaced with empty regular files
            ignored_keys.add('type')

        # we remove the ignored keys from the set of dictionary keys
        # before we compare them
        for key in (frozenset(self.data.keys()) - ignored_keys):
            if key == 'uname' or key == 'gname':
                # here for legacy reasons - 0.12.x didn't store u/gnames
                other_name = other.data.get(key, None)
                if (other_name and other_name != "None"
                        and other_name != self.data[key]):
                    return False
            elif (key not in other.data or self.data[key] != other.data[key]):
                return False
        return True

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        """
        Pretty print file statistics
        """
        return "<{cls}/{cid}:\n\tIndex={idx}\n\tData={data}>".format(
            cls=self.__class__.__name__, cid=id(self),
            idx=self.get_safeindex(), data=self.data)

    def __str__(self):
        """
        Return safe path of index even with names throwing UnicodeEncodeError

        For instance, if the index is ("a", "b"), return "'a/b'".
        """
        return self.get_indexpath().decode(errors='replace')

    def __getstate__(self):
        """Return picklable state

        This is necessary in case the RORPath is carrying around a
        file object, which can't/shouldn't be pickled.

        """
        return (self.index, self.data)

    def __setstate__(self, rorp_state):
        """Reproduce RORPath from __getstate__ output"""
        self.index, self.data = rorp_state

    def zero(self):
        """Set inside of self to type None"""
        self.data = {'type': None}
        self.file = None

    def make_zero_dir(self, dir_rp):
        """Set self.data the same as dir_rp.data but with safe permissions"""
        self.data = dir_rp.data.copy()
        self.data['perms'] = 0o700

    def equal_loose(self, other):
        """True iff the two rorpaths are kinda equivalent

        Sometimes because permissions cannot be set, a file cannot be
        replicated exactly on the remote side.  This function tells
        you whether the two files are close enough.  self must be the
        original rpath.

        """
        # we build a set of keys to be ignored during loose comparaison
        ignored_keys = set(('uid', 'gid', 'uname', 'gname', 'ctime', 'inode',
                           'mirrorname', 'incname', 'devloc', 'nlink'))
        # we ignore the hash because one or the other might not have it FIXME?
        ignored_keys.add('sha1')
        # add the keys to be globally ignored
        ignored_keys.update(self._global_ignored_keys())
        # self specific additions
        if not self.isreg():
            ignored_keys.add('size')
        # self and other specific additions
        if (self.isspecial() and other.isreg() and other.getsize() == 0):
            # Special files may be replaced with empty regular files
            ignored_keys.add('type')

        # we remove the ignored keys from the set of dictionary keys
        # before we compare them
        for key in (frozenset(self.data.keys()) - ignored_keys):
            if (key not in other.data or self.data[key] != other.data[key]):
                return False

        if self.lstat() and not self.issym() and Globals.change_ownership:
            # Now compare ownership.  Symlinks don't have ownership
            try:
                own_uid_gid = map_owners.map_rpath_owner(self)
                if own_uid_gid != other.getuidgid():
                    return False
            except KeyError:
                # uid/gid might be missing if metadata file is corrupt
                return False

        return True

    def getRORPath(self):
        """Return new rorpath based on self"""
        return RORPath(self.index, self.data.copy())

    def lstat(self):
        """Returns type of file

        The allowable types are None if the file doesn't exist, 'reg'
        for a regular file, 'dir' for a directory, 'dev' for a device
        file, 'fifo' for a fifo, 'sock' for a socket, and 'sym' for a
        symlink.
        """
        return self.data['type']

    gettype = lstat

    def isdir(self):
        """True if self is a dir"""
        return self.data['type'] == 'dir'

    def isreg(self):
        """True if self is a regular file"""
        return self.data['type'] == 'reg'

    def issym(self):
        """True if path is of a symlink"""
        return self.data['type'] == 'sym'

    def isfifo(self):
        """True if path is a fifo"""
        return self.data['type'] == 'fifo'

    def ischardev(self):
        """True if path is a character device file"""
        return self.data['type'] == 'dev' and self.data['devnums'][0] == 'c'

    def isblkdev(self):
        """True if path is a block device file"""
        return self.data['type'] == 'dev' and self.data['devnums'][0] == 'b'

    def isdev(self):
        """True if path is a device file"""
        return self.data['type'] == 'dev'

    def issock(self):
        """True if path is a socket"""
        return self.data['type'] == 'sock'

    def isspecial(self):
        """True if the file is a sock, symlink, device, or fifo"""
        type = self.data['type']
        return (type == 'dev' or type == 'sock' or type == 'fifo'
                or type == 'sym')

    def getperms(self):
        """Return permission block of file"""
        if 'perms' in self.data:
            return self.data['perms']
        else:
            return 0

    def getuname(self):
        """Return username that owns the file"""
        try:
            return self.data['uname']
        except KeyError:
            return None

    def getgname(self):
        """Return groupname that owns the file"""
        try:
            return self.data['gname']
        except KeyError:
            return None

    def hassize(self):
        """True if rpath has a size parameter"""
        return 'size' in self.data

    def getsize(self):
        """Return length of file in bytes"""
        return self.data['size']

    def getuidgid(self):
        """Return userid/groupid of file"""
        return self.data['uid'], self.data['gid']

    def getatime(self):
        """Return access time in seconds"""
        return self.data['atime']

    def getmtime(self):
        """Return modification time in seconds"""
        return self.data['mtime']

    def getctime(self):
        """Return change time in seconds"""
        return self.data['ctime']

    def getinode(self):
        """Return inode number of file"""
        return self.data['inode']

    def getdevloc(self):
        """Device number file resides on"""
        return self.data['devloc']

    def getnumlinks(self):
        """Number of places inode is linked to"""
        if 'nlink' in self.data:
            return self.data['nlink']
        else:
            return 1

    def readlink(self):
        """Wrapper around os.readlink()"""
        return self.data['linkname']

    def getdevnums(self):
        """Return a device's type and major/minor numbers from dictionary"""
        return self.data['devnums']

    def setfile(self, file):
        """Right now just set self.file to be the already opened file"""
        assert file and not self.file, "Can't assign twice a file."

        def closing_hook():
            self._file_already_open = False

        self.file = _RPathFileHook(file, closing_hook)
        self._file_already_open = False

    def get_safeindex(self):
        """Return index as a tuple of strings with safe decoding

        For instance, if the index is (b"a", b"b"), return ("a", "b")
        """
        return tuple(map(lambda f: f.decode(errors='replace'), self.index))

    def get_indexpath(self):
        """Return path of index portion

        For instance, if the index is ("a", "b"), return "a/b".

        """
        if not self.index:
            return b'.'
        return self.path_join(*self.index)

    def get_attached_filetype(self):
        """If there is a file attached, say what it is

        Currently the choices are 'snapshot' meaning an exact copy of
        something, and 'diff' for an rdiff style diff.

        """
        return self.data['filetype']

    def set_attached_filetype(self, type):
        """Set the type of the attached file"""
        self.data['filetype'] = type

    def isflaglinked(self):
        """True if rorp is a signature/diff for a hardlink file

        This indicates that a file's data need not be transferred
        because it is hardlinked on the remote side.

        """
        return 'linked' in self.data

    def get_link_flag(self):
        """Return previous index that a file is hard linked to"""
        return self.data['linked']

    def flaglinked(self, index):
        """Signal that rorp is a signature/diff for a hardlink file"""
        self.data['linked'] = index

    def open(self, mode):
        """Return file type object if any was given using self.setfile"""
        if mode != "rb":
            raise RPathException("Bad mode %s" % mode)
        if self._file_already_open:
            raise RPathException("Attempt to open same file twice")
        self._file_already_open = True
        return self.file

    def close_if_necessary(self):
        """If file is present, discard data and close"""
        if self.file:
            while self.file.read(Globals.blocksize):
                pass
            self.file.close()
            self._file_already_open = False

    def set_acl(self, acl_meta):
        """Record access control list in dictionary.  Does not write"""
        self.data['acl'] = acl_meta

    def get_acl(self):
        """Return access control list object from dictionary"""
        try:
            return self.data['acl']
        except KeyError:
            acl_meta = self.data['acl'] = acl_posix.get_blank_meta(self.index)
            return acl_meta

    def set_ea(self, ea_meta):
        """Record extended attributes in dictionary.  Does not write"""
        self.data['ea'] = ea_meta

    def get_ea(self):
        """Return extended attributes object"""
        try:
            return self.data['ea']
        except KeyError:
            ea_meta = self.data['ea'] = ea.get_blank_meta(self.index)
            return ea_meta

    def has_carbonfile(self):
        """True if rpath has a carbonfile parameter"""
        return 'carbonfile' in self.data

    def get_carbonfile(self):
        """Returns the carbonfile data"""
        return self.data['carbonfile']

    def set_carbonfile(self, cfile):
        """Record carbonfile data in dictionary.  Does not write."""
        self.data['carbonfile'] = cfile

    def has_resource_fork(self):
        """True if rpath has a resourcefork parameter"""
        return 'resourcefork' in self.data

    def get_resource_fork(self):
        """Return the resource fork in binary data"""
        return self.data['resourcefork']

    def set_resource_fork(self, rfork):
        """Record resource fork in dictionary.  Does not write"""
        self.data['resourcefork'] = rfork

    def set_win_acl(self, acl_meta):
        """Record Windows access control list in dictionary. Does not write"""
        self.data['win_acl'] = acl_meta

    def get_win_acl(self):
        """Return access control list object from dictionary"""
        try:
            return self.data['win_acl']
        except KeyError:
            acl_meta = self.data['win_acl'] = acl_win.get_blank_meta(self.index)
            return acl_meta

    def has_alt_mirror_name(self):
        """True if rorp has an alternate mirror name specified"""
        return 'mirrorname' in self.data

    def get_alt_mirror_name(self):
        """Return alternate mirror name (for long filenames)"""
        return self.data['mirrorname']

    def set_alt_mirror_name(self, filename):
        """Set alternate mirror name to filename

        Instead of writing to the traditional mirror file, store
        mirror information in filename in the long filename
        directory.

        """
        self.data['mirrorname'] = filename

    def has_alt_inc_name(self):
        """True if rorp has an alternate increment base specified"""
        return 'incname' in self.data

    def get_alt_inc_name(self):
        """Return alternate increment base (used for long name support)"""
        return self.data['incname']

    def set_alt_inc_name(self, name):
        """Set alternate increment name to name

        If set, increments will be in the long name directory with
        name as their base.  If the alt mirror name is set, this
        should be set to the same.

        """
        self.data['incname'] = name

    def has_sha1(self):
        """True iff self has its sha1 digest set"""
        return 'sha1' in self.data

    def get_sha1(self):
        """Return sha1 digest.  Causes exception unless set_sha1 first"""
        return self.data['sha1']

    def set_sha1(self, digest):
        """
        Set sha1 hash (should be in hexdecimal)

        Return True if modified, else False.
        """
        old_digest = self.data.get('sha1')
        self.data['sha1'] = digest
        return old_digest != digest

    def _equal_verbose(self,
                       other,
                       check_index=1,
                       compare_inodes=0,
                       compare_ownership=0,
                       compare_acls=0,
                       compare_eas=0,
                       compare_win_acls=0,
                       compare_size=1,
                       compare_type=1,
                       verbosity=log.WARNING):
        """Like __eq__, but log more information.  Useful when testing"""
        if check_index and self.index != other.index:
            log.Log("Index {ix} != other index {oi}".format(
                ix=self.get_safeindex(), oi=other.get_safeindex()),
                verbosity)
            return None

        for key in list(self.data.keys()):  # compare dicts key by key
            if (key in ('uid', 'gid', 'uname', 'gname')
                    and (self.issym() or not compare_ownership)):
                # Don't compare gid/uid for symlinks, or if told not to
                pass
            elif key == 'type' and not compare_type:
                pass
            elif key == 'atime' and not Globals.preserve_atime:
                pass
            elif key == 'ctime':
                pass
            elif key == 'devloc' or key == 'nlink':
                pass
            elif key == 'size' and (not self.isreg() or not compare_size):
                pass
            elif key == 'inode' and (not self.isreg() or not compare_inodes):
                pass
            elif key == 'ea' and not compare_eas:
                pass
            elif key == 'acl' and not compare_acls:
                pass
            elif key == 'win_acl' and not compare_win_acls:
                pass
            elif (key not in other.data or self.data[key] != other.data[key]):
                if key not in other.data:
                    log.Log("Second is missing key {mk}".format(mk=key),
                            verbosity)
                else:
                    log.Log(
                        "Values of key {ke} differ between this path {tp} "
                        "and other path {op}: {tv} vs. {ov}".format(
                            ke=key, tp=self.get_indexpath(),
                            op=other.get_indexpath(), tv=self.data[key],
                            ov=other.data[key]), verbosity)
                return None
        return 1


class RPath(RORPath):
    """
    Remote Path class - wrapper around a possibly non-local pathname

    This class contains a dictionary called "data" which should
    contain all the information about the file sufficient for
    identification (i.e. if two files have the the same (==) data
    dictionary, they are the same file).
    """
    # class index to make temporary files unique, see get_temp_rpath
    _temp_file_index = 0

    def __init__(self, connection, base, index=(), data=None):
        """
        RPath constructor

        connection = self.conn is the Connection the RPath will use to
        make system calls, and index is the name of the rpath used for
        comparison, and should be a tuple consisting of the parts of
        the rpath after the base split up.  For instance ("foo",
        "bar") for "foo/bar" (no base), and ("local", "bin") for
        "/usr/local/bin" if the base is "/usr".

        For the root directory "/", the index is empty and the base is
        "/".
        """
        super().__init__(index, data)
        self.conn = connection
        if base is not None:
            self.base = os.fsencode(base)  # path is always bytes
            self.path = self.path_join(self.base, *self.index)
            if data is None:
                self.setdata()
        else:
            self.base = None

    def __repr__(self):
        return ("<{cls}/{cid}:\n\tPath={rp}\n\tIndex={idx}\n"
                "\tConnection={conn}\n\tData={data}>".format(
                    cls=self.__class__.__name__, cid=id(self), rp=self,
                    idx=self.get_safeindex(), conn=self.conn, data=self.data))

    def __fspath__(self):
        """
        Just a getter for the path variable

        Fulfills the os.PathLike interface, can be overwritten by QuotedRPath
        """
        return self.path

    def __str__(self, somepath=None):
        """
        Return safely decoded version of path into the current encoding

        it's meant only for logging and outputting to user
        """
        if somepath is not None:
            # somepath should never be a string but just to be sure
            # we check before we decode it
            if isinstance(somepath, str):
                return somepath
            else:
                return somepath.decode(errors='replace')
        else:
            return self.path.decode(errors='replace')

    def __getstate__(self):
        """Return picklable state

        The rpath's connection will be encoded as its conn_number.  It
        and the other information is put in a tuple. Data and any attached
        file won't be saved.

        """
        return (self.conn.conn_number, self.base, self.index, self.data)

    def __setstate__(self, rpath_state):
        """Reproduce RPath from __getstate__ output"""
        conn_number, self.base, self.index, self.data = rpath_state
        self.conn = Globals.connection_dict[conn_number]
        self.path = self.path_join(self.base, *self.index)

    def setdata(self):
        """Set data dictionary using the wrapper"""
        self.data = self.conn.rpath.make_file_dict(self.path)
        if self.lstat():
            self.conn.rpath.setdata_local(self)

    def chmod(self, permissions, loglevel=log.WARNING):
        """Wrapper around os.chmod"""
        try:
            self.conn.os.chmod(self.path,
                               permissions & Globals.permission_mask)
        except OSError as e:
            if e.strerror == "Inappropriate file type or format" \
                    and not self.isdir():
                # Some systems throw this error if try to set sticky bit
                # on a non-directory. Remove sticky bit and try again.
                log.Log(
                    "Unable to set permissions of path {pa} to {pe:o} - "
                    "trying again without sticky bit ({ws:o})".format(
                        pa=self.path, pe=permissions,
                        ws=(permissions & 0o6777)), loglevel)
                self.conn.os.chmod(
                    self.path, permissions
                    & 0o6777 & Globals.permission_mask)
            else:
                raise
        self.data['perms'] = permissions

    def settime(self, accesstime, modtime):
        """Change file modification times"""
        log.Log("Setting time of path {pa} to modified time {md}".format(
            pa=self, md=modtime), log.DEBUG)
        try:
            self.conn.os.utime(self.path, (accesstime, modtime))
        except OverflowError:
            log.Log("Cannot change times of path {pa} to times {ti} - "
                    "problem is probably 64->32bit conversion".format(
                        pa=self, ti=(accesstime, modtime)), log.WARNING)
        else:
            self.data['atime'] = accesstime
            self.data['mtime'] = modtime

    def setmtime(self, modtime):
        """Set only modtime (access time to present)"""
        log.Log(
            lambda: "Setting time of path {pa} to modified time {mt}".format(
                pa=self, mt=modtime), log.DEBUG)
        if modtime < 0:
            log.Log("Modification time {mt} of path {pa} is"
                    "before 1970".format(mt=modtime, pa=self), log.WARNING)
        try:
            self.conn.os.utime(self.path, (int(time.time()), modtime))
        except OverflowError:
            log.Log("Cannot change path {pa} to modified time {mt} - "
                    "problem is probably 64->32bit conversion".format(
                        pa=self, mt=modtime), log.WARNING)
        except OSError:
            # It's not possible to set a modification time for
            # directories on Windows.
            if not self.isdir():
                raise
            if Globals.get_api_version() < 201:  # compat200
                if self.conn.os.name != "nt":  # doesn't work, just historical
                    raise
            else:
                if self.conn.platform.system() != "Windows":
                    raise
        else:
            self.data['mtime'] = modtime

    def chown(self, uid, gid):
        """Set file's uid and gid"""
        if self.issym():
            try:
                self.conn.os.lchown(self.path, uid, gid)
            except AttributeError:
                log.Log("Function lchown missing, cannot change ownership "
                        "of symlink {sl}".format(sl=self), log.WARNING)
        else:
            self.conn.os.chown(self.path, uid, gid)
        # uid/gid equal to -1 is ignored by chown/lchown
        if uid >= 0:
            self.data['uid'] = uid
        if gid >= 0:
            self.data['gid'] = gid

    def mkdir(self):
        log.Log("Making directory {di}".format(di=self), log.DEBUG)
        self.conn.os.mkdir(self.path)
        self.setdata()

    def makedirs(self):
        log.Log("Making directory path {dp}".format(dp=self), log.DEBUG)
        self.conn.os.makedirs(self.path)
        self.setdata()

    def rmdir(self):
        log.Log("Removing directory {di}".format(di=self), log.DEBUG)
        self.conn.os.chmod(self.path, 0o700)
        self.conn.os.rmdir(self.path)
        self.data = {'type': None}

    def listdir(self):
        """Return list of string paths returned by os.listdir"""
        path = self.path
        return self.conn.os.listdir(path)

    def symlink(self, linktext):
        """Make symlink at self.path pointing to linktext"""
        self.conn.os.symlink(linktext, self.path)
        self.setdata()
        if not self.issym():
            raise RPathException("Type of '{rp!r}' isn't '{rtype}'.".format(
                rp=self, rtype='symlink'))

    def hardlink(self, linkpath):
        """Make self into a hardlink joined to linkpath"""
        log.Log("Hard linking source path {sp} to target path {tp}".format(
            sp=self, tp=self.__str__(linkpath)), log.DEBUG)
        self.conn.os.link(linkpath, self.path)
        self.setdata()

    def mkfifo(self):
        """Make a fifo at self.path"""
        self.conn.os.mkfifo(self.path)
        self.setdata()
        if not self.isfifo():
            raise RPathException("Type of '{rp!r}' isn't '{rtype}'".format(
                rp=self, rtype='fifo'))

    def mksock(self):
        """Make a socket at self.path"""
        self.conn.rpath.make_socket_local(self)
        self.setdata()
        if not self.issock():
            raise RPathException("Type of '{rp!r}' isn't '{rtype}'".format(
                rp=self, rtype='socket'))

    def touch(self):
        """Make sure file at self.path exists"""
        log.Log("Touching file {fi}".format(fi=self), log.DEBUG)
        self.conn.open(self.path, "wb").close()
        self.setdata()
        if not self.isreg():
            raise RPathException("Type of '{rp!r}' isn't '{rtype}'".format(
                rp=self, rtype='regular'))

    def hasfullperms(self):
        """Return true if current process has full permissions on the file"""
        if self.isowner():
            return self.getperms() % 0o1000 >= 0o700
        elif self.isgroup():
            return self.getperms() % 0o100 >= 0o70
        else:
            return self.getperms() % 0o10 >= 0o7

    def readable(self):
        """Return true if current process has read permissions on the file"""
        if self.isowner():
            return self.getperms() % 0o1000 >= 0o400
        elif self.isgroup():
            return self.getperms() % 0o100 >= 0o40
        else:
            return self.getperms() % 0o10 >= 0o4

    def executable(self):
        """Return true if current process has execute permissions"""
        if self.isowner():
            return self.getperms() % 0o200 >= 0o100
        elif self.isgroup():
            return self.getperms() % 0o20 >= 0o10
        else:
            return self.getperms() % 0o2 >= 0o1

    def isowner(self):
        """Return true if current process is owner of rp or root"""
        try:
            uid = self.conn.os.getuid()
        except AttributeError:
            return True  # Windows doesn't have getuid(), so hope for the best
        return uid == 0 or \
            ('uid' in self.data and uid == self.data['uid'])

    def isgroup(self):
        """Return true if process has group of rp"""
        return ('gid' in self.data
                and self.data['gid'] in self.conn.Globals.get('process_groups'))

    def delete(self):
        """Delete file at self.path.  Recursively deletes directories."""
        log.Log("Deleting (recursively) path {pa}".format(pa=self), log.DEBUG)
        if self.isdir():
            try:
                self.rmdir()
            except os.error:
                if Globals.fsync_directories:
                    self.fsync()
                self.conn.shutil.rmtree(self.path)
        else:
            try:
                self.conn.os.unlink(self.path)
            except OSError as error:
                if error.errno in (errno.EPERM, errno.EACCES):
                    # On Windows, read-only files cannot be deleted.
                    # Remove the read-only attribute and try again.
                    self.chmod(0o700)
                    self.conn.os.unlink(self.path)
                else:
                    raise

        self.setdata()

    def contains_files(self):
        """Returns true if self (or subdir) contains any regular files."""
        log.Log("Determining if directory {di} contains files".format(di=self),
                log.DEBUG)
        if not self.isdir():
            return False
        dir_entries = self.listdir()
        for entry in dir_entries:
            child_rp = self.append(entry)
            if not child_rp.isdir():
                return True
            else:
                if child_rp.contains_files():
                    return True
        return False

    def normalize(self):
        """Return RPath canonical version of self.path

        This just means that redundant /'s will be removed, including
        the trailing one, even for directories.  ".." components will
        be retained.

        """
        newpath = self.path_join(
            b'', *[x for x in self.path.split(b"/") if x and x != b"."])
        if self.path[0:1] == b"/":
            newpath = b"/" + newpath
            if self.path[1:2] == b"/" and self.path[2:3].isalnum():  # we assume a Windows share
                newpath = b"/" + newpath
        elif not newpath:
            newpath = b"."
        return self.newpath(newpath)

    def dirsplit(self):
        """Returns a tuple of strings (dirname, basename)

        Basename is never '' unless self is root, so it is unlike
        os.path.basename.  If path is just above root (so dirname is
        root), then dirname is ''.  In all other cases dirname is not
        the empty string.  Also, dirsplit depends on the format of
        self, so basename could be ".." and dirname could be a
        subdirectory.  For an atomic relative path, dirname will be
        '.'.

        """
        normed = self.normalize()
        if normed.path.find(b"/") == -1:
            return (b".", normed.path)
        comps = normed.path.split(b"/")
        return b"/".join(comps[:-1]), comps[-1]

    def get_parent_rp(self):
        """Return new RPath of directory self is in"""
        if self.index:
            return self.__class__(self.conn, self.base, self.index[:-1])
        dirname = self.dirsplit()[0]
        if dirname:
            return self.__class__(self.conn, dirname)
        else:
            return self.__class__(self.conn, b"/")

    def get_repository_dirs(self):
        """
        Determine the base_dir of a repo based on a given path.

        The rpath can be either the repository itself, a sub-directory
        (in the mirror) or a dated increment file.
        Return a tuple made of (the identified base directory, a path index,
        the recovery type). The path index is the split relative path of the
        sub-directory to restore (or of the path corresponding to the
        increment). The type is either 'base', 'subpath', 'inc' or None if the
        given rpath couldn't be properly analyzed.

        Note that the current path can be relative but must still
        contain the name of the repository (it can't be just within it).
        """
        # get the path as a list of directories/file
        path_list = self._get_path_as_list()
        if self.isincfile():
            if (b"rdiff-backup-data" not in path_list):
                log.Log("Path '{pa}' looks like an increment but doesn't "
                        "have 'rdiff-backup-data' in its path".format(
                            pa=self), log.ERROR)
                return (self, (), None)
            else:
                data_idx = path_list.index(b"rdiff-backup-data")
                if b"increments" in path_list:
                    inc_idx = path_list.index(b"increments")
                    # base_index is the path within the increments directory,
                    # replacing the name of the increment with the name of the
                    # file it represents
                    base_index = path_list[inc_idx + 1:-1]
                    base_index.append(self.inc_basestr.split(b"/")[-1])
                elif path_list[-1].startswith(b"increments."):
                    inc_idx = len(path_list) - 1
                    base_index = []
                else:
                    inc_idx = -1
                if (inc_idx != data_idx + 1):
                    log.Log("Path '{pa}' looks like an increment but "
                            "doesn't have 'rdiff-backup-data/increments' "
                            "in its path.".format(pa=self), log.ERROR)
                    return (self, (), None)
                # base_dir is the directory above the data directory
                base_dir = RPath(self.conn, b"/".join(path_list[:data_idx]))
                return (base_dir, tuple(base_index), "inc")
        else:
            # rpath is either the base directory itself or a sub-dir of it
            if (self.lstat() and self.isdir()
                    and b"rdiff-backup-data" in self.listdir()):
                # it's a base directory, simple case...
                return (self, (), "base")
            parent_rp = self
            for element in range(1, len(path_list)):
                parent_rp = parent_rp.get_parent_rp()
                if (parent_rp.lstat() and parent_rp.isdir()
                        and b"rdiff-backup-data" in parent_rp.listdir()):
                    return (parent_rp, tuple(path_list[-element:]), "subpath")
            log.Log("Path '{pa}' couldn't be identified as being within "
                    "an existing backup repository".format(pa=self),
                    log.ERROR)
            return (self, (), None)

    def get_incfiles_list(self):
        """
        Returns list of increments whose name starts like the current file
        """
        dirname, basename = self.dirsplit()
        parent_dir = self.__class__(self.conn, dirname, ())
        if not parent_dir.isdir():
            return []  # inc directory not created yet

        inc_list = []
        for filename in parent_dir.listdir():
            inc_info = get_incfile_info(filename)
            if inc_info and inc_info[3] == basename:
                inc = parent_dir.append(filename)
                assert inc.isincfile(), (
                    "Path '{irp!r}' must be an increment file".format(irp=inc))
                inc_list.append(inc)
        return inc_list

    def newpath(self, newpath, index=()):
        """Return new RPath with the same connection but different path"""
        return self.__class__(self.conn, newpath, index)

    def append(self, *ext):
        """Return new RPath with same connection by adjoining ext"""
        return self.__class__(self.conn, self.base, self.index + ext)

    def append_path(self, ext, new_index=()):
        """Like append, but add ext to path instead of to index"""
        # ext can be a string but shouldn't hence we transform it into bytes
        return self.__class__(self.conn,
                              self.path_join(self.base, os.fsencode(ext)),
                              new_index)

    def new_index(self, index):
        """Return similar RPath but with new index"""
        return self.__class__(self.conn, self.base, index)

    def new_index_empty(self, index):
        """Return similar RPath with given index, but initialize to empty"""
        return self.__class__(self.conn, self.base, index, {'type': None})

    def get_temp_rpath(self, sibling=False):
        """Return new temp rpath in given or parent directory"""
        assert self.conn is Globals.local_connection, (
            "Function must be called locally not over {conn}.".format(
                conn=self.conn))

        # recursion if current rpath isn't a directory or if explicitly asked
        if sibling or not self.isdir():
            return self.get_parent_rp().get_temp_rpath()

        # we have to create our own "uniqueness" as tempfile.mktemp is
        # obsolete and we just want a name agnostic regarding file vs. dir
        while True:
            if self.__class__._temp_file_index > 100000000:
                log.Log("Resetting tempfile index", log.NOTE)
                self.__class__._temp_file_index = 0

            # When the file system hosting the rdiff-backup-data directory
            # is full and when the --tempdir flag is defined, attempt to save
            # temporary files on a different path / file system.
            if tempfile.tempdir and (shutil.disk_usage(self.path).free == 0):
                # If tempfile.tempdir is manually passed in via the --tempdir
                # cli flag, it defaults being a bytes string, as such we need to
                # convert the target path to a string first
                tempdir = os.fsdecode(tempfile.tempdir)
            else:
                tempdir = None

            _tf = 'rdiff-backup.tmp.{index:d}'.format(index=self.__class__._temp_file_index)
            if not tempdir:
                tf = self.append(_tf)
            else:
                tf = os.path.join(tempdir, _tf)
            self.__class__._temp_file_index += 1
            if not tf.lstat():
                return tf

    def open(self, mode, compress=None):
        """Return open file.  Supports modes "w" and "r".

        If compress is true, data written/read will be gzip
        compressed/decompressed on the fly.  The extra complications
        below are for security reasons - try to make the extent of the
        risk apparent from the remote call.

        """
        if self.conn is Globals.local_connection:
            if compress:
                return gzip.GzipFile(self.path, mode)
            else:
                return open(self.path, mode)

        if compress:
            if mode == "r" or mode == "rb":
                return self.conn.rpath.gzip_open_local_read(self)
            else:
                return self.conn.gzip.GzipFile(self.path, mode)
        else:
            if mode == "r" or mode == "rb":
                return self.conn.rpath.open_local_read(self)
            else:
                return self.conn.open(self.path, mode)

    def write_from_fileobj(self, fp, compress=None):
        """Reads fp and writes to self.path.  Closes both when done

        If compress is true, fp will be gzip compressed before being
        written to self.  Returns closing value of fp.

        """
        log.Log("Writing file object to file {fi}".format(fi=self), log.DEBUG)
        assert not self.lstat(), "File '{rp!r}' already exists".format(rp=self)
        outfp = self.open("wb", compress=compress)
        copyfileobj(fp, outfp)
        if outfp.close():
            raise RPathException("Error closing file")
        self.setdata()
        return fp.close()

    def write_string(self, s, compress=None):
        """Write string s into rpath"""
        assert not self.lstat(), "File '{rp!r}' already exists".format(rp=self)
        outfp = self.open("w", compress=compress)
        outfp.write(s)
        outfp.close()
        self.setdata()

    def write_bytes(self, s, compress=None):
        """Write data s into rpath"""
        assert not self.lstat(), "File '{rp!r}' already exists".format(rp=self)
        outfp = self.open("wb", compress=compress)
        outfp.write(s)
        outfp.close()
        self.setdata()

    def isincfile(self):
        """Return true if path looks like an increment file

        Also sets various inc information used by the *inc* functions.

        """
        if self.index:
            basename = self.index[-1]
        else:
            basename = self.base

        inc_info = get_incfile_info(basename)

        if inc_info:
            self.inc_compressed, self.inc_timestr, \
                self.inc_type, self.inc_basestr = inc_info
            return 1
        else:
            return None

    def isinccompressed(self):
        """Return true if inc file is compressed"""
        return self.inc_compressed

    def getinctype(self):
        """Return type of an increment file"""
        return self.inc_type

    def getinctime(self):
        """Return time in seconds of an increment file"""
        return Time.bytestotime(self.inc_timestr)

    def getincbase(self):
        """Return the base filename of an increment file in rp form"""
        if self.index:
            return self.__class__(self.conn, self.base,
                                  self.index[:-1] + (self.inc_basestr, ))
        else:
            return self.__class__(self.conn, self.inc_basestr)

    def getincbase_bname(self):
        """Return the base filename as bytes of an increment file"""
        rp = self.getincbase()
        if rp.index:
            return rp.index[-1]
        else:
            return rp.dirsplit()[1]

    def makedev(self, type, major, minor):
        """Make a special file with specified type, and major/minor nums"""
        if type == 'c':
            mode = stat.S_IFCHR | 0o600
        elif type == 'b':
            mode = stat.S_IFBLK | 0o600
        else:
            raise RPathException
        try:
            self.conn.os.mknod(self.path, mode,
                               self.conn.os.makedev(major, minor))
        except OSError as exc:
            log.Log("Unable to mknod device file '{df}' due to "
                    "exception '{ex}', using touch instead".format(
                        df=self, ex=exc), log.INFO)
            self.touch()
        self.setdata()

    def fsync(self, fp=None):
        """fsync the current file or directory

        If fp is none, get the file description by opening the file.
        This can be useful for directories.

        """
        if Globals.do_fsync:
            if not fp:
                self.conn.rpath.RPath.fsync_local(self)
            else:
                os.fsync(fp.fileno())

    # @API(RPath.fsync_local, 200)
    def fsync_local(self, thunk=None):
        """fsync current file, run locally

        If thunk is given, run it before syncing but after gathering
        the file's file descriptor.

        """
        assert self.conn is Globals.local_connection, (
            "Function must be called locally not over {conn}.".format(
                conn=self.conn))
        try:
            fd = os.open(self.path, os.O_RDONLY)
            os.fsync(fd)
            os.close(fd)
        except OSError as e:
            if 'fd' in locals():
                os.close(fd)
            if (e.errno not in (errno.EPERM, errno.EACCES, errno.EBADF)) or self.isdir():
                raise

            # Maybe the system doesn't like read-only fsyncing.
            # However, to open RDWR, we may need to alter permissions
            # temporarily.
            if self.hasfullperms():
                oldperms = None
            else:
                oldperms = self.getperms()
                if not oldperms:  # self.data['perms'] is probably out of sync
                    self.setdata()
                    oldperms = self.getperms()
                self.chmod(0o700)
            fd = os.open(self.path, os.O_RDWR)
            if oldperms is not None:
                self.chmod(oldperms)
            if thunk:
                thunk()
            os.fsync(fd)  # Sync after we switch back permissions!
            os.close(fd)

    def fsync_with_dir(self, fp=None):
        """fsync self and directory self is under"""
        self.fsync(fp)
        if Globals.fsync_directories:
            self.get_parent_rp().fsync()

    def get_bytes(self, compressed=None):
        """Open file as a regular file, read data, close, return data"""
        fp = self.open("rb", compressed)
        d = fp.read()
        fp.close()
        return d

    def get_string(self, compressed=None):
        """Open file as a regular file, read string, close, return string"""
        fp = self.open("r", compressed)
        s = fp.read()
        fp.close()
        if isinstance(s, bytes) or isinstance(s, bytearray):
            s = s.decode()
        return s

    def get_acl(self):
        """Return access control list object, setting if necessary"""
        try:
            acl_meta = self.data['acl']
        except KeyError:
            acl_meta = self.data['acl'] = acl_posix.get_meta(self)
        return acl_meta

    def write_acl(self, acl_meta, map_names=1):
        """Change access control list of rp

        If map_names is true, map the ids in acl by user/group names.

        """
        acl_meta.write_to_rp(self, map_names)
        self.data['acl'] = acl_meta

    def get_ea(self):
        """Return extended attributes object, setting if necessary"""
        try:
            ea_meta = self.data['ea']
        except KeyError:
            ea_meta = self.data['ea'] = ea.get_meta(self)
        return ea_meta

    def write_ea(self, ea_meta):
        """Change extended attributes of rp"""
        ea_meta.write_to_rp(self)
        self.data['ea'] = ea_meta

    def write_carbonfile(self, cfile):
        """Write new carbon data to self."""
        if not cfile:
            return
        log.Log("Writing carbon data to path {pa}".format(pa=self), log.DEBUG)
        from Carbon.File import FSSpec
        from Carbon.File import FSRef
        import Carbon.Files
        fsobj = FSSpec(self.path)
        finderinfo = fsobj.FSpGetFInfo()
        finderinfo.Creator = cfile['creator']
        finderinfo.Type = cfile['type']
        finderinfo.Location = cfile['location']
        finderinfo.Flags = cfile['flags']
        fsobj.FSpSetFInfo(finderinfo)
        """Write Creation Date to self (if stored in metadata)."""
        try:
            cdate = cfile['createDate']
            fsref = FSRef(fsobj)
            cataloginfo, d1, d2, d3 = fsref.FSGetCatalogInfo(
                Carbon.Files.kFSCatInfoCreateDate)
            cataloginfo.createDate = (0, cdate, 0)
            fsref.FSSetCatalogInfo(Carbon.Files.kFSCatInfoCreateDate,
                                   cataloginfo)
            self.set_carbonfile(cfile)
        except KeyError:
            self.set_carbonfile(cfile)

    def get_resource_fork(self):
        """Return resource fork data, setting if necessary"""
        assert self.isreg(), (
            "Path '{rp}' must point to a regular file.".format(rp=self))
        try:
            rfork = self.data['resourcefork']
        except KeyError:
            try:
                rfork_fp = self.conn.open(
                    os.path.join(self.path, b'..namedfork', b'rsrc'), 'rb')
                rfork = rfork_fp.read()
                rfork_fp.close()
            except OSError:
                rfork = b''
            self.data['resourcefork'] = rfork
        return rfork

    def write_resource_fork(self, rfork_data):
        """Write new resource fork to self"""
        log.Log("Writing resource fork to path {pa}".format(pa=self), log.DEBUG)
        fp = self.conn.open(
            os.path.join(self.path, b'..namedfork', b'rsrc'), 'wb')
        fp.write(rfork_data)
        fp.close()
        self.set_resource_fork(rfork_data)

    def get_win_acl(self):
        """Return Windows access control list, setting if necessary"""
        try:
            acl_meta = self.data['win_acl']
        except KeyError:
            acl_meta = self.data['win_acl'] = acl_win.get_meta(self)
        return acl_meta

    def write_win_acl(self, acl_meta):
        """Change access control list of rp"""
        acl_win.write_meta(self, acl_meta)
        self.data['win_acl'] = acl_meta

    def _debug_consistency(self):
        """Raise an error if consistency of rp broken

        This is useful for debugging when the cache and disk get out
        of sync and you need to find out where it happened.

        """
        temptype = self.data['type']
        self.setdata()
        if temptype != self.data['type']:
            print("\nPath: {rp}\nhas cached an inconsistent type\n"
                  "Old: {otype} --> New: {ntype}\n".format(
                      rp=self, otype=temptype, ntype=self.data['type']))

    def _get_path_as_list(self):
        """
        Return the complete path (base and index) as list of file names.
        """
        return self.path.split(b"/")


class MaybeGzip:
    """
    Represent a file object that may or may not be compressed

    We don't want to compress 0 length files.  This class lets us
    delay the opening of the file until either the first write (so we
    know it has data and should be compressed), or close (when there's
    no data).
    """

    def __init__(self, base_rp, callback=None):
        """Return file-like object with filename based on base_rp"""
        assert not base_rp.lstat(), (
            "Path '{rp}' shouldn't already exist.".format(rp=base_rp))
        self.base_rp = base_rp
        # callback will be called with final write rp as only argument
        self.callback = callback
        self.fileobj = None  # Will be None unless data gets written
        self.closed = 0

    def __getattr__(self, name):
        if name == 'fileno':
            return self.fileobj.fileno
        else:
            raise AttributeError(name)

    def write(self, buf):
        """Write buf to fileobj"""
        if isinstance(buf, str):
            buf = buf.encode()
        if self.fileobj:
            return self.fileobj.write(buf)
        if not buf:
            return

        new_rp = self._get_gzipped_rp()
        if self.callback:
            self.callback(new_rp)
        self.fileobj = new_rp.open("wb", compress=1)
        return self.fileobj.write(buf)

    def close(self):
        """Close related fileobj, pass return value"""
        if self.closed:
            return None
        self.closed = 1
        if self.fileobj:
            return self.fileobj.close()
        if self.callback:
            self.callback(self.base_rp)
        self.base_rp.touch()

    def _get_gzipped_rp(self):
        """Return gzipped rp by adding .gz to base_rp"""
        if self.base_rp.index:
            newind = self.base_rp.index[:-1] + (
                self.base_rp.index[-1] + b'.gz', )
            return self.base_rp.new_index(newind)
        else:
            return self.base_rp.append_path(b'.gz')


class _RPathFileHook:
    """Look like a file, but add closing hook"""

    def __init__(self, file, closing_thunk):
        self.file = file
        self.closing_thunk = closing_thunk

    def read(self, length=-1):
        return self.file.read(length)

    def write(self, buf):
        return self.file.write(buf)

    def close(self):
        """Close file and then run closing thunk"""
        result = self.file.close()
        self.closing_thunk()
        return result


def copyfileobj(inputfp, outputfp):
    """Copies file inputfp to outputfp in blocksize intervals"""
    blocksize = Globals.blocksize

    sparse = False
    """Negative seeks are not supported by GzipFile"""
    compressed = False
    if isinstance(outputfp, gzip.GzipFile):
        compressed = True

    while 1:
        inbuf = inputfp.read(blocksize)
        if not inbuf:
            break

        buflen = len(inbuf)
        if not compressed and inbuf == b"\x00" * buflen:
            outputfp.seek(buflen, os.SEEK_CUR)
            # flag sparse=True, that we seek()ed, but have not written yet
            # The filesize is wrong until we write
            sparse = True
        else:
            outputfp.write(inbuf)
            # We wrote, so clear sparse.
            sparse = False

    if sparse:
        outputfp.seek(-1, os.SEEK_CUR)
        outputfp.write(b"\x00")


def move(rpin, rpout):
    """Move rpin to rpout, renaming if possible"""
    try:
        rename(rpin, rpout)
    except os.error:
        copy(rpin, rpout)
        rpin.delete()


def copy(rpin, rpout, compress=0):
    """Copy RPath or RORPath rpin to rpout.  Works for symlinks, dirs, etc.

    Returns close value of input for regular file, which can be used
    to pass hashes on.
    """
    log.Log("Regular copying input path {ip} to output path {op}".format(
        ip=rpin, op=rpout), log.DEBUG)
    if not rpin.lstat():
        if rpout.lstat():
            rpout.delete()
        return

    if rpout.lstat():
        if rpin.isreg() or not cmp(rpin, rpout):
            rpout.delete()  # easier to write than compare
        else:
            return

    if rpin.isreg():
        return copy_reg_file(rpin, rpout, compress)
    elif rpin.isdir():
        rpout.mkdir()
    elif rpin.issym():
        # some systems support permissions for symlinks, but
        # only by setting at creation via the umask
        if Globals.symlink_perms:
            orig_umask = os.umask(0o777 & ~rpin.getperms())
        rpout.symlink(rpin.readlink())
        if Globals.symlink_perms:
            os.umask(orig_umask)  # restore previous umask
    elif rpin.isdev():
        dev_type, major, minor = rpin.getdevnums()
        rpout.makedev(dev_type, major, minor)
    elif rpin.isfifo():
        rpout.mkfifo()
    elif rpin.issock():
        rpout.mksock()
    else:
        raise RPathException("File '{rp!r}' has unknown type.".format(rp=rpin))


# @API(copy_reg_file, 200)
def copy_reg_file(rpin, rpout, compress=0):
    """Copy regular file rpin to rpout, possibly avoiding connection"""
    try:
        if (rpout.conn is rpin.conn
                and rpout.conn is not Globals.local_connection):
            v = rpout.conn.rpath.copy_reg_file(rpin.path, rpout.path, compress)
            rpout.setdata()
            return v
    except AttributeError:
        pass
    try:
        return rpout.write_from_fileobj(rpin.open("rb"), compress=compress)
    except OSError as e:
        if (e.errno == errno.ERANGE):
            log.Log.FatalError(
                "'OSError - Result too large' while reading file {fi}. "
                "If you are using a Mac, this is probably "
                "the result of HFS+ filesystem corruption. "
                "Please exclude this file from your backup "
                "before proceeding".format(fi=rpin))
        else:
            raise


def cmp(rpin, rpout):
    """True if rpin has the same data as rpout

    does not compare file ownership, permissions, or times, or
    examine the contents of a directory.

    """
    _check_for_files(rpin, rpout)
    if rpin.isreg():
        if not rpout.isreg():
            return None
        fp1, fp2 = rpin.open("rb"), rpout.open("rb")
        result = _cmp_file_obj(fp1, fp2)
        if fp1.close() or fp2.close():
            raise RPathException("Error closing file")
        return result
    elif rpin.isdir():
        return rpout.isdir()
    elif rpin.issym():
        return rpout.issym() and (rpin.readlink() == rpout.readlink())
    elif rpin.isdev():
        return rpout.isdev() and (rpin.getdevnums() == rpout.getdevnums())
    elif rpin.isfifo():
        return rpout.isfifo()
    elif rpin.issock():
        return rpout.issock()
    else:
        raise RPathException("File {rp!r} has unknown type".format(rp=rpin))


def copy_attribs(rpin, rpout):
    """Change file attributes of rpout to match rpin

    Only changes the chmoddable bits, uid/gid ownership, and
    timestamps, so both must already exist.

    """
    log.Log("Copying attributes from path {fp!r} to path {tp!r}".format(
        fp=rpin, tp=rpout), log.DEBUG)
    assert rpin.lstat() == rpout.lstat() or rpin.isspecial(), (
        "Input '{irp!r}' and output '{orp!r}' paths must exist likewise, "
        "or input be special.".format(irp=rpin, orp=rpout))
    assert rpout.conn is Globals.local_connection, (
        "Function works locally not over '{conn}'.".format(conn=rpout.conn))
    if Globals.change_ownership:
        rpout.chown(*map_owners.map_rpath_owner(rpin))
    if Globals.eas_write:
        rpout.write_ea(rpin.get_ea())
    if rpin.issym():
        return  # symlinks don't have times or perms
    if (Globals.resource_forks_write and rpin.isreg()
            and rpin.has_resource_fork()):
        rpout.write_resource_fork(rpin.get_resource_fork())
    if (Globals.carbonfile_write and rpin.isreg() and rpin.has_carbonfile()):
        rpout.write_carbonfile(rpin.get_carbonfile())
    rpout.chmod(rpin.getperms())
    if Globals.acls_write:
        rpout.write_acl(rpin.get_acl())
    if not rpin.isdev():
        rpout.setmtime(rpin.getmtime())
    if Globals.win_acls_write:
        rpout.write_win_acl(rpin.get_win_acl())


def copy_attribs_inc(rpin, rpout):
    """Change file attributes of rpout to match rpin

    Like above, but used to give increments the same attributes as the
    originals.  Therefore, don't copy all directory acl and
    permissions.

    """
    log.Log("Copying inc attributes from path {fp!r} to path {tp!r}".format(
        fp=rpin, tp=rpout), log.DEBUG)
    _check_for_files(rpin, rpout)
    if Globals.change_ownership:
        rpout.chown(*rpin.getuidgid())
    if Globals.eas_write:
        rpout.write_ea(rpin.get_ea())
    if rpin.issym():
        return  # symlinks don't have times or perms
    if (Globals.resource_forks_write and rpin.isreg()
            and rpin.has_resource_fork() and rpout.isreg()):
        rpout.write_resource_fork(rpin.get_resource_fork())
    if (Globals.carbonfile_write and rpin.isreg() and rpin.has_carbonfile()
            and rpout.isreg()):
        rpout.write_carbonfile(rpin.get_carbonfile())
    if rpin.isdir() and not rpout.isdir():
        rpout.chmod(rpin.getperms() & 0o777)
    else:
        rpout.chmod(rpin.getperms())
    if Globals.acls_write:
        rpout.write_acl(rpin.get_acl(), map_names=0)
    if not rpin.isdev():
        rpout.setmtime(rpin.getmtime())
    # TODO check why win_acls aren't copied


def copy_with_attribs(rpin, rpout, compress=0):
    """Copy file and then copy over attributes"""
    copy(rpin, rpout, compress)
    if rpin.lstat():
        copy_attribs(rpin, rpout)


def rename(rp_source, rp_dest):
    """Rename rp_source to rp_dest"""
    assert rp_source.conn is rp_dest.conn, (
        "Source '{srp!r}' and destination '{drp!r}' paths must have the "
        "same connection for renaming.".format(srp=rp_source, drp=rp_dest))
    log.Log(lambda: "Renaming from path {fp} to path {tp}".format(
        fp=rp_source, tp=rp_dest), log.DEBUG)
    if not rp_source.lstat():
        rp_dest.delete()
    else:
        if (rp_dest.lstat() and rp_source.getinode() == rp_dest.getinode()
                and rp_source.getinode() != 0):
            log.Log("Attempt to rename over same inode: from path "
                    "{fp} to path {tp}".format(
                        fp=rp_source, tp=rp_dest), log.WARNING)
            # You can't rename one hard linked file over another
            rp_source.delete()
        else:
            try:
                rp_source.conn.os.rename(rp_source.path, rp_dest.path)
            except OSError as error:
                # XXX errno.EINVAL and len(rp_dest.path) >= 260 indicates
                # pathname too long on Windows
                if error.errno == errno.EXDEV and rp_source.issym():
                    # On Linux, ZFS and quota project raise errno.EXDEV
                    # Invalid cross-device link
                    rp_source.conn.os.symlink(rp_source.readlink(), rp_dest.path)
                    rp_source.conn.os.unlink(rp_source.path)
                elif error.errno == errno.EEXIST:
                    # On Windows, files can't be renamed on top of an existing file
                    rp_source.conn.os.chmod(rp_dest.path, 0o700)
                    rp_source.conn.os.unlink(rp_dest.path)
                    rp_source.conn.os.rename(rp_source.path, rp_dest.path)
                else:
                    log.Log("Exception '{ex}' while renaming from path {fp} "
                            "to path {tp}".format(
                                ex=error, fp=rp_source, tp=rp_dest), log.ERROR)
                    raise

        rp_dest.data = rp_source.data
        rp_source.data = {'type': None}


# @API(make_file_dict, 200)
def make_file_dict(filename):
    """Generate the data dictionary for the given RPath

    This is a global function so that os.name can be called locally,
    thus avoiding network lag and so that we only need to send the
    filename over the network, thus avoiding the need to pickle an
    (incomplete) rpath object.
    """

    try:
        statblock = os.lstat(filename)
    except (FileNotFoundError, NotADirectoryError, PermissionError):
        # FIXME not sure if this shouldn't trigger a warning but doing it
        # generates (too) many messages during the tests
        # log.Log("Missing file '{mf}' couldn't be assessed".format(
        #             mf=filename), log.WARNING)
        # FIXME perhaps we should have a different type/flag for this case?
        return {'type': None}
    data = {}
    mode = statblock[stat.ST_MODE]

    if stat.S_ISREG(mode):
        type_ = 'reg'
    elif stat.S_ISDIR(mode):
        type_ = 'dir'
    elif stat.S_ISCHR(mode):
        type_ = 'dev'
        s = statblock.st_rdev
        data['devnums'] = ('c', os.major(s), os.minor(s))
    elif stat.S_ISBLK(mode):
        type_ = 'dev'
        s = statblock.st_rdev
        data['devnums'] = ('b', os.major(s), os.minor(s))
    elif stat.S_ISFIFO(mode):
        type_ = 'fifo'
    elif stat.S_ISLNK(mode):
        type_ = 'sym'
        data['linkname'] = os.readlink(filename)
    elif stat.S_ISSOCK(mode):
        type_ = 'sock'
    else:
        raise C.UnknownFileError(filename)
    data['type'] = type_
    data['size'] = statblock[stat.ST_SIZE]
    data['perms'] = stat.S_IMODE(mode)
    data['uid'] = statblock[stat.ST_UID]
    data['gid'] = statblock[stat.ST_GID]
    data['inode'] = statblock[stat.ST_INO]
    data['devloc'] = statblock[stat.ST_DEV]
    data['nlink'] = statblock[stat.ST_NLINK]

    if os.name == 'nt':
        try:
            attribs = win32api.GetFileAttributes(os.fsdecode(filename))
        except pywintypes.error as exc:
            if (exc.args[0] == 32):  # file in use
                # we could also ignore with: return {'type': None}
                # but this approach seems to be better handled
                attribs = 0
            else:
                # we replace the specific Windows exception by a generic
                # one also understood by a potential Linux client/server
                raise OSError(None, exc.args[1] + " - " + exc.args[2],
                              filename, exc.args[0]) from None
        if attribs & win32con.FILE_ATTRIBUTE_REPARSE_POINT:
            data['type'] = 'sym'
            data['linkname'] = None

    if not (type_ == 'sym' or type_ == 'dev'):
        # mtimes on symlinks and dev files don't work consistently
        data['mtime'] = int(statblock[stat.ST_MTIME])
        data['atime'] = int(statblock[stat.ST_ATIME])
        data['ctime'] = int(statblock[stat.ST_CTIME])
    return data


# @API(make_socket_local, 200)
def make_socket_local(rpath):
    """Make a local socket at the given path

    This takes an rpath so that it will be checked by Security.
    (Miscellaneous strings will not be.)
    """
    assert rpath.conn is Globals.local_connection, (
        "Function works locally not over '{conn}'.".format(conn=rpath.conn))
    rpath.conn.os.mknod(rpath.path, stat.S_IFSOCK)


# @API(gzip_open_local_read, 200)
def gzip_open_local_read(rpath):
    """Return open GzipFile.  See security note directly above"""
    assert rpath.conn is Globals.local_connection, (
        "Function works locally not over '{conn}'.".format(conn=rpath.conn))
    return gzip.GzipFile(rpath.path, "rb")


# @API(open_local_read, 200)
def open_local_read(rpath):
    """Return open file (provided for security reasons)"""
    assert rpath.conn is Globals.local_connection, (
        "Function works locally not over '{conn}'.".format(conn=rpath.conn))
    return open(rpath.path, "rb")


def get_incfile_info(basename):
    """Returns None or tuple of
    (is_compressed, timestr, type, and basename)"""
    dotsplit = basename.split(b'.')
    if dotsplit[-1] == b'gz':
        compressed = 1
        if len(dotsplit) < 4:
            return None
        timestring, ext = dotsplit[-3:-1]
    else:
        compressed = None
        if len(dotsplit) < 3:
            return None
        timestring, ext = dotsplit[-2:]
    if Time.bytestotime(timestring) is None:
        return None
    if not (ext == b"snapshot" or ext == b"dir" or ext == b"missing"
            or ext == b"diff" or ext == b"data"):
        return None
    if compressed:
        basestr = b'.'.join(dotsplit[:-3])
    else:
        basestr = b'.'.join(dotsplit[:-2])
    return (compressed, timestring, ext, basestr)


# @API(delete_dir_no_files, 200)
def delete_dir_no_files(rp):
    """Deletes the directory at rp.path if empty. Raises if the
    directory contains files."""
    assert rp.isdir(), (
        "Path '{rp}' must be a directory to be deleted.".format(rp=rp))
    if rp.contains_files():
        raise RPathException("Directory contains files.")
    rp.delete()


# @API(setdata_local, 200)
def setdata_local(rpath):
    """Set eas/acls, uid/gid, resource fork in data dictionary

    This is a global function because it must be called locally, since
    these features may exist or not depending on the connection.

    """
    assert rpath.conn is Globals.local_connection, (
        "Function must be called locally not over {conn}.".format(
            conn=rpath.conn))
    reset_perms = False
    if (Globals.process_uid != 0 and not rpath.readable() and rpath.isowner()):
        reset_perms = True
        rpath.chmod(0o400 | rpath.getperms())

    rpath.data['uname'] = usrgrp.uid2uname(rpath.data['uid'])
    rpath.data['gname'] = usrgrp.gid2gname(rpath.data['gid'])
    if Globals.eas_conn:
        rpath.data['ea'] = ea.get_meta(rpath)
    if Globals.acls_conn:
        rpath.data['acl'] = acl_posix.get_meta(rpath)
    if Globals.win_acls_conn:
        rpath.data['win_acl'] = acl_win.get_meta(rpath)
    if Globals.resource_forks_conn and rpath.isreg():
        rpath.get_resource_fork()
    if Globals.carbonfile_conn and rpath.isreg():
        rpath.data['carbonfile'] = _carbonfile_get(rpath)

    if reset_perms:
        rpath.chmod(rpath.getperms() & ~0o400)


def _carbonfile_get(rp):
    """Return carbonfile value for local rpath"""
    # Note, after we drop support for Mac OS X 10.0 - 10.3, it will no longer
    # be necessary to read the finderinfo struct since it is a strict subset
    # of the data stored in the com.apple.FinderInfo extended attribute
    # introduced in 10.4. Indeed, FSpGetFInfo() is deprecated on 10.4.
    from Carbon.File import FSSpec
    from Carbon.File import FSRef
    import Carbon.Files
    import MacOS
    try:
        fsobj = FSSpec(rp.path)
        finderinfo = fsobj.FSpGetFInfo()
        cataloginfo, d1, d2, d3 = FSRef(fsobj).FSGetCatalogInfo(
            Carbon.Files.kFSCatInfoCreateDate)
        cfile = {
            'creator': finderinfo.Creator,
            'type': finderinfo.Type,
            'location': finderinfo.Location,
            'flags': finderinfo.Flags,
            'createDate': cataloginfo.createDate[1]
        }
        return cfile
    except MacOS.Error:
        log.Log("Cannot read carbonfile information from path {pa}".format(
            pa=rp), log.WARNING)
        return None


def _cmp_file_attribs(rp1, rp2):
    """True if rp1 has the same file attributes as rp2

    Does not compare file access times.  If not changing
    ownership, do not check user/group id.

    """
    _check_for_files(rp1, rp2)
    if Globals.change_ownership and rp1.getuidgid() != rp2.getuidgid():
        result = None
    elif rp1.getperms() != rp2.getperms():
        result = None
    elif rp1.issym() and rp2.issym():  # Don't check times for some types
        result = 1
    elif rp1.isblkdev() and rp2.isblkdev():
        result = 1
    elif rp1.ischardev() and rp2.ischardev():
        result = 1
    else:
        result = ((rp1.getctime() == rp2.getctime())
                  and (rp1.getmtime() == rp2.getmtime()))
    log.Log("Compare attribs of paths {p1} and {p2} gives result: {re}".format(
            p1=rp1, p2=rp2, re=result), log.DEBUG)
    return result


def _cmp_file_obj(fp1, fp2):
    """True if file objects fp1 and fp2 contain same data, used for testing"""
    blocksize = Globals.blocksize
    while 1:
        buf1 = fp1.read(blocksize)
        buf2 = fp2.read(blocksize)
        if buf1 != buf2:
            return None
        elif not buf1:
            return 1


def _check_for_files(*rps):
    """Make sure that all the rps exist, raise error if not"""
    for rp in rps:
        if not rp.lstat():
            raise RPathException("File {rp} does not exist".format(rp=rp))
