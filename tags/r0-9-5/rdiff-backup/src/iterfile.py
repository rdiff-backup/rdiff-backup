# Copyright 2002 Ben Escoto
#
# This file is part of rdiff-backup.
#
# rdiff-backup is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, Inc., 675 Mass Ave, Cambridge MA
# 02139, USA; either version 2 of the License, or (at your option) any
# later version; incorporated herein by reference.

"""Convert an iterator to a file object and vice-versa"""

import cPickle, array
import Globals, C


class IterFileException(Exception): pass

class UnwrapFile:
	"""Contains some basic methods for parsing a file containing an iter"""
	def __init__(self, file):
		self.file = file

	def _s2l_old(self, s):
		"""Convert string to long int"""
		assert len(s) == 7
		l = 0L
		for i in range(7): l = l*256 + ord(s[i])
		return l

	def _get(self):
		"""Return pair (type, data) next in line on the file

		type is a single character which is either "o" for object, "f"
		for file, "c" for a continution of a file, or None if no more
		data can be read.  Data is either the file's data, if type is
		"c" or "f", or the actual object if the type is "o".

		"""
		header = self.file.read(8)
		if not header: return None, None
		if len(header) != 8:
			assert None, "Header %s is only %d bytes" % (header, len(header))
		type, length = header[0], C.str2long(header[1:])
		buf = self.file.read(length)
		if type == "o": return type, cPickle.loads(buf)
		else: return type, buf


class IterWrappingFile(UnwrapFile):
	"""An iterator generated from a file.

	Initialize with a file type object, and then it will return the
	elements of the file in order.

	"""
	def __init__(self, file):
		UnwrapFile.__init__(self, file)
		self.currently_in_file = None

	def __iter__(self): return self

	def next(self):
		if self.currently_in_file:
			self.currently_in_file.close() # no error checking by this point
		type, data = self._get()
		if not type: raise StopIteration
		if type == "o": return data
		elif type == "f":
			file = IterVirtualFile(self, data)
			if data: self.currently_in_file = file
			else: self.currently_in_file = None
			return file
		else: raise IterFileException("Bad file type %s" % type)


class IterVirtualFile(UnwrapFile):
	"""Another version of a pretend file

	This is returned by IterWrappingFile when a file is embedded in
	the main file that the IterWrappingFile is based around.

	"""
	def __init__(self, iwf, initial_data):
		"""Initializer

		initial_data is the data from the first block of the file.
		iwf is the iter wrapping file that spawned this
		IterVirtualFile.

		"""
		UnwrapFile.__init__(self, iwf.file)
		self.iwf = iwf
		self.buffer = initial_data
		self.closed = None

	def read(self, length = -1):
		"""Read length bytes from the file, updating buffers as necessary"""
		assert not self.closed
		if self.iwf.currently_in_file:
			if length >= 0:
				while length >= len(self.buffer):
					if not self.addtobuffer(): break
				real_len = min(length, len(self.buffer))
			else:
				while 1:
					if not self.addtobuffer(): break
				real_len = len(self.buffer)
		else: real_len = min(length, len(self.buffer))

		return_val = self.buffer[:real_len]
		self.buffer = self.buffer[real_len:]
		return return_val
			
	def addtobuffer(self):
		"""Read a chunk from the file and add it to the buffer"""
		assert self.iwf.currently_in_file
		type, data = self._get()
		assert type == "c", "Type is %s instead of c" % type
		if data:
			self.buffer += data
			return 1
		else:
			self.iwf.currently_in_file = None
			return None

	def close(self):
		"""Currently just reads whats left and discards it"""
		while self.iwf.currently_in_file:
			self.addtobuffer()
			self.buffer = ""
		self.closed = 1


class FileWrappingIter:
	"""A file interface wrapping around an iterator

	This is initialized with an iterator, and then converts it into a
	stream of characters.  The object will evaluate as little of the
	iterator as is necessary to provide the requested bytes.

	The actual file is a sequence of marshaled objects, each preceded
	by 8 bytes which identifies the following the type of object, and
	specifies its length.  File objects are not marshalled, but the
	data is written in chunks of Globals.blocksize, and the following
	blocks can identify themselves as continuations.

	"""
	def __init__(self, iter):
		"""Initialize with iter"""
		self.iter = iter
		self.array_buf = array.array('c')
		self.currently_in_file = None
		self.closed = None

	def read(self, length):
		"""Return next length bytes in file"""
		assert not self.closed
		while len(self.array_buf) < length:
			if not self.addtobuffer(): break

		result = self.array_buf[:length].tostring()
		del self.array_buf[:length]
		return result

	def addtobuffer(self):
		"""Updates self.buffer, adding a chunk from the iterator.

		Returns None if we have reached the end of the iterator,
		otherwise return true.

		"""
		array_buf = self.array_buf
		if self.currently_in_file:
			array_buf.fromstring("c")
			array_buf.fromstring(self.addfromfile())
		else:
			try: currentobj = self.iter.next()
			except StopIteration: return None
			if hasattr(currentobj, "read") and hasattr(currentobj, "close"):
				self.currently_in_file = currentobj
				array_buf.fromstring("f")
				array_buf.fromstring(self.addfromfile())
			else:
				pickle = cPickle.dumps(currentobj, 1)
				array_buf.fromstring("o")
				array_buf.fromstring(C.long2str(long(len(pickle))))
				array_buf.fromstring(pickle)
		return 1

	def addfromfile(self):
		"""Read a chunk from the current file and return it"""
		# Check file read for errors, buf = "" if find one
		buf = Robust.check_common_error(self.read_error_handler,
										self.currently_in_file.read,
										[Globals.blocksize])
		if not buf:
			assert not self.currently_in_file.close()
			self.currently_in_file = None
		return C.long2str(long(len(buf))) + buf

	def read_error_handler(self, exc, blocksize):
		"""Log error when reading from file"""
		Log("Error '%s' reading from fileobj, truncating" % (str(exc),), 2)
		return ""

	def _l2s_old(self, l):
		"""Convert long int to string of 7 characters"""
		s = ""
		for i in range(7):
			l, remainder = divmod(l, 256)
			s = chr(remainder) + s
		assert remainder == 0
		return s

	def close(self): self.closed = 1


class BufferedRead:
	"""Buffer the .read() calls to the given file

	This is used to lessen overhead and latency when a file is sent
	over a connection.  Profiling said that arrays were faster than
	strings here.

	"""
	def __init__(self, file):
		self.file = file
		self.array_buf = array.array('c')
		self.bufsize = Globals.conn_bufsize

	def read(self, l = -1):
		array_buf = self.array_buf
		if l < 0: # Read as much as possible
			result = array_buf.tostring() + self.file.read()
			del array_buf[:]
			return result

		if len(array_buf) < l: # Try to make buffer at least as long as l
			array_buf.fromstring(self.file.read(max(self.bufsize, l)))
		result = array_buf[:l].tostring()
		del array_buf[:l]
		return result

	def close(self): return self.file.close()

from log import *
from robust import *
