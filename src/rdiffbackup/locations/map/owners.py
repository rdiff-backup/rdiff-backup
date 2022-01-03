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
"""
This module deal with users and groups

On each connection we may need to map unames and gnames to uids and
gids, and possibly vice-versa.  So maintain a separate dictionary for
this.

On the destination connection only, if necessary have a separate
dictionary of mappings, which specify how to map users/groups on one
connection to the users/groups on the other.  The _user_map and _group_map
objects should only be used on the destination.
"""

from rdiff_backup import log
from rdiffbackup.utils import usrgrp

# The following two variables are set by init_users_mapping resp.
# init_groups_mapping to an object of class Map, DefinedMap or NumericalMap
# depending on mapping type
_user_map = None
_group_map = None


def map_rpath_owner(rp):
    """
    Return mapped (newuid, newgid) from rpath's initial info

    This is the main function exported by the user_group module.  Note
    that it is connection specific.
    """
    uid, gid = rp.getuidgid()
    uname, gname = rp.getuname(), rp.getgname()
    return (_user_map(uid, uname), _group_map(gid, gname))


def map_acl_user(uid, uname):
    return _user_map.map_acl(uid, uname)


def map_acl_group(gid, gname):
    return _group_map.map_acl(gid, gname)


# ----------- "Private" section - don't use outside user_group -----------


class _Map:
    """
    Used for mapping names and id on source side to dest side
    """

    def __init__(self, is_user):
        """
        Initialize, is_user is True for users, False for groups
        """
        if is_user:
            self.name2id = usrgrp.uname2uid
        else:
            self.name2id = usrgrp.gname2gid

    def __call__(self, id, name=None):
        """
        Return mapped id from id and, if available, name
        """
        if not name:
            return id
        newid = self.name2id(name)
        if newid is None:
            return id
        else:
            return newid

    def map_acl(self, id, name=None):
        """
        Like get_id, but use this for ACLs.  Return id or None

        Unlike ordinary user/group ownership, ACLs are not required
        and can be dropped.  If we cannot map the name over, return
        None.
        """
        if not name:
            return id
        return self.name2id(name)


class _DefinedMap(_Map):
    """
    Map names and ids on source side to appropriate ids on dest side

    Like map, but initialize with user-defined mapping string, which
    supersedes _Map.
    """

    def __init__(self, is_user, mapping_string):
        """
        Initialize object with given mapping string

        The mapping_string should consist of a number of lines, each which
        should have the form "source_id_or_name:dest_id_or_name".  Do user
        mapping unless user is false, then do group.
        """
        super().__init__(is_user)
        self.name_mapping_dict = {}
        self.id_mapping_dict = {}

        if isinstance(mapping_string, str):  # else we assume a list
            mapping_string = mapping_string.split("\n")
        for line in mapping_string:
            line = line.strip()
            if not line:
                continue
            comps = line.split(':')
            if not len(comps) == 2:
                log.Log.FatalError("Failed parsing user/group mapping file, "
                                   "bad line {bl}".format(bl=line))
            old, new = comps

            try:
                self.id_mapping_dict[int(old)] = self._get_new_id(new)
            except ValueError:
                self.name_mapping_dict[old] = self._get_new_id(new)

    def __call__(self, id, name=None):
        """
        Return new id given old id and name
        """
        newid = self.map_acl(id, name)
        if newid is None:
            return id
        else:
            return newid

    def map_acl(self, id, name=None):
        """
        Return new id or None given old and name (used for ACLs)
        """
        if name:
            if name in self.name_mapping_dict:
                return self.name_mapping_dict[name]
            newid = self.name2id(name)
            if newid is not None:
                return newid
        if id in self.id_mapping_dict:
            return self.id_mapping_dict[id]
        else:
            return None

    def _get_new_id(self, id_or_name):
        """
        Return id of id_or_name, failing if cannot.  Used in __init__
        """
        try:
            return int(id_or_name)
        except ValueError:
            try:
                return self.name2id(id_or_name)
            except KeyError:
                log.Log.FatalError("Cannot get id for user or group "
                                   "name {ug}".format(ug=id_or_name))


class _NumericalMap:
    """
    Simple Map replacement that just keeps numerical uid or gid
    """

    def __call__(self, id, name=None):
        return id

    def map_acl(self, id, name=None):
        return id


def init_users_mapping(mapping_string=None, numerical_ids=None):
    """
    Initialize user mapping with given mapping string

    If numerical_ids is set, just keep the same uid.  If either
    argument is None, default to preserving uname where possible.
    """
    global _user_map
    if numerical_ids:
        _user_map = _NumericalMap()
    elif mapping_string:
        _user_map = _DefinedMap(True, mapping_string)
    else:
        _user_map = _Map(True)


def init_groups_mapping(mapping_string=None, numerical_ids=None):
    """
    Initialize group mapping with given mapping string

    If numerical_ids is set, just keep the same gid.  If either
    argument is None, default to preserving gname where possible.
    """
    global _group_map
    if numerical_ids:
        _group_map = _NumericalMap()
    elif mapping_string:
        _group_map = _DefinedMap(False, mapping_string)
    else:
        _group_map = _Map(False)
