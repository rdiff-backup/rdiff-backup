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

"""Manage temp files"""

import os
import Globals, rpath

# This is a connection-specific list of temp files, to be cleaned
# up before rdiff-backup exits.
_tempfiles = []

# To make collisions less likely, this gets put in the file name
# and incremented whenever a new file is requested.
_tfindex = 0

def new(rp_base, same_dir = 1):
	"""Return new tempfile that isn't in use.

	If same_dir, tempfile will be in same directory as rp_base.
	Otherwise, use tempfile module to get filename.

	"""
	conn = rp_base.conn
	if conn is not Globals.local_connection:
		return conn.TempFile.new(rp_base, same_dir)

	def find_unused(conn, dir):
		"""Find an unused tempfile with connection conn in directory dir"""
		global _tfindex, tempfiles
		while 1:
			if _tfindex > 100000000:
				Log("Resetting index", 2)
				_tfindex = 0
			tf = TempFile(conn, os.path.join(dir,
								   "rdiff-backup.tmp.%d" % _tfindex))
			_tfindex = _tfindex+1
			if not tf.lstat(): return tf

	if same_dir: tf = find_unused(conn, rp_base.dirsplit()[0])
	else: tf = TempFile(conn, tempfile.mktemp())
	_tempfiles.append(tf)
	return tf

def remove_listing(tempfile):
	"""Remove listing of tempfile"""
	if Globals.local_connection is not tempfile.conn:
		tempfile.conn.TempFile.remove_listing(tempfile)
	elif tempfile in _tempfiles: _tempfiles.remove(tempfile)

def delete_all():
	"""Delete all remaining tempfiles"""
	for tf in _tempfiles[:]: tf.delete()


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

