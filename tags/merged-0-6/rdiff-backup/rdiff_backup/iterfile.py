execfile("ttime.py")
import cPickle

#######################################################################
#
# iterfile - Convert an iterator to a file object and vice-versa
#

class IterFileException(Exception): pass

class UnwrapFile:
	"""Contains some basic methods for parsing a file containing an iter"""
	def __init__(self, file):
		self.file = file

	def _s2l(self, s):
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
		assert len(header) == 8, "Header is only %d bytes" % len(header)
		type, length = header[0], self._s2l(header[1:])
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
		self.bufferlist = [initial_data]
		self.bufferlen = len(initial_data)
		self.closed = None

	def check_consistency(self):
		l = len("".join(self.bufferlist))
		assert l == self.bufferlen, \
			   "Length of IVF bufferlist doesn't match (%s, %s)" % \
			   (l, self.bufferlen)

	def read(self, length):
		assert not self.closed
		if self.iwf.currently_in_file:
			while length >= self.bufferlen:
				if not self.addtobuffer(): break

		real_len = min(length, self.bufferlen)
		combined_buffer = "".join(self.bufferlist)
		assert len(combined_buffer) == self.bufferlen, \
			   (len(combined_buffer), self.bufferlen)
		self.bufferlist = [combined_buffer[real_len:]]
		self.bufferlen = self.bufferlen - real_len
		return combined_buffer[:real_len]
			
	def addtobuffer(self):
		"""Read a chunk from the file and add it to the buffer"""
		assert self.iwf.currently_in_file
		type, data = self._get()
		assert type == "c", "Type is %s instead of c" % type
		if data:
			self.bufferlen = self.bufferlen + len(data)
			self.bufferlist.append(data)
			return 1
		else:
			self.iwf.currently_in_file = None
			return None

	def close(self):
		"""Currently just reads whats left and discards it"""
		while self.iwf.currently_in_file:
			self.addtobuffer()
			self.bufferlist = []
			self.bufferlen = 0
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
		self.bufferlist = []
		self.bufferlen = 0L
		self.currently_in_file = None
		self.closed = None

	def read(self, length):
		"""Return next length bytes in file"""
		assert not self.closed
		while self.bufferlen < length:
			if not self.addtobuffer(): break

		combined_buffer = "".join(self.bufferlist)
		assert len(combined_buffer) == self.bufferlen
		real_len = min(self.bufferlen, length)
		self.bufferlen = self.bufferlen - real_len
		self.bufferlist = [combined_buffer[real_len:]]
		return combined_buffer[:real_len]

	def addtobuffer(self):
		"""Updates self.bufferlist and self.bufferlen, adding on a chunk

		Returns None if we have reached the end of the iterator,
		otherwise return true.

		"""
		if self.currently_in_file:
			buf = "c" + self.addfromfile()
		else:
			try: currentobj = self.iter.next()
			except StopIteration: return None
			if hasattr(currentobj, "read") and hasattr(currentobj, "close"):
				self.currently_in_file = currentobj
				buf = "f" + self.addfromfile()
			else:
				pickle = cPickle.dumps(currentobj, 1)
				buf = "o" + self._l2s(len(pickle)) + pickle
				
		self.bufferlist.append(buf)
		self.bufferlen = self.bufferlen + len(buf)
		return 1

	def addfromfile(self):
		"""Read a chunk from the current file and return it"""
		buf = self.currently_in_file.read(Globals.blocksize)
		if not buf:
			assert not self.currently_in_file.close()
			self.currently_in_file = None
		return self._l2s(len(buf)) + buf

	def _l2s(self, l):
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
	over a connection.

	"""
	def __init__(self, file):
		self.file = file
		self.buffer = ""
		self.bufsize = Globals.conn_bufsize

	def read(self, l = -1):
		if l < 0: # Read as much as possible
			result = self.buffer + self.file.read()
			self.buffer = ""
			return result

		if len(self.buffer) < l: # Try to make buffer as long as l
			self.buffer += self.file.read(max(self.bufsize,
											  l - len(self.buffer)))
		actual_size = min(l, len(self.buffer))
		result = self.buffer[:actual_size]
		self.buffer = self.buffer[actual_size:]
		return result

	def close(self): return self.file.close()
