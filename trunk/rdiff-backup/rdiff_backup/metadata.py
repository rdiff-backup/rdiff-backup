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

"""Store and retrieve metadata in destination directory

The plan is to store metadata information for all files in the
destination directory in a special metadata file.  There are two
reasons for this:

1)  The filesystem of the mirror directory may not be able to handle
    types of metadata that the source filesystem can.  For instance,
    rdiff-backup may not have root access on the destination side, so
    cannot set uid/gid.  Or the source side may have ACLs and the
    destination side doesn't.

	Hopefully every file system can store binary data.  Storing
	metadata separately allows us to back up anything (ok, maybe
	strange filenames are still a problem).

2)  Metadata can be more quickly read from a file than it can by
    traversing the mirror directory over and over again.  In many
    cases most of rdiff-backup's time is spent compaing metadata (like
    file size and modtime), trying to find differences.  Reading this
    data sequentially from a file is significantly less taxing than
    listing directories and statting files all over the mirror
    directory.

The metadata is stored in a text file, which is a bunch of records
concatenated together.  Each record has the format:

File <filename>
  <field_name1> <value>
  <field_name2> <value>
  ...

Where the lines are separated by newlines.  See the code below for the
field names and values.

"""

from __future__ import generators
import re, gzip, os, binascii
import log, Globals, rpath, Time, robust, increment, static

class ParsingError(Exception):
	"""This is raised when bad or unparsable data is received"""
	pass


def RORP2Record(rorpath):
	"""From RORPath, return text record of file's metadata"""
	str_list = ["File %s\n" % quote_path(rorpath.get_indexpath())]

	# Store file type, e.g. "dev", "reg", or "sym", and type-specific data
	type = rorpath.gettype()
	if type is None: type = "None"
	str_list.append("  Type %s\n" % type)
	if type == "reg":
		str_list.append("  Size %s\n" % rorpath.getsize())

		# If there is a resource fork, save it.
		if rorpath.has_resource_fork():
			if not rorpath.get_resource_fork(): rf = "None"
			else: rf = binascii.hexlify(rorpath.get_resource_fork())
			str_list.append("  ResourceFork %s\n" % (rf,))

		# If file is hardlinked, add that information
		if Globals.preserve_hardlinks:
			numlinks = rorpath.getnumlinks()
			if numlinks > 1:
				str_list.append("  NumHardLinks %s\n" % numlinks)
				str_list.append("  Inode %s\n" % rorpath.getinode())
				str_list.append("  DeviceLoc %s\n" % rorpath.getdevloc())

	elif type == "None": return "".join(str_list)
	elif type == "dir" or type == "sock" or type == "fifo": pass
	elif type == "sym":
		str_list.append("  SymData %s\n" % quote_path(rorpath.readlink()))
	elif type == "dev":
		major, minor = rorpath.getdevnums()
		if rorpath.isblkdev(): devchar = "b"
		else:
			assert rorpath.ischardev()
			devchar = "c"
		str_list.append("  DeviceNum %s %s %s\n" % (devchar, major, minor))

	# Store time information
	if type != 'sym' and type != 'dev':
		str_list.append("  ModTime %s\n" % rorpath.getmtime())

	# Add user, group, and permission information
	uid, gid = rorpath.getuidgid()
	str_list.append("  Uid %s\n" % uid)
	str_list.append("  Gid %s\n" % gid)
	str_list.append("  Permissions %s\n" % rorpath.getperms())
	return "".join(str_list)

line_parsing_regexp = re.compile("^ *([A-Za-z0-9]+) (.+)$", re.M)
def Record2RORP(record_string):
	"""Given record_string, return RORPath

	For speed reasons, write the RORPath data dictionary directly
	instead of calling rorpath functions.  Profiling has shown this to
	be a time critical function.

	"""
	data_dict = {}
	for field, data in line_parsing_regexp.findall(record_string):
		if field == "File": index = quoted_filename_to_index(data)
		elif field == "Type":
			if data == "None": data_dict['type'] = None
			else: data_dict['type'] = data
		elif field == "Size": data_dict['size'] = long(data)
		elif field == "ResourceFork":
			if data == "None": data_dict['resourcefork'] = ""
			else: data_dict['resourcefork'] = binascii.unhexlify(data)
		elif field == "NumHardLinks": data_dict['nlink'] = int(data)
		elif field == "Inode": data_dict['inode'] = long(data)
		elif field == "DeviceLoc": data_dict['devloc'] = long(data)
		elif field == "SymData": data_dict['linkname'] = unquote_path(data)
		elif field == "DeviceNum":
			devchar, major_str, minor_str = data.split(" ")
			data_dict['devnums'] = (devchar, int(major_str), int(minor_str))
		elif field == "ModTime": data_dict['mtime'] = long(data)
		elif field == "Uid": data_dict['uid'] = int(data)
		elif field == "Gid": data_dict['gid'] = int(data)
		elif field == "Permissions": data_dict['perms'] = int(data)
		else: raise ParsingError("Unknown field in line '%s'" % line)
	return rpath.RORPath(index, data_dict)

chars_to_quote = re.compile("\\n|\\\\")
def quote_path(path_string):
	"""Return quoted verson of path_string

	Because newlines are used to separate fields in a record, they are
	replaced with \n.  Backslashes become \\ and everything else is
	left the way it is.

	"""
	def replacement_func(match_obj):
		"""This is called on the match obj of any char that needs quoting"""
		char = match_obj.group(0)
		if char == "\n": return "\\n"
		elif char == "\\": return "\\\\"
		assert 0, "Bad char %s needs quoting" % char
	return chars_to_quote.sub(replacement_func, path_string)

def unquote_path(quoted_string):
	"""Reverse what was done by quote_path"""
	def replacement_func(match_obj):
		"""Unquote match obj of two character sequence"""
		two_chars = match_obj.group(0)
		if two_chars == "\\n": return "\n"
		elif two_chars == "\\\\": return "\\"
		log.Log("Warning, unknown quoted sequence %s found" % two_chars, 2)
		return two_chars
	return re.sub("\\\\n|\\\\\\\\", replacement_func, quoted_string)

def quoted_filename_to_index(quoted_filename):
	"""Return tuple index given quoted filename"""
	if quoted_filename == '.': return ()
	else: return tuple(unquote_path(quoted_filename).split('/'))

class FlatExtractor:
	"""Controls iterating objects from flat file"""

	# Set this in subclass.  record_boundary_regexp should match
	# beginning of next record.  The first group should start at the
	# beginning of the record.  The second group should contain the
	# (possibly quoted) filename.
	record_boundary_regexp = None

	# Set in subclass to function that converts text record to object
	record_to_object = None

	def __init__(self, fileobj):
		self.fileobj = fileobj # holds file object we are reading from
		self.buf = "" # holds the next part of the file
		self.at_end = 0 # True if we are at the end of the file
		self.blocksize = 32 * 1024

	def get_next_pos(self):
		"""Return position of next record in buffer, or end pos if none"""
		while 1:
			m = self.record_boundary_regexp.search(self.buf, 1)
			if m: return m.start(1)
			else: # add next block to the buffer, loop again
				newbuf = self.fileobj.read(self.blocksize)
				if not newbuf:
					self.at_end = 1
					return len(self.buf)
				else: self.buf += newbuf

	def iterate(self):
		"""Return iterator that yields all objects with records"""
		while 1:
			next_pos = self.get_next_pos()
			try: yield self.record_to_object(self.buf[:next_pos])
			except ParsingError, e:
				if self.at_end: break # Ignore whitespace/bad records at end
				log.Log("Error parsing flat file: %s" % (e,), 2)
			if self.at_end: break
			self.buf = self.buf[next_pos:]
		assert not self.close()

	def skip_to_index(self, index):
		"""Scan through the file, set buffer to beginning of index record

		Here we make sure that the buffer always ends in a newline, so
		we will not be splitting lines in half.

		"""
		assert not self.buf or self.buf.endswith("\n")
		while 1:
			self.buf = self.fileobj.read(self.blocksize)
			self.buf += self.fileobj.readline()
			if not self.buf:
				self.at_end = 1
				return
			while 1:
				m = self.record_boundary_regexp.search(self.buf)
				if not m: break
				cur_index = self.filename_to_index(m.group(2))
				if cur_index >= index:
					self.buf = self.buf[m.start(1):]
					return
				else: self.buf = self.buf[m.end(1):]

	def iterate_starting_with(self, index):
		"""Iterate objects whose index starts with given index"""
		self.skip_to_index(index)
		if self.at_end: return
		while 1:
			next_pos = self.get_next_pos()
			try: obj = self.record_to_object(self.buf[:next_pos])
			except ParsingError, e:
				log.Log("Error parsing metadata file: %s" % (e,), 2)
			else:
				if obj.index[:len(index)] != index: break
				yield obj
			if self.at_end: break
			self.buf = self.buf[next_pos:]
		assert not self.close()

	def filename_to_index(self, filename):
		"""Translate filename, possibly quoted, into an index tuple

		The filename is the first group matched by
		regexp_boundary_regexp.

		"""
		assert 0 # subclass

	def close(self):
		"""Return value of closing associated file"""
		return self.fileobj.close()

class RorpExtractor(FlatExtractor):
	"""Iterate rorps from metadata file"""
	record_boundary_regexp = re.compile("(?:\\n|^)(File (.*?))\\n")
	record_to_object = staticmethod(Record2RORP)
	filename_to_index = staticmethod(quoted_filename_to_index)


class FlatFile:
	"""Manage a flat (probably text) file containing info on various files

	This is used for metadata information, and possibly EAs and ACLs.
	The main read interface is as an iterator.  The storage format is
	a flat, probably compressed file, so random access is not
	recommended.

	"""
	_prefix = None # Set this to real prefix when subclassing
	_rp, _fileobj = None, None
	# Buffering may be useful because gzip writes are slow
	_buffering_on = 1
	_record_buffer, _max_buffer_size = None, 100
	_extractor = FlatExtractor # Set to class that iterates objects

	def open_file(cls, rp = None, compress = 1):
		"""Open file for writing.  Use cls._rp if rp not given."""
		assert not cls._fileobj, "Flatfile already open"
		cls._record_buffer = []
		if rp: cls._rp = rp
		else:
			if compress: typestr = 'snapshot.gz'
			else: typestr = 'snapshot'
			cls._rp = Globals.rbdir.append(
				"%s.%s.%s" % (cls._prefix, Time.curtimestr, typestr))
		cls._fileobj = cls._rp.open("wb", compress = compress)

	def write_object(cls, object):
		"""Convert one object to record and write to file"""
		record = cls._object_to_record(object)
		if cls._buffering_on:
			cls._record_buffer.append(record)
			if len(cls._record_buffer) >= cls._max_buffer_size:
				cls._fileobj.write("".join(cls._record_buffer))
				cls._record_buffer = []
		else: cls._fileobj.write(record)

	def close_file(cls):
		"""Close file, for when any writing is done"""
		assert cls._fileobj, "File already closed"
		if cls._buffering_on and cls._record_buffer: 
			cls._fileobj.write("".join(cls._record_buffer))
			cls._record_buffer = []
		try: fileno = cls._fileobj.fileno() # will not work if GzipFile
		except AttributeError: fileno = cls._fileobj.fileobj.fileno()
		os.fsync(fileno)
		result = cls._fileobj.close()
		cls._fileobj = None
		cls._rp.setdata()
		return result

	def get_objects(cls, restrict_index = None, compressed = None):
		"""Return iterator of objects records from file rp"""
		assert cls._rp, "Must have rp set before get_objects can be used"
		if compressed is None:
			if cls._rp.isincfile():
				compressed = cls._rp.inc_compressed
				assert (cls._rp.inc_type == 'data' or
						cls._rp.inc_type == 'snapshot'), cls._rp.inc_type
			else: compressed = cls._rp.get_indexpath().endswith('.gz')

		fileobj = cls._rp.open('rb', compress = compressed)
		if not restrict_index: return cls._extractor(fileobj).iterate()
		else:
			re = cls._extractor(fileobj)
			return re.iterate_starting_with(restrict_index)
		
	def get_objects_at_time(cls, rbdir, time, restrict_index = None,
							rblist = None):
		"""Scan through rbdir, finding data at given time, iterate

		If rblist is givenr, use that instead of listing rbdir.  Time
		here is exact, we don't take the next one older or anything.
		Returns None if no file matching prefix is found.

		"""
		if rblist is None:
			rblist = map(lambda x: rbdir.append(x), robust.listrp(rbdir))

		for rp in rblist:
			if (rp.isincfile() and
				(rp.getinctype() == "data" or rp.getinctype() == "snapshot")
				and rp.getincbase_str() == cls._prefix):
				if rp.getinctime() == time:
					cls._rp = rp
					return cls.get_objects(restrict_index)
		return None

static.MakeClass(FlatFile)

class MetadataFile(FlatFile):
	"""Store/retrieve metadata from mirror_metadata as rorps"""
	_prefix = "mirror_metadata"
	_extractor = RorpExtractor
	_object_to_record = staticmethod(RORP2Record)

