# Copyright 2002 Ben Escoto
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

from __future__ import generators
import cPickle
import Globals, Time, rpath, log, robust

# The keys in this dictionary are (inode, devloc) pairs.  The values
# are a pair (index, remaining_links, dest_key) where index is the
# rorp index of the first such linked file, remaining_links is the
# number of files hard linked to this one we may see, and key is
# either (dest_inode, dest_devloc) or None, and represents the
# hardlink info of the existing file on the destination.
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

def add_rorp(rorp, dest_rorp = None):
	"""Process new rorp and update hard link dictionaries"""
	if not rorp.isreg() or rorp.getnumlinks() < 2: return
	rp_inode_key = get_inode_key(rorp)
	if not _inode_index.has_key(rp_inode_key):
		if not dest_rorp: dest_key = None
		elif dest_rorp.getnumlinks() == 1: dest_key = "NA"
		else: dest_key = get_inode_key(dest_rorp)
		_inode_index[rp_inode_key] = (rorp.index, rorp.getnumlinks(), dest_key)

def del_rorp(rorp):
	"""Remove rorp information from dictionary if seen all links"""
	if not rorp.isreg() or rorp.getnumlinks() < 2: return
	rp_inode_key = get_inode_key(rorp)
	val = _inode_index.get(rp_inode_key)
	if not val: return
	index, remaining, dest_key = val
	if remaining == 1: del _inode_index[rp_inode_key]
	else: _inode_index[rp_inode_key] = (index, remaining-1, dest_key)

def rorp_eq(src_rorp, dest_rorp):
	"""Compare hardlinked for equality

	Return false if dest_rorp is linked differently, which can happen
	if dest is linked more than source, or if it is represented by a
	different inode.

	"""
	if (not src_rorp.isreg() or not dest_rorp.isreg() or
		src_rorp.getnumlinks() == dest_rorp.getnumlinks() == 1):
		return 1 # Hard links don't apply

	if src_rorp.getnumlinks() < dest_rorp.getnumlinks(): return 0
	src_key = get_inode_key(src_rorp)
	index, remaining, dest_key = _inode_index[src_key]
	if dest_key == "NA":
		# Allow this to be ok for first comparison, but not any
		# subsequent ones
		_inode_index[src_key] = (index, remaining, None)
		return 1
	return dest_key == get_inode_key(dest_rorp)

def islinked(rorp):
	"""True if rorp's index is already linked to something on src side"""
	if not rorp.getnumlinks() > 1: return 0
	dict_val = _inode_index.get(get_inode_key(rorp))
	if not dict_val: return 0
	return dict_val[0] != rorp.index # If equal, then rorp is first

def get_link_index(rorp):
	"""Return first index on target side rorp is already linked to"""
	return _inode_index[get_inode_key(rorp)][0]

def link_rp(diff_rorp, dest_rpath, dest_root = None):
	"""Make dest_rpath into a link using link flag in diff_rorp"""
	if not dest_root: dest_root = dest_rpath # use base of dest_rpath
	dest_link_rpath = dest_root.new_index(diff_rorp.get_link_flag())
	dest_rpath.hardlink(dest_link_rpath.path)

