# Copyright 2008 Fred Gansevles <fred@betterbe.com>
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

import re
import os
from . import C, metadata, rorpiter, rpath, log

try:
    from win32security import (
        AdjustTokenPrivileges,
        DACL_SECURITY_INFORMATION,
        GetTokenInformation,
        GROUP_SECURITY_INFORMATION,
        INHERIT_ONLY_ACE,
        LookupPrivilegeValue,
        OpenProcessToken,
        OWNER_SECURITY_INFORMATION,
        SACL_SECURITY_INFORMATION,
        SDDL_REVISION_1,
        SE_BACKUP_NAME,
        SE_DACL_PROTECTED,
        SE_FILE_OBJECT,
        SE_PRIVILEGE_ENABLED,
        SE_RESTORE_NAME,
        SE_SECURITY_NAME,
        TOKEN_ADJUST_PRIVILEGES,
        TokenPrivileges,
        TOKEN_QUERY,
    )
    import pywintypes
except ImportError:
    GROUP_SECURITY_INFORMATION = 0
    OWNER_SECURITY_INFORMATION = 0
    DACL_SECURITY_INFORMATION = 0

    pywintypes = None


class ACL:
    flags = (GROUP_SECURITY_INFORMATION | OWNER_SECURITY_INFORMATION
             | DACL_SECURITY_INFORMATION)

    def __init__(self, index=()):
        self.__acl = b""
        self.index = index

    def get_indexpath(self):
        return self.index and b'/'.join(self.index) or b'.'

    def load_from_rp(self, rp, skip_inherit_only=True):
        self.index = rp.index

        # Sometimes, we are asked to load from an rpath when ACL's
        # are not supported. Ignore the request in this case.
        if not pywintypes:
            return

        try:
            sd = rp.conn.win32security.GetNamedSecurityInfo(os.fsdecode(rp.path),
                                                            SE_FILE_OBJECT, ACL.flags)
        except (OSError, IOError, pywintypes.error) as exc:
            log.Log(
                "Warning: unable to read ACL from %s: %s" % (repr(rp.path),
                                                             exc), 4)
            return

        if skip_inherit_only:
            # skip the inherit_only aces
            acl = sd.GetSecurityDescriptorDacl()
            if acl:
                n = acl.GetAceCount()
                # traverse the ACL in reverse, so the indices stay correct
                while n:
                    n -= 1
                    ace_flags = acl.GetAce(n)[0][1]
                    if ace_flags & INHERIT_ONLY_ACE:
                        acl.DeleteAce(n)
            sd.SetSecurityDescriptorDacl(1, acl, 0)

            if ACL.flags & SACL_SECURITY_INFORMATION:
                acl = sd.GetSecurityDescriptorSacl()
                if acl:
                    n = acl.GetAceCount()
                    # traverse the ACL in reverse, so the indices stay correct
                    while n:
                        n -= 1
                        ace_flags = acl.GetAce(n)[0][1]
                        if ace_flags & INHERIT_ONLY_ACE:
                            acl.DeleteAce(n)
                    sd.SetSecurityDescriptorSacl(1, acl, 0)

        if not sd.GetSecurityDescriptorDacl():
            sd.SetSecurityDescriptorDacl(0, None, 0)
        if (ACL.flags & SACL_SECURITY_INFORMATION) and not sd.GetSecurityDescriptorSacl():
            sd.SetSecurityDescriptorSacl(0, None, 0)

        try:
            self.__acl = \
                rp.conn.win32security.ConvertSecurityDescriptorToStringSecurityDescriptor(sd,
                                                                                          SDDL_REVISION_1,
                                                                                          ACL.flags)
        except (OSError, IOError, pywintypes.error) as exc:
            log.Log(
                "Warning: unable to convert ACL from %s to string: %s" % (repr(
                    rp.path), exc), 4)
            self.__acl = ''
        self.__acl = os.fsencode(self.__acl)

    def clear_rp(self, rp):
        # not sure how to interpret this
        # I'll just clear all acl-s from rp.path
        try:
            sd = rp.conn.win32security. \
                GetNamedSecurityInfo(os.fsdecode(rp.path), SE_FILE_OBJECT, ACL.flags)
        except (OSError, IOError, pywintypes.error) as exc:
            log.Log(
                "Warning: unable to read ACL from %s for clearing: %s" % (repr(
                    rp.path), exc), 4)
            return

        acl = sd.GetSecurityDescriptorDacl()
        if acl:
            n = acl.GetAceCount()
            # traverse the ACL in reverse, so the indices stay correct
            while n:
                n -= 1
                acl.DeleteAce(n)
            sd.SetSecurityDescriptorDacl(0, acl, 0)

        if ACL.flags & SACL_SECURITY_INFORMATION:
            acl = sd.GetSecurityDescriptorSacl()
            if acl:
                n = acl.GetAceCount()
                # traverse the ACL in reverse, so the indices stay correct
                while n:
                    n -= 1
                    acl.DeleteAce(n)
                sd.SetSecurityDescriptorSacl(0, acl, 0)

        try:
            rp.conn.win32security. \
                SetNamedSecurityInfo(os.fsdecode(rp.path),
                                     SE_FILE_OBJECT,
                                     ACL.flags,
                                     sd.GetSecurityDescriptorOwner(),
                                     sd.GetSecurityDescriptorGroup(),
                                     sd.GetSecurityDescriptorDacl(),
                                     (ACL.flags & SACL_SECURITY_INFORMATION)
                                     and sd.GetSecurityDescriptorSacl() or None)
        except (OSError, IOError, pywintypes.error) as exc:
            log.Log(
                "Warning: unable to set ACL on %s after clearing: %s" % (repr(
                    rp.path), exc), 4)

    def write_to_rp(self, rp):
        if not self.__acl:
            return

        try:
            sd = rp.conn.win32security. \
                ConvertStringSecurityDescriptorToSecurityDescriptor(
                    os.fsdecode(self.__acl),
                    SDDL_REVISION_1)
        except (OSError, IOError, pywintypes.error) as exc:
            log.Log(
                "Warning: unable to convert string %s to ACL: %s" % (repr(
                    self.__acl), exc), 4)

        # Enable next block of code for dirs after we have a mechanism in
        # backup.py (and similar) to do a first pass to see if a directory
        # has SE_DACL_PROTECTED. In that case, we will need to
        #       1) dest_rorp.write_win_acl(source_rorp.get_win_acl())
        #               --> And clear existing dest_rorp one while doing so
        #       2) Check if backup user has Admin privs to write dest_rorp
        #               --> May need to use Win32 AccessCheck() API
        #       3) If not, add Admin write privs to dest_rorp and add dir
        #               to dir_perms_list-equivalent
        #       4) THEN, allow the pre_process() function to finish and the
        #               files be copied over. Those files which wish to
        #               will now inherit the correct ACE objects.
        #       5) If dir was on dir_perms_list-equivalent, drop the write
        #               write permission we added.
        #       6) When copy_attribs is called in end_process, make sure
        #               that the write_win_acl() call isn't made this time
        # The reason we will need to do this is because otherwise, the files
        # which are created during step 4 will reference the ACE entries
        # which we clear during step 6. We need to clear them *before* the
        # children files/subdirs are created and generate the appropriate
        # DACL so the inheritance magic can happen during step 4.

        (flags, revision) = sd.GetSecurityDescriptorControl()
        if (not rp.isdir() and flags & SE_DACL_PROTECTED):
            self.clear_rp(rp)

        try:
            rp.conn.win32security. \
                SetNamedSecurityInfo(os.fsdecode(rp.path),
                                     SE_FILE_OBJECT, ACL.flags,
                                     sd.GetSecurityDescriptorOwner(),
                                     sd.GetSecurityDescriptorGroup(),
                                     sd.GetSecurityDescriptorDacl(),
                                     (ACL.flags & SACL_SECURITY_INFORMATION)
                                     and sd.GetSecurityDescriptorSacl() or None)
        except (OSError, IOError, pywintypes.error) as exc:
            log.Log(
                "Warning: unable to set ACL on %s: %s" % (repr(rp.path), exc),
                4)

    def __bytes__(self):
        return b'# file: %b\n%b\n' % \
            (C.acl_quote(self.get_indexpath()), self.__acl)

    def __str__(self):
        return os.fsdecode(self.__bytes__())

    def from_string(self, acl_str):
        lines = acl_str.splitlines()
        if len(lines) != 2 or not lines[0][:8] == b"# file: ":
            raise metadata.ParsingError(
                "Bad record beginning: %a" % lines[0][:8])
        filename = lines[0][8:]
        if filename == b'.':
            self.index = ()
        else:
            self.index = tuple(C.acl_unquote(filename).split(b'/'))
        self.__acl = lines[1]


def Record2WACL(record):
    acl = ACL()
    acl.from_string(record)
    return acl


def WACL2Record(wacl):
    return bytes(wacl)


class WACLExtractor(metadata.FlatExtractor):
    """Iterate ExtendedAttributes objects from the WACL information file"""
    record_boundary_regexp = re.compile(b'(?:\\n|^)(# file: (.*?))\\n')
    record_to_object = staticmethod(Record2WACL)

    def filename_to_index(self, filename):
        """Convert possibly quoted filename to index tuple"""
        if filename == b'.':
            return ()
        else:
            return tuple(C.acl_unquote(filename).split(b'/'))


class WinAccessControlListFile(metadata.FlatFile):
    """Store/retrieve ACLs from extended_attributes file"""
    _prefix = b"win_access_control_lists"
    _extractor = WACLExtractor
    _object_to_record = staticmethod(WACL2Record)


def join_wacl_iter(rorp_iter, wacl_iter):
    """Update a rorp iter by adding the information from acl_iter"""
    for rorp, wacl in rorpiter.CollateIterators(rorp_iter, wacl_iter):
        assert rorp, "Missing rorp for index %s" % (wacl.index, )
        if not wacl:
            wacl = ACL(rorp.index)
        rorp.set_win_acl(bytes(wacl))
        yield rorp


def rpath_acl_win_get(rpath):
    acl = ACL()
    acl.load_from_rp(rpath)
    return bytes(acl)


rpath.win_acl_get = rpath_acl_win_get


def rpath_get_blank_win_acl(index):
    acl = ACL(index)
    return bytes(acl)


rpath.get_blank_win_acl = rpath_get_blank_win_acl


def rpath_set_win_acl(rp, acl_str):
    acl = ACL()
    acl.from_string(acl_str)
    acl.write_to_rp(rp)


rpath.write_win_acl = rpath_set_win_acl


def init_acls():
    # A process that tries to read or write a SACL needs
    # to have and enable the SE_SECURITY_NAME privilege.
    # And inorder to backup/restore, the SE_BACKUP_NAME and
    # SE_RESTORE_NAME privileges are needed.
    import win32api
    try:
        hnd = OpenProcessToken(win32api.GetCurrentProcess(),
                               TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY)
    except win32api.error as exc:
        log.Log("Warning: unable to open Windows process token: %s" % exc, 5)
        return
    try:
        try:
            def lpv(priv):
                return LookupPrivilegeValue(None, priv)

            # enable the SE_*_NAME privileges
            SecurityName = lpv(SE_SECURITY_NAME)
            AdjustTokenPrivileges(
                hnd, False, [(SecurityName, SE_PRIVILEGE_ENABLED),
                             (lpv(SE_BACKUP_NAME), SE_PRIVILEGE_ENABLED),
                             (lpv(SE_RESTORE_NAME), SE_PRIVILEGE_ENABLED)])
        except win32api.error as exc:
            log.Log("Warning: unable to enable SE_*_NAME privileges: %s" % exc,
                    5)
            return
        for name, enabled in GetTokenInformation(hnd, TokenPrivileges):
            if name == SecurityName and enabled:
                # now we *may* access the SACL (sigh)
                ACL.flags |= SACL_SECURITY_INFORMATION
                break
    finally:
        win32api.CloseHandle(hnd)
