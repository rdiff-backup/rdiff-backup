# Copyright 2005 Ben Escoto
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

"""Contains a file wrapper that returns a hash on close"""

# Until rdiff-backup is ported to Python 3 (or abandons support for versions
# below Python 2.5), we'll ignore the warning about the deprecated sha module
import warnings
warnings.filterwarnings("ignore", ".*sha module.*", DeprecationWarning)

import sha
import Globals

class FileWrapper:
	"""Wrapper around a file-like object

	Only use this with files that will be read through in a single
	pass and then closed.  (There is no seek().)  When you close it,
	return value will be a Report.

	Currently this just calculates a sha1sum of the datastream.

	"""
	def __init__(self, fileobj):
		self.fileobj = fileobj
		self.sha1 = sha.new()
		self.closed = 0

	def read(self, length = -1):
		assert not self.closed
		buf = self.fileobj.read(length)
		self.sha1.update(buf)
		return buf

	def close(self):
		return Report(self.fileobj.close(), self.sha1.hexdigest())


class Report:
	"""Hold final information about a byte stream"""
	def __init__(self, close_val, sha1_digest):
		assert not close_val # For now just assume inner file closes correctly
		self.sha1_digest = sha1_digest


def compute_sha1(rp, compressed = 0):
	"""Return the hex sha1 hash of given rpath"""
	assert rp.conn is Globals.local_connection # inefficient not to do locally
	digest = compute_sha1_fp(rp.open("rb", compressed))
	rp.set_sha1(digest)
	return digest

def compute_sha1_fp(fp, compressed = 0):
	"""Return hex sha1 hash of given file-like object"""
	blocksize = Globals.blocksize
	fw = FileWrapper(fp)
	while 1:
		if not fw.read(blocksize): break
	return fw.close().sha1_digest


