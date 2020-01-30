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
"""Store and retrieve extended attributes and access control lists

Not all file systems will have EAs and ACLs, but if they do, store
this information in separate files in the rdiff-backup-data directory,
called extended_attributes.<time>.snapshot and
access_control_lists.<time>.snapshot.

"""

import base64
import errno
import re
import io
import os
try:
    import posix1e
except ImportError:
    pass
from . import Globals, connection, metadata, rorpiter, log, C, rpath, user_group  # noqa: F401

# When an ACL gets dropped, put name in dropped_acl_names.  This is
# only used so that only the first dropped ACL for any given name
# triggers a warning.
dropped_acl_names = {}


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
        assert isinstance(ea, ExtendedAttributes)
        return ea.attr_dict == self.attr_dict

    def __ne__(self, ea):
        return not self.__eq__(ea)

    def get_indexpath(self):
        return self.index and b'/'.join(self.index) or b'.'

    def read_from_rp(self, rp):
        """Set the extended attributes from an rpath"""
        try:
            attr_list = rp.conn.xattr.listxattr(rp.path, rp.issym())
        except IOError as exc:
            if exc.errno in (errno.EOPNOTSUPP, errno.EPERM, errno.ETXTBSY):
                return  # if not supported, consider empty
            if exc.errno in (errno.EACCES, errno.ENOENT, errno.ELOOP):
                log.Log("Warning: listattr(%s): %s" % (rp.get_safepath(), exc),
                        4)
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
                self.attr_dict[attr] = \
                    rp.conn.xattr.getxattr(rp.path, attr, rp.issym())
            except IOError as exc:
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

    def clear_rp(self, rp):
        """Delete all the extended attributes in rpath"""
        try:
            for name in rp.conn.xattr.listxattr(rp.path, rp.issym()):
                try:
                    rp.conn.xattr.removexattr(rp.path, name, rp.issym())
                except PermissionError:  # errno.EACCES
                    # SELinux attributes cannot be removed, and we don't want
                    # to bail out or be too noisy at low log levels.
                    log.Log(
                        "Warning: unable to remove xattr %s from %s" %
                        (name, rp.get_safepath()), 7)
                    continue
                except OSError as exc:
                    # can happen because trusted.SGI_ACL_FILE is deleted together with
                    # system.posix_acl_access on XFS file systems.
                    if exc.errno == errno.ENODATA:
                        continue
                    else:  # can be anything, just fail
                        raise
        except io.UnsupportedOperation:  # errno.EOPNOTSUPP or errno.EPERM
            return  # if not supported, consider empty
        except FileNotFoundError as exc:
            log.Log(
                "Warning: unable to clear xattrs on %s: %s" %
                (rp.get_safepath(), exc), 3)
            return

    def write_to_rp(self, rp):
        """Write extended attributes to rpath rp"""
        self.clear_rp(rp)
        for (name, value) in self.attr_dict.items():
            try:
                rp.conn.xattr.setxattr(rp.path, name, value, 0, rp.issym())
            except IOError as exc:
                # Mac and Linux attributes have different namespaces, so
                # fail gracefully if can't call setxattr
                if exc.errno in (errno.EOPNOTSUPP, errno.EPERM, errno.EACCES,
                                 errno.ENOENT, errno.EINVAL):
                    log.Log(
                        "Warning: unable to write xattr %s to %s" %
                        (name, rp.get_safepath()), 6)
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

    def empty(self):
        """Return true if no extended attributes are set"""
        return not self.attr_dict


def ea_compare_rps(rp1, rp2):
    """Return true if rp1 and rp2 have same extended attributes"""
    ea1 = ExtendedAttributes(rp1.index)
    ea1.read_from_rp(rp1)
    ea2 = ExtendedAttributes(rp2.index)
    ea2.read_from_rp(rp2)
    return ea1 == ea2


def EA2Record(ea):
    """Convert ExtendedAttributes object to text record"""
    str_list = [b'# file: %s' % C.acl_quote(ea.get_indexpath())]

    for (name, val) in ea.attr_dict.items():
        if not val:
            str_list.append(name)
        else:
            encoded_val = base64.b64encode(val)
            str_list.append(b'%s=0s%s' % (C.acl_quote(name), encoded_val))
    return b'\n'.join(str_list) + b'\n'


def Record2EA(record):
    """Convert text record to ExtendedAttributes object"""
    lines = record.split(b'\n')
    first = lines.pop(0)
    if not first[:8] == b'# file: ':
        raise metadata.ParsingError("Bad record beginning: %b" % first[:8])
    filename = first[8:]
    if filename == b'.':
        index = ()
    else:
        unquoted_filename = C.acl_unquote(filename)
        index = tuple(unquoted_filename.split(b'/'))
    ea = ExtendedAttributes(index)

    for line in lines:
        line = line.strip()
        if not line:
            continue
        assert line[0] != b'#', line
        eq_pos = line.find(b'=')
        if eq_pos == -1:
            ea.set(line)
        else:
            name = line[:eq_pos]
            assert line[eq_pos + 1:eq_pos + 3] == b'0s', \
                "Currently only base64 encoding supported"
            encoded_val = line[eq_pos + 3:]
            ea.set(name, base64.b64decode(encoded_val))
    return ea


class EAExtractor(metadata.FlatExtractor):
    """Iterate ExtendedAttributes objects from the EA information file"""
    record_boundary_regexp = re.compile(b'(?:\\n|^)(# file: (.*?))\\n')
    record_to_object = staticmethod(Record2EA)

    def filename_to_index(self, filename):
        """Convert possibly quoted filename to index tuple"""
        if filename == b'.':
            return ()
        else:
            return tuple(C.acl_unquote(filename).split(b'/'))


class ExtendedAttributesFile(metadata.FlatFile):
    """Store/retrieve EAs from extended_attributes file"""
    _prefix = b"extended_attributes"
    _extractor = EAExtractor
    _object_to_record = staticmethod(EA2Record)


def join_ea_iter(rorp_iter, ea_iter):
    """Update a rorp iter by adding the information from ea_iter"""
    for rorp, ea in rorpiter.CollateIterators(rorp_iter, ea_iter):
        assert rorp, "Missing rorp for index %a" % (ea.index, )
        if not ea:
            ea = ExtendedAttributes(rorp.index)
        rorp.set_ea(ea)
        yield rorp


class AccessControlLists:
    """Hold a file's access control list information

    Since posix1e.ACL objects cannot be pickled, and because they lack
    user/group name information, store everything in self.entry_list
    and self.default_entry_list.

    """

    def __init__(self, index, acl_text=None):
        """Initialize object with index and possibly acl_text"""
        self.index = index
        if acl_text:
            self.set_from_text(acl_text)
        else:
            self.entry_list = self.default_entry_list = None

    def set_from_text(self, text):
        """Set self.entry_list and self.default_entry_list from text"""
        self.entry_list, self.default_entry_list = [], []
        for line in text.split('\n'):
            comment_pos = line.find('#')
            if comment_pos >= 0:
                line = line[:comment_pos]
            line = line.strip()
            if not line:
                continue

            if line.startswith('default:'):
                entrytuple = self.text_to_entrytuple(line[8:])
                self.default_entry_list.append(entrytuple)
            else:
                self.entry_list.append(self.text_to_entrytuple(line))

    def __str__(self):
        """Return text version of acls"""
        if not self.entry_list:
            return ""
        slist = list(map(self.entrytuple_to_text, self.entry_list))
        if self.default_entry_list:
            slist.extend([
                "default:" + self.entrytuple_to_text(e)
                for e in self.default_entry_list
            ])
        return "\n".join(slist)

    def entrytuple_to_text(self, entrytuple):
        """Return text version of entrytuple, as in getfacl"""
        tagchar, name_pair, perms = entrytuple
        if tagchar == "U":
            text = 'user::'
        elif tagchar == "u":
            uid, uname = name_pair
            text = 'user:%s:' % (uname or uid)
        elif tagchar == "G":
            text = 'group::'
        elif tagchar == "g":
            gid, gname = name_pair
            text = 'group:%s:' % (gname or gid)
        elif tagchar == "M":
            text = 'mask::'
        else:
            assert tagchar == "O", tagchar
            text = 'other::'

        permstring = '%s%s%s' % (perms & 4 and 'r' or '-', perms & 2 and 'w'
                                 or '-', perms & 1 and 'x' or '-')
        return text + permstring

    def text_to_entrytuple(self, text):
        """Return entrytuple given text like 'user:foo:r--'

        See the acl_to_list function for entrytuple documentation.

        """
        typetext, qualifier, permtext = text.split(':')
        if qualifier:
            try:
                uid = int(qualifier)
            except ValueError:
                namepair = (None, qualifier)
            else:
                namepair = (uid, None)

            if typetext == 'user':
                typechar = "u"
            else:
                assert typetext == 'group', (typetext, text)
                typechar = "g"
        else:
            namepair = None
            if typetext == 'user':
                typechar = "U"
            elif typetext == 'group':
                typechar = "G"
            elif typetext == 'mask':
                typechar = "M"
            else:
                assert typetext == 'other', (typetext, text)
                typechar = "O"

        assert len(permtext) == 3, (permtext, text)
        read, write, execute = permtext
        perms = ((read == 'r') << 2 | (write == 'w') << 1 | (execute == 'x'))
        return (typechar, namepair, perms)

    def cmp_entry_list(self, l1, l2):
        """True if the lists have same entries.  Assume preordered"""
        if not l1:
            return not l2
        if not l2 or len(l1) != len(l2):
            return 0
        for i in range(len(l1)):
            type1, namepair1, perms1 = l1[i]
            type2, namepair2, perms2 = l2[i]
            if type1 != type2 or perms1 != perms2:
                return 0
            if namepair1 == namepair2:
                continue
            if not namepair1 or not namepair2:
                return 0
            (id1, name1), (id2, name2) = namepair1, namepair2
            if name1:
                if name1 == name2:
                    continue
                else:
                    return 0
            if name2:
                return 0
            if id1 != id2:
                return 0
        return 1

    def __eq__(self, acl):
        """Compare self and other access control list

        Basic acl permissions are considered equal to an empty acl
        object.

        """
        assert isinstance(acl, self.__class__)
        if self.is_basic():
            return acl.is_basic()
        return (self.cmp_entry_list(self.entry_list, acl.entry_list)
                and self.cmp_entry_list(self.default_entry_list,
                                        acl.default_entry_list))

    def __ne__(self, acl):
        return not self.__eq__(acl)

    def eq_verbose(self, acl):
        """Returns same as __eq__ but print explanation if not equal"""
        if not self.cmp_entry_list(self.entry_list, acl.entry_list):
            print("ACL entries for %s compare differently" % (self.index, ))
            return 0
        if not self.cmp_entry_list(self.default_entry_list,
                                   acl.default_entry_list):
            print("Default ACL entries for %s do not compare" % (self.index, ))
            return 0
        return 1

    def get_indexpath(self):
        return self.index and b'/'.join(self.index) or b'.'

    def is_basic(self):
        """True if acl can be reduced to standard unix permissions

        Assume that if they are only three entries, they correspond to
        user, group, and other, and thus don't use any special ACL
        features.

        """
        if not self.entry_list and not self.default_entry_list:
            return 1
        assert len(self.entry_list) >= 3, self.entry_list
        return len(self.entry_list) == 3 and not self.default_entry_list

    def read_from_rp(self, rp):
        """Set self.ACL from an rpath, or None if not supported"""
        self.entry_list, self.default_entry_list = \
            rp.conn.eas_acls.get_acl_lists_from_rp(rp)

    def write_to_rp(self, rp, map_names=1):
        """Write current access control list to RPath rp"""
        rp.conn.eas_acls.set_rp_acl(rp, self.entry_list,
                                    self.default_entry_list, map_names)


def set_rp_acl(rp, entry_list=None, default_entry_list=None, map_names=1):
    """Set given rp with ACL that acl_text defines.  rp should be local"""
    assert rp.conn is Globals.local_connection
    if entry_list:
        acl = list_to_acl(entry_list, map_names)
    else:
        acl = posix1e.ACL()

    try:
        acl.applyto(rp.path)
    except IOError as exc:
        if exc.errno == errno.EOPNOTSUPP:
            log.Log(
                "Warning: unable to set ACL on %s: %s" % (rp.get_safepath(),
                                                          exc), 4)
            return
        else:
            raise

    if rp.isdir():
        if default_entry_list:
            def_acl = list_to_acl(default_entry_list, map_names)
        else:
            def_acl = posix1e.ACL()
        def_acl.applyto(rp.path, posix1e.ACL_TYPE_DEFAULT)


def get_acl_lists_from_rp(rp):
    """Returns (acl_list, def_acl_list) from an rpath.  Call locally"""
    assert rp.conn is Globals.local_connection
    try:
        acl = posix1e.ACL(file=rp.path)
    except (FileNotFoundError, UnicodeEncodeError) as exc:
        log.Log(
            "Warning: unable to read ACL from %s: %s" % (rp.get_safepath(),
                                                         exc), 3)
        acl = None
    except IOError as exc:
        if exc.errno == errno.EOPNOTSUPP:
            acl = None
        else:
            raise
    if rp.isdir():
        try:
            def_acl = posix1e.ACL(filedef=os.fsdecode(rp.path))
        except (FileNotFoundError, UnicodeEncodeError) as exc:
            log.Log(
                "Warning: unable to read default ACL from %s: %s" %
                (rp.get_safepath(), exc), 3)
            def_acl = None
        except IOError as exc:
            if exc.errno == errno.EOPNOTSUPP:
                def_acl = None
            else:
                raise
    else:
        def_acl = None
    return (acl and acl_to_list(acl), def_acl and acl_to_list(def_acl))


def acl_to_list(acl):
    """Return list representation of posix1e.ACL object

    ACL objects cannot be pickled, so this representation keeps
    the structure while adding that option.  Also we insert the
    username along with the id, because that information will be
    lost when moved to another system.

    The result will be a list of tuples.  Each tuple will have the
    form (acltype, (uid or gid, uname or gname) or None, permissions
    as an int).  acltype is encoded as a single character:

    U - ACL_USER_OBJ
    u - ACL_USER
    G - ACL_GROUP_OBJ
    g - ACL_GROUP
    M - ACL_MASK
    O - ACL_OTHER

    """

    def acltag_to_char(tag):
        if tag == posix1e.ACL_USER_OBJ:
            return "U"
        elif tag == posix1e.ACL_USER:
            return "u"
        elif tag == posix1e.ACL_GROUP_OBJ:
            return "G"
        elif tag == posix1e.ACL_GROUP:
            return "g"
        elif tag == posix1e.ACL_MASK:
            return "M"
        else:
            assert tag == posix1e.ACL_OTHER, tag
            return "O"

    def entry_to_tuple(entry):
        tagchar = acltag_to_char(entry.tag_type)
        if tagchar == "u":
            uid = entry.qualifier
            owner_pair = (uid, user_group.uid2uname(uid))
        elif tagchar == "g":
            gid = entry.qualifier
            owner_pair = (gid, user_group.gid2gname(gid))
        else:
            owner_pair = None

        perms = (entry.permset.read << 2 | entry.permset.write << 1
                 | entry.permset.execute)
        return (tagchar, owner_pair, perms)

    return list(map(entry_to_tuple, acl))


def list_to_acl(entry_list, map_names=1):
    """Return posix1e.ACL object from list representation

    If map_names is true, use user_group to update the names for the
    current system, and drop if not available.  Otherwise just use the
    same id.

    See the acl_to_list function for the format of an acllist.

    """

    def char_to_acltag(typechar):
        """Given typechar, query posix1e module for appropriate constant"""
        if typechar == "U":
            return posix1e.ACL_USER_OBJ
        elif typechar == "u":
            return posix1e.ACL_USER
        elif typechar == "G":
            return posix1e.ACL_GROUP_OBJ
        elif typechar == "g":
            return posix1e.ACL_GROUP
        elif typechar == "M":
            return posix1e.ACL_MASK
        else:
            assert typechar == "O", typechar
            return posix1e.ACL_OTHER

    def warn_drop(name):
        """Warn about acl with name getting dropped"""
        global dropped_acl_names
        if Globals.never_drop_acls:
            log.Log.FatalError(
                "--never-drop-acls specified but cannot map name\n"
                "%s occurring inside an ACL." % (name, ))
        if name in dropped_acl_names:
            return
        log.Log(
            "Warning: name %s not found on system, dropping ACL entry.\n"
            "Further ACL entries dropped with this name will not "
            "trigger further warnings" % (name, ), 2)
        dropped_acl_names[name] = name

    acl = posix1e.ACL()
    for typechar, owner_pair, perms in entry_list:
        id = None
        if owner_pair:
            if map_names:
                if typechar == "u":
                    id = user_group.acl_user_map(*owner_pair)
                else:
                    assert typechar == "g", (typechar, owner_pair, perms)
                    id = user_group.acl_group_map(*owner_pair)
                if id is None:
                    warn_drop(owner_pair[1])
                    continue
            else:
                assert owner_pair[0] is not None, (typechar, owner_pair, perms)
                id = owner_pair[0]

        entry = posix1e.Entry(acl)
        entry.tag_type = char_to_acltag(typechar)
        if id is not None:
            entry.qualifier = id
        entry.permset.read = perms >> 2
        entry.permset.write = perms >> 1 & 1
        entry.permset.execute = perms & 1
    return acl


def acl_compare_rps(rp1, rp2):
    """Return true if rp1 and rp2 have same acl information"""
    acl1 = AccessControlLists(rp1.index)
    acl1.read_from_rp(rp1)
    acl2 = AccessControlLists(rp2.index)
    acl2.read_from_rp(rp2)
    return acl1 == acl2


def ACL2Record(acl):
    """Convert an AccessControlLists object into a text record"""
    return b'# file: %b\n%b\n' % (C.acl_quote(acl.get_indexpath()), os.fsencode(str(acl)))


def Record2ACL(record):
    """Convert text record to an AccessControlLists object"""
    newline_pos = record.find(b'\n')
    first_line = record[:newline_pos]
    if not first_line.startswith(b'# file: '):
        raise metadata.ParsingError("Bad record beginning: %b" % first_line)
    filename = first_line[8:]
    if filename == b'.':
        index = ()
    else:
        unquoted_filename = C.acl_unquote(filename)
        index = tuple(unquoted_filename.split(b'/'))
    return AccessControlLists(index, os.fsdecode(record[newline_pos:]))


class ACLExtractor(EAExtractor):
    """Iterate AccessControlLists objects from the ACL information file

    Except for the record_to_object method, we can reuse everything in
    the EAExtractor class because the file formats are so similar.

    """
    record_to_object = staticmethod(Record2ACL)


class AccessControlListFile(metadata.FlatFile):
    """Store/retrieve ACLs from extended attributes file"""
    _prefix = b'access_control_lists'
    _extractor = ACLExtractor
    _object_to_record = staticmethod(ACL2Record)


def join_acl_iter(rorp_iter, acl_iter):
    """Update a rorp iter by adding the information from acl_iter"""
    for rorp, acl in rorpiter.CollateIterators(rorp_iter, acl_iter):
        assert rorp, "Missing rorp for index %s" % (acl.index, )
        if not acl:
            acl = AccessControlLists(rorp.index)
        rorp.set_acl(acl)
        yield rorp


def rpath_acl_get(rp):
    """Get acls of given rpath rp.

    This overrides a function in the rpath module.

    """
    acl = AccessControlLists(rp.index)
    if not rp.issym():
        acl.read_from_rp(rp)
    return acl


rpath.acl_get = rpath_acl_get


def rpath_get_blank_acl(index):
    """Get a blank AccessControlLists object (override rpath function)"""
    return AccessControlLists(index)


rpath.get_blank_acl = rpath_get_blank_acl


def rpath_ea_get(rp):
    """Get extended attributes of given rpath

    This overrides a function in the rpath module.

    """
    ea = ExtendedAttributes(rp.index)
    if not rp.issock() and not rp.isfifo():
        ea.read_from_rp(rp)
    return ea


rpath.ea_get = rpath_ea_get


def rpath_get_blank_ea(index):
    """Get a blank ExtendedAttributes object (override rpath function)"""
    return ExtendedAttributes(index)


rpath.get_blank_ea = rpath_get_blank_ea
