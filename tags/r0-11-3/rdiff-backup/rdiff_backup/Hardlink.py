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

# In all of these lists of indicies are the values.  The keys in
# _inode_ ones are (inode, devloc) pairs.
_src_inode_indicies = None
_dest_inode_indicies = None

# The keys for these two are just indicies.  They share values
# with the earlier dictionaries.
_src_index_indicies = None
_dest_index_indicies = None

# When a linked file is restored, its path is added to this dict,
# so it can be found when later paths being restored are linked to
# it.
_restore_index_path = None

def initialize_dictionaries():
	"""Set all the hard link dictionaries to empty"""
	global _src_inode_indicies, _dest_inode_indicies
	global _src_index_indicies, _dest_index_indicies, _restore_index_path
	_src_inode_indicies = {}
	_dest_inode_indicies = {}
	_src_index_indicies = {}
	_dest_index_indicies = {}
	_restore_index_path = {}

def clear_dictionaries():
	"""Delete all dictionaries"""
	global _src_inode_indicies, _dest_inode_indicies
	global _src_index_indicies, _dest_index_indicies, _restore_index_path
	_src_inode_indicies = _dest_inode_indicies = None
	_src_index_indicies = _dest_index_indicies = _restore_index_path = None


def get_inode_key(rorp):
	"""Return rorp's key for _inode_ dictionaries"""
	return (rorp.getinode(), rorp.getdevloc())

def get_indicies(rorp, source):
	"""Return a list of similarly linked indicies, using rorp's index"""
	if source: dict = _src_index_indicies
	else: dict = _dest_index_indicies
	try: return dict[rorp.index]
	except KeyError: return []

def add_rorp(rorp, source):
	"""Process new rorp and update hard link dictionaries

	First enter it into src_inode_indicies.  If we have already
	seen all the hard links, then we can delete the entry.
	Everything must stay recorded in src_index_indicies though.

	"""
	if not rorp.isreg() or rorp.getnumlinks() < 2: return

	if source:
		inode_dict, index_dict = _src_inode_indicies, _src_index_indicies
	else: inode_dict, index_dict = _dest_inode_indicies, _dest_index_indicies

	rp_inode_key = get_inode_key(rorp)
	if inode_dict.has_key(rp_inode_key):
		index_list = inode_dict[rp_inode_key]
		index_list.append(rorp.index)
		if len(index_list) == rorp.getnumlinks():
			del inode_dict[rp_inode_key]
	else: # make new entry in both src dicts
		index_list = [rorp.index]
		inode_dict[rp_inode_key] = index_list
	index_dict[rorp.index] = index_list

def add_rorp_iter(iter, source):
	"""Return new rorp iterator like iter that add_rorp's first"""
	for rorp in iter:
		add_rorp(rorp, source)
		yield rorp

def rorp_eq(src_rorp, dest_rorp):
	"""Compare hardlinked for equality

	Two files may otherwise seem equal but be hardlinked in
	different ways.  This function considers them equal enough if
	they have been hardlinked correctly to the previously seen
	indicies.

	"""
	if (not src_rorp.isreg() or not dest_rorp.isreg() or
		src_rorp.getnumlinks() == dest_rorp.getnumlinks() == 1):
		return 1 # Hard links don't apply

	src_index_list = get_indicies(src_rorp, 1)
	dest_index_list = get_indicies(dest_rorp, None)

	# If a list only has one element, then it is only hardlinked
	# to itself so far, so that is not a genuine difference yet.
	if not src_index_list or len(src_index_list) == 1:
		return not dest_index_list or len(dest_index_list) == 1
	if not dest_index_list or len(dest_index_list) == 1: return None

	# Both index lists exist and are non-empty
	return src_index_list == dest_index_list # they are always sorted

def islinked(rorp):
	"""True if rorp's index is already linked to something on src side"""
	return len(get_indicies(rorp, 1)) >= 2

def get_link_index(rorp):
	"""Return first index on target side rorp is already linked to"""
	return get_indicies(rorp, 1)[0]

def restore_link(index, rpath):
	"""Restores a linked file by linking it

	When restoring, all the hardlink data is already present, and
	we can only link to something already written.  In either
	case, add to the _restore_index_path dict, so we know later
	that the file is available for hard
	linking.

	Returns true if succeeded in creating rpath, false if must
	restore rpath normally.

	"""
	if index not in _src_index_indicies: return None
	for linked_index in _src_index_indicies[index]:
		if linked_index in _restore_index_path:
			srcpath = _restore_index_path[linked_index]
			log.Log("Restoring %s by hard linking to %s" %
					(rpath.path, srcpath), 6)
			rpath.hardlink(srcpath)
			return 1
	_restore_index_path[index] = rpath.path
	return None

def link_rp(diff_rorp, dest_rpath, dest_root = None):
	"""Make dest_rpath into a link using link flag in diff_rorp"""
	if not dest_root: dest_root = dest_rpath # use base of dest_rpath
	dest_link_rpath = rpath.RPath(dest_root.conn, dest_root.base,
								  diff_rorp.get_link_flag())
	dest_rpath.hardlink(dest_link_rpath.path)




