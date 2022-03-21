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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA
"""
Preserve and restore hard links

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
# are a tuple (index, remaining_links, dest_key, sha1sum) where index
# is the rorp index of the first such linked file, remaining_links is
# the number of files hard linked to this one we may see, and key is
# either (dest_inode, dest_devloc) or None, and represents the
# hardlink info of the existing file on the destination.  Finally
# sha1sum is the hash of the file if it exists, or None.
_inode_index = {}

# This dictionary only holds sha1sum of old hardlinks
_inode_old_index = {}


def add_rorp(rorp, dest_rorp=None):
    """
    Process new rorp and update hard link dictionaries
    """
    if not rorp.isreg() or rorp.getnumlinks() < 2:
        return None
    rp_inode_key = _get_inode_key(rorp)
    if rp_inode_key not in _inode_index:
        if not dest_rorp:
            dest_key = None
        else:
            if dest_rorp.getnumlinks() == 1:
                dest_key = "NA"
            else:
                dest_key = _get_inode_key(dest_rorp)
            # we copy the hash from a potential old first hardlink
            if dest_key in _inode_old_index and not dest_rorp.has_sha1():
                old_hash = _inode_old_index.pop(dest_key)
                dest_rorp.set_sha1(old_hash)
        digest = rorp.has_sha1() and rorp.get_sha1() or None
        _inode_index[rp_inode_key] = (rorp.index, rorp.getnumlinks(), dest_key,
                                      digest)
    return rp_inode_key


def add_old_rorp(rorp):
    """
    A deleted first hardlink holds the information about a previous hash which is required later on
    """
    if not rorp.isreg() or rorp.getnumlinks() < 2 or not rorp.has_sha1():
        return None
    rp_inode_key = _get_inode_key(rorp)
    if rp_inode_key not in _inode_old_index:
        _inode_old_index[rp_inode_key] = rorp.get_sha1()
    return rp_inode_key


def del_rorp(rorp):
    """
    Remove rorp information from dictionary if seen all links
    """
    if not rorp.isreg() or rorp.getnumlinks() < 2:
        return
    rp_inode_key = _get_inode_key(rorp)
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
    """
    Compare hardlinked for equality

    Return false if dest_rorp is linked differently, which can happen
    if dest is linked more than source, or if it is represented by a
    different inode.
    """
    if (not src_rorp.isreg() or not dest_rorp.isreg()
            or src_rorp.getnumlinks() == dest_rorp.getnumlinks() == 1):
        return True  # Hard links don't apply

    # The sha1 of linked files is only stored in the metadata of the first
    # linked file on the dest side.  If the first linked file on the src side
    # is deleted, then the sha1 will also be deleted on the dest side, so we
    # test for this & report not equal so that another sha1 will be stored
    # with the next linked file on the dest side
    if (not is_linked(src_rorp) and not dest_rorp.has_sha1()):
        return False
    if src_rorp.getnumlinks() != dest_rorp.getnumlinks():
        return False
    src_key = _get_inode_key(src_rorp)
    index, remaining, dest_key, digest = _inode_index[src_key]
    if dest_key == "NA":
        # Allow this to be ok for first comparison, but not any
        # subsequent ones
        _inode_index[src_key] = (index, remaining, None, None)
        return True
    try:
        return dest_key == _get_inode_key(dest_rorp)
    except KeyError:
        # Inode key might be missing if the metadata file is corrupt
        return False


def is_linked(rorp):
    """
    True if rorp's index is already linked to something on src side
    """
    if not rorp.getnumlinks() > 1:
        return False
    dict_val = _inode_index.get(_get_inode_key(rorp))
    if not dict_val:
        return False
    return dict_val[0] != rorp.index  # If equal, then rorp is first


def get_link_index(rorp):
    """
    Return first index on target side rorp is already linked to
    """
    return _inode_index[_get_inode_key(rorp)][0]


def get_sha1(rorp):
    """
    Return sha1 digest of what rorp is linked to
    """
    return _inode_index[_get_inode_key(rorp)][3]


def get_hash(rorp):
    """
    Try to get a sha1 digest from the repository.  If hardlinks
    are saved in the metadata, get the sha1 from the first hardlink
    """
    add_rorp(rorp)
    if is_linked(rorp):
        verify_sha1 = get_sha1(rorp)
    elif rorp.has_sha1():
        verify_sha1 = rorp.get_sha1()
    else:
        verify_sha1 = None
    del_rorp(rorp)
    return verify_sha1


def link_rp(diff_rorp, dest_rpath, dest_root=None):
    """
    Make dest_rpath into a link using link flag in diff_rorp
    """
    if not dest_root:
        dest_root = dest_rpath  # use base of dest_rpath
    dest_link_rpath = dest_root.new_index(diff_rorp.get_link_flag())
    try:
        dest_rpath.hardlink(dest_link_rpath.path)
    except OSError as exc:
        # This can happen if the source of dest_link_rpath was deleted
        # after it's linking info was recorded but before
        # dest_link_rpath was written.
        if exc.errno == errno.ENOENT:
            dest_rpath.touch()  # This will cause an UpdateError later
        else:
            raise Exception("OS error '%s' linking %s to %s" %
                            (exc, dest_rpath.path, dest_link_rpath.path))


# === Internal functions  ===


def _get_inode_key(rorp):
    """
    Return rorp's key for _inode_ dictionaries
    """
    return (rorp.getinode(), rorp.getdevloc())
