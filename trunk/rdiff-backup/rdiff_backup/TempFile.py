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

"""Manage temp files

Earlier this had routines for keeping track of existing tempfiles.
Now we just use normal rpaths instead of the TempFile class.

"""

import os
import Globals, rpath

# To make collisions less likely, this gets put in the file name
# and incremented whenever a new file is requested.
_tfindex = 0

def new(rp_base):
	"""Return new tempfile that isn't in use in same dir as rp_base"""
	return new_in_dir(rp_base.get_parent_rp())

def new_in_dir(dir_rp):
	"""Return new temp rpath in directory dir_rp"""
	global _tfindex
	assert dir_rp.conn is Globals.local_connection
	while 1:
		if _tfindex > 100000000:
			Log("Warning: Resetting tempfile index", 2)
			_tfindex = 0
		tf = dir_rp.append('rdiff-backup.tmp.%d' % _tfindex)
		_tfindex = _tfindex+1
		if not tf.lstat(): return tf




class TempFile(rpath.RPath):
	"""Like an RPath, but keep track of which ones are still here"""
	def rename(self, rp_dest):
		"""Rename temp file to permanent location, possibly overwriting"""
		if not self.lstat(): # "Moving" empty file, so just delete
			if rp_dest.lstat(): rp_dest.delete()
			remove_listing(self)
			return

		if self.isdir() and not rp_dest.isdir():
			# Cannot move a directory directly over another file
			rp_dest.delete()
		rpath.rename(self, rp_dest)

		# Sometimes this just seems to fail silently, as in one
		# hardlinked twin is moved over the other.  So check to make
		# sure below.
		self.setdata()
		if self.lstat():
			rp_dest.delete()
			rpath.rename(self, rp_dest)
			self.setdata()
			if self.lstat(): raise OSError("Cannot rename tmp file correctly")
		remove_listing(self)

	def delete(self):
		rpath.RPath.delete(self)
		remove_listing(self)

