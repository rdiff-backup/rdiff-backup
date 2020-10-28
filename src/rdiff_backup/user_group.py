# Copyright 2002, 2003 Ben Escoto
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
"""This module deal with users and groups

On each connection we may need to map unames and gnames to uids and
gids, and possibly vice-versa.  So maintain a separate dictionary for
this.

On the destination connection only, if necessary have a separate
dictionary of mappings, which specify how to map users/groups on one
connection to the users/groups on the other.  The _user_map and _group_map
objects should only be used on the destination.

"""

try:
    import grp
    import pwd
except ImportError:
    pass

from . import log

# ----------- "Private" section - don't use outside user_group -----------

# The following two variables are set by init_user_mapping resp. init_group_mapping
# to an object of class Map, DefinedMap or NumericalMap depending on mapping type
_user_map = None
_group_map = None

# Used to cache by uid2uname and gid2gname below
_uid2uname_dict = {}
_gid2gname_dict = {}

_uname2uid_dict = {}
_gname2gid_dict = {}


class _Map:
    """Used for mapping names and id on source side to dest side"""

    def __init__(self, is_user):
        """Initialize, user is true for users, false for groups"""
        self.name2id = (is_user and _uname2uid) or _gname2gid

    def __call__(self, id, name=None):
        """Return mapped id from id and, if available, name"""
        if not name:
            return id
        newid = self.name2id(name)
        if newid is None:
            return id
        else:
            return newid

    def map_acl(self, id, name=None):
        """Like get_id, but use this for ACLs.  Return id or None

        Unlike ordinary user/group ownership, ACLs are not required
        and can be dropped.  If we cannot map the name over, return
        None.

        """
        if not name:
            return id
        return self.name2id(name)


class _DefinedMap(_Map):
    """Map names and ids on source side to appropriate ids on dest side

    Like map, but initialize with user-defined mapping string, which
    supersedes _Map.

    """

    def __init__(self, is_user, mapping_string):
        """Initialize object with given mapping string

        The mapping_string should consist of a number of lines, each which
        should have the form "source_id_or_name:dest_id_or_name".  Do user
        mapping unless user is false, then do group.

        """
        super().__init__(is_user)
        self.name_mapping_dict = {}
        self.id_mapping_dict = {}

        for line in mapping_string.split('\n'):
            line = line.strip()
            if not line:
                continue
            comps = line.split(':')
            if not len(comps) == 2:
                log.Log.FatalError("Error parsing mapping file, bad line: "
                                   + line)
            old, new = comps

            try:
                self.id_mapping_dict[int(old)] = self._get_new_id(new)
            except ValueError:
                self.name_mapping_dict[old] = self._get_new_id(new)

    def __call__(self, id, name=None):
        """Return new id given old id and name"""
        newid = self.map_acl(id, name)
        if newid is None:
            return id
        else:
            return newid

    def map_acl(self, id, name=None):
        """Return new id or None given old and name (used for ACLs)"""
        if name:
            try:
                return self.name_mapping_dict[name]
            except KeyError:
                pass
            newid = self.name2id(name)
            if newid is not None:
                return newid
        try:
            return self.id_mapping_dict[id]
        except KeyError:
            return None

    def _get_new_id(self, id_or_name):
        """Return id of id_or_name, failing if cannot.  Used in __init__"""
        try:
            return int(id_or_name)
        except ValueError:
            try:
                return self.name2id(id_or_name)
            except KeyError:
                log.Log.FatalError("Cannot get id for user or group name "
                                   + id_or_name)


class _NumericalMap:
    """Simple Map replacement that just keeps numerical uid or gid"""

    def __call__(self, id, name=None):
        return id

    def map_acl(self, id, name=None):
        return id


def uid2uname(uid):
    """Given uid, return uname from passwd file, or None if cannot find"""
    try:
        return _uid2uname_dict[uid]
    except KeyError:
        try:
            uname = pwd.getpwuid(uid)[0]
        except (KeyError, OverflowError, NameError):
            uname = None
        _uid2uname_dict[uid] = uname
        return uname


def gid2gname(gid):
    """Given gid, return group name from group file or None if cannot find"""
    try:
        return _gid2gname_dict[gid]
    except KeyError:
        try:
            gname = grp.getgrgid(gid)[0]
        except (KeyError, OverflowError, NameError):
            gname = None
        _gid2gname_dict[gid] = gname
        return gname


# @API(init_user_mapping, 200)
def init_user_mapping(mapping_string=None, numerical_ids=None):
    """Initialize user mapping with given mapping string

    If numerical_ids is set, just keep the same uid.  If either
    argument is None, default to preserving uname where possible.

    """
    global _user_map
    if numerical_ids:
        _user_map = _NumericalMap()
    elif mapping_string:
        _user_map = _DefinedMap(1, mapping_string)
    else:
        _user_map = _Map(1)


# @API(init_group_mapping, 200)
def init_group_mapping(mapping_string=None, numerical_ids=None):
    """Initialize group mapping with given mapping string

    If numerical_ids is set, just keep the same gid.  If either
    argument is None, default to preserving gname where possible.

    """
    global _group_map
    if numerical_ids:
        _group_map = _NumericalMap()
    elif mapping_string:
        _group_map = _DefinedMap(0, mapping_string)
    else:
        _group_map = _Map(0)


# @API(map_rpath, 200)
def map_rpath(rp):
    """Return mapped (newuid, newgid) from rpath's initial info

    This is the main function exported by the user_group module.  Note
    that it is connection specific.

    """
    uid, gid = rp.getuidgid()
    uname, gname = rp.getuname(), rp.getgname()
    return (_user_map(uid, uname), _group_map(gid, gname))


def acl_user_map(uid, uname):
    return _user_map.map_acl(uid, uname)


def acl_group_map(gid, gname):
    return _group_map.map_acl(gid, gname)


def _uname2uid(uname):
    """Given uname, return uid or None if cannot find"""
    try:
        return _uname2uid_dict[uname]
    except KeyError:
        try:
            uid = pwd.getpwnam(uname)[2]
        except (KeyError, NameError):
            uid = None
        _uname2uid_dict[uname] = uid
        return uid


def _gname2gid(gname):
    """Given gname, return gid or None if cannot find"""
    try:
        return _gname2gid_dict[gname]
    except KeyError:
        try:
            gid = grp.getgrnam(gname)[2]
        except (KeyError, NameError):
            gid = None
        _gname2gid_dict[gname] = gid
        return gid
