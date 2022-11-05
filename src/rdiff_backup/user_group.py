# DEPRECATED compat200
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

from rdiffbackup.locations.map import owners as map_owners


# @API(init_user_mapping, 200, 200)
def init_user_mapping(mapping_string=None, numerical_ids=None):
    """
    Initialize user mapping with given mapping string

    If numerical_ids is set, just keep the same uid.  If either
    argument is None, default to preserving uname where possible.
    """
    return map_owners.init_users_mapping(mapping_string, numerical_ids)


# @API(init_group_mapping, 200, 200)
def init_group_mapping(mapping_string=None, numerical_ids=None):
    """
    Initialize group mapping with given mapping string

    If numerical_ids is set, just keep the same gid.  If either
    argument is None, default to preserving gname where possible.
    """
    return map_owners.init_groups_mapping(mapping_string, numerical_ids)
