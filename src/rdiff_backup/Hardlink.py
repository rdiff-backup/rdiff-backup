# Copyright 2002 2005 Ben Escoto
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
"""Preserve and restore hard links

If the preserve_hardlinks option is selected, linked files in the
source directory will be linked in the mirror directory.  Linked files
are treated like any other with respect to incrementing, but their
link status can be retrieved because their device location and inode #
is written in the metadata file.

All these functions are meant to be executed on the mirror side.  The
source side should only transmit inode information.

"""

import errno

# The keys in this dictionary are (inode, devloc) pairs.  The values
# are a pair (index, remaining_links, dest_key, sha1sum) where index
# is the rorp index of the first such linked file, remaining_links is
# the number of files hard linked to this one we may see, and key is
# either (dest_inode, dest_devloc) or None, and represents the
# hardlink info of the existing file on the destination.  Finally
# sha1sum is the hash of the file if it exists, or None.
_inode_index = None


def initialize_dictionaries():
    """Set all the hard link dictionaries to empty"""
    global _inode_index
    _inode_index = {}


def clear_dictionaries():
    """Delete all dictionaries"""
    global _inode_index
    _inode_index = None


def get_inode_key(rorp):
    """Return rorp's key for _inode_ dictionaries"""
    return (rorp.getinode(), rorp.getdevloc())


def add_rorp(rorp, dest_rorp=None):
    """Process new rorp and update hard link dictionaries"""
    if not rorp.isreg() or rorp.getnumlinks() < 2:
        return None
    rp_inode_key = get_inode_key(rorp)
    if rp_inode_key not in _inode_index:
        if not dest_rorp:
            dest_key = None
        elif dest_rorp.getnumlinks() == 1:
            dest_key = "NA"
        else:
            dest_key = get_inode_key(dest_rorp)
        digest = rorp.has_sha1() and rorp.get_sha1() or None
        _inode_index[rp_inode_key] = (rorp.index, rorp.getnumlinks(), dest_key,
                                      digest)
    return rp_inode_key


def del_rorp(rorp):
    """Remove rorp information from dictionary if seen all links"""
    if not rorp.isreg() or rorp.getnumlinks() < 2:
        return
    rp_inode_key = get_inode_key(rorp)
    val = _inode_index.get(rp_inode_key)
    if not val:
        return
    index, remaining, dest_key, digest = val
    if remaining == 1:
        del _inode_index[rp_inode_key]
        return 1
    else:
        _inode_index[rp_inode_key] = (index, remaining - 1, dest_key, digest)
        return 0


def rorp_eq(src_rorp, dest_rorp):
    """Compare hardlinked for equality

    Return false if dest_rorp is linked differently, which can happen
    if dest is linked more than source, or if it is represented by a
    different inode.

    """
    if (not src_rorp.isreg() or not dest_rorp.isreg()
            or src_rorp.getnumlinks() == dest_rorp.getnumlinks() == 1):
        return 1  # Hard links don't apply

    if src_rorp.getnumlinks() < dest_rorp.getnumlinks():
        return 0
    src_key = get_inode_key(src_rorp)
    index, remaining, dest_key, digest = _inode_index[src_key]
    if dest_key == "NA":
        # Allow this to be ok for first comparison, but not any
        # subsequent ones
        _inode_index[src_key] = (index, remaining, None, None)
        return 1
    try:
        return dest_key == get_inode_key(dest_rorp)
    except KeyError:
        return 0  # Inode key might be missing if the metadata file is corrupt


def islinked(rorp):
    """True if rorp's index is already linked to something on src side"""
    if not rorp.getnumlinks() > 1:
        return 0
    dict_val = _inode_index.get(get_inode_key(rorp))
    if not dict_val:
        return 0
    return dict_val[0] != rorp.index  # If equal, then rorp is first


def get_link_index(rorp):
    """Return first index on target side rorp is already linked to"""
    return _inode_index[get_inode_key(rorp)][0]


def get_sha1(rorp):
    """Return sha1 digest of what rorp is linked to"""
    return _inode_index[get_inode_key(rorp)][3]


def link_rp(diff_rorp, dest_rpath, dest_root=None):
    """Make dest_rpath into a link using link flag in diff_rorp"""
    if not dest_root:
        dest_root = dest_rpath  # use base of dest_rpath
    dest_link_rpath = dest_root.new_index(diff_rorp.get_link_flag())
    try:
        dest_rpath.hardlink(dest_link_rpath.path)
    except EnvironmentError as exc:
        # This can happen if the source of dest_link_rpath was deleted
        # after it's linking info was recorded but before
        # dest_link_rpath was written.
        if exc.errno == errno.ENOENT:
            dest_rpath.touch()  # This will cause an UpdateError later
        else:
            raise Exception("EnvironmentError '%s' linking %s to %s" %
                            (exc, dest_rpath.path, dest_link_rpath.path))
