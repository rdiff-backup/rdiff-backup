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
Store and retrieve extended attributes

Not all file systems will have EAs, but if they do, store
this information in separate files in the rdiff-backup-data directory,
called extended_attributes.<time>.snapshot
"""

import base64
import errno
import re
import io

try:
    import xattr.pyxattr_compat as xattr
except ImportError:
    try:
        import xattr
    except ImportError:
        pass

from rdiff_backup import C, Globals, log, rorpiter
from rdiffbackup import meta
from rdiffbackup.utils import safestr


class ExtendedAttributes:
    """Hold a file's extended attribute information"""

    def __init__(self, index, attr_dict=None):
        """Initialize EA object with no attributes"""
        self.index = index
        if attr_dict is None:
            self.attr_dict = {}
        else:
            self.attr_dict = attr_dict

    def __eq__(self, ea):
        """Equal if all attributes are equal"""
        assert isinstance(ea, ExtendedAttributes), (
            "You can only compare with extended attributes not with {otype}.".format(
                otype=type(ea)))
        return ea.attr_dict == self.attr_dict

    def __ne__(self, ea):
        return not self.__eq__(ea)

    def get_indexpath(self):
        return self.index and b'/'.join(self.index) or b'.'

    def read_from_rp(self, rp):
        """Set the extended attributes from an rpath"""
        try:
            attr_list = xattr.list(rp.path, rp.issym())
        except OSError as exc:
            if exc.errno in (errno.EOPNOTSUPP, errno.EPERM, errno.ETXTBSY):
                return  # if not supported, consider empty
            if exc.errno in (errno.EACCES, errno.ENOENT, errno.ELOOP):
                log.Log("Listing extended attributes of path {pa} produced "
                        "exception '{ex}', ignored".format(pa=rp, ex=exc),
                        log.INFO)
                return
            raise
        for attr in attr_list:
            if attr.startswith(b'system.'):
                # Do not preserve system extended attributes
                continue
            if not rp.isdir() and attr == b'com.apple.ResourceFork':
                # Resource Fork handled elsewhere, except for directories
                continue
            try:
                self.attr_dict[attr] = xattr.get(rp.path, attr, rp.issym())
            except OSError as exc:
                # File probably modified while reading, just continue
                if exc.errno == errno.ENODATA:
                    continue
                elif exc.errno == errno.ENOENT:
                    break
                    # Handle bug in pyxattr < 0.2.2
                elif exc.errno == errno.ERANGE:
                    continue
                else:
                    raise

    def write_to_rp(self, rp):
        """Write extended attributes to rpath rp"""
        assert rp.conn is Globals.local_connection, (
            "Function works locally not over '{co}'.".format(co=rp.conn))

        self._clear_rp(rp)
        for (name, value) in self.attr_dict.items():
            try:
                xattr.set(rp.path, name, value, 0, rp.issym())
            except OSError as exc:
                # Mac and Linux attributes have different namespaces, so
                # fail gracefully if can't call xattr.set
                if exc.errno in (errno.EOPNOTSUPP, errno.EPERM, errno.EACCES,
                                 errno.ENOENT, errno.EINVAL):
                    log.Log("Unable to write xattr {xa} to path {pa} "
                            "due to exception '{ex}', ignoring".format(
                                xa=name, pa=rp, ex=exc), log.INFO)
                    continue
                else:
                    raise

    def get(self, name):
        """Return attribute attached to given name"""
        return self.attr_dict[name]

    def set(self, name, value=b""):
        """Set given name to given value.  Does not write to disk"""
        self.attr_dict[name] = value

    def delete(self, name):
        """Delete value associated with given name"""
        del self.attr_dict[name]

    def is_empty(self):
        """Return true if no extended attributes are set"""
        return not self.attr_dict

    def _clear_rp(self, rp):
        """Delete all the extended attributes in rpath"""
        try:
            for name in xattr.list(rp.path, rp.issym()):
                try:
                    xattr.remove(rp.path, name, rp.issym())
                except PermissionError:  # errno.EACCES
                    # SELinux attributes cannot be removed, and we don't want
                    # to bail out or be too noisy at low log levels.
                    log.Log("Not allowed to remove extended attribute "
                            "{ea} from path {pa}".format(ea=name, pa=rp),
                            log.DEBUG)
                    continue
                except OSError as exc:
                    # EINVAL is thrown on trying to remove system.nfs4_acl
                    # ENODATA can happen because trusted.SGI_ACL_FILE is deleted
                    # together with system.posix_acl_access on XFS file systems.
                    if exc.errno in (errno.EINVAL, errno.ENODATA):
                        continue
                    else:  # can be anything, just fail
                        log.Log(
                            "Can't remove extended attribute '{ea}' from "
                            "path '{pa}'".format(ea=name, pa=rp), log.ERROR)
                        raise
        except io.UnsupportedOperation:  # errno.EOPNOTSUPP or errno.EPERM
            return  # if not supported, consider empty
        except FileNotFoundError as exc:
            log.Log("Unable to clear extended attributes on path {pa} due to "
                    "exception '{ex}', ignoring".format(pa=rp, ex=exc),
                    log.NOTE)
            return


class EAExtractor(meta.FlatExtractor):
    """Iterate ExtendedAttributes objects from the EA information file"""
    record_boundary_regexp = re.compile(b'(?:\\n|^)(# file: (.*?))\\n')

    @staticmethod
    def _record_to_object(record):
        """Convert text record to ExtendedAttributes object"""
        lines = record.split(b'\n')
        first = lines.pop(0)
        if not first[:8] == b'# file: ':
            raise meta.ParsingError("Bad record beginning: %r" % first[:8])
        filename = first[8:]
        if filename == b'.':
            index = ()
        else:
            unquoted_filename = C.acl_unquote(filename)
            index = tuple(unquoted_filename.split(b'/'))
        ea = get_meta_object(index)

        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line[0] == b'#':
                raise meta.ParsingError(
                    "Only the first line of a record can start with a hash: {line}.".format(
                        line=line))
            eq_pos = line.find(b'=')
            if eq_pos == -1:
                ea.set(line)
            else:
                name = line[:eq_pos]
                if line[eq_pos + 1:eq_pos + 3] != b'0s':
                    raise meta.ParsingError(
                        "Currently only base64 encoding supported")
                encoded_val = line[eq_pos + 3:]
                ea.set(name, base64.b64decode(encoded_val))
        return ea

    def _filename_to_index(self, filename):
        """Convert possibly quoted filename to index tuple"""
        if filename == b'.':
            return ()
        else:
            return tuple(C.acl_unquote(filename).split(b'/'))


class ExtendedAttributesFile(meta.FlatFile):
    """Store/retrieve EAs from extended_attributes file"""
    _name = "ea"
    _description = "Extended Attributes"
    _prefix = b"extended_attributes"
    _extractor = EAExtractor
    _is_main = False

    @classmethod
    def is_active(cls):
        return Globals.eas_active

    @staticmethod
    def _object_to_record(ea):
        """Convert ExtendedAttributes object to text record"""
        str_list = [b'# file: %s' % C.acl_quote(ea.get_indexpath())]

        for (name, val) in ea.attr_dict.items():
            if not val:
                str_list.append(name)
            else:
                encoded_val = base64.b64encode(val)
                str_list.append(b'%s=0s%s' % (C.acl_quote(name), encoded_val))
        return b'\n'.join(str_list) + b'\n'

    @staticmethod
    def join_iter(rorp_iter, ea_iter):
        """Update a rorp iter by adding the information from ea_iter"""
        for rorp, ea in rorpiter.CollateIterators(rorp_iter, ea_iter):
            assert rorp, ("Missing rorp for EA index '{eaidx}'.".format(
                eaidx=map(safestr.to_str, ea.index)))
            if not ea:
                ea = get_meta_object(rorp.index)
            rorp.set_ea(ea)
            yield rorp

    def write_object(self, rorp, force_empty=False):
        """
        write RORPath' metadata to file

        The force_empty parameter is for test purposes only to even write
        empty metadata
        """
        ea_meta = rorp.get_ea()
        if ea_meta.is_empty() and not force_empty:
            return None
        else:
            return super().write_object(ea_meta)


def get_meta(rp):
    """
    Get extended attributes of given rpath
    """
    assert rp.conn is Globals.local_connection, (
        "Function works locally not over '{co}'.".format(co=rp.conn))
    ea = get_meta_object(rp.index)
    if not rp.issock() and not rp.isfifo():
        ea.read_from_rp(rp)
    return ea


def get_blank_meta(index):
    """
    Get a blank ExtendedAttributes object
    """
    return get_meta_object(index)


def get_meta_object(*params):
    """
    Returns a Metadata object as corresponds to the current type

    Necessary to guarantee compatibility between rdiff-backup 2.0 and 2.1+
    """
    if Globals.get_api_version() < 201:  # compat200
        from rdiff_backup import eas_acls
        return eas_acls.ExtendedAttributes(*params)
    else:
        return ExtendedAttributes(*params)


def get_plugin_class():
    return ExtendedAttributesFile
