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
import re, gzip, os
import log, Globals, rpath, Time, robust, increment

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

line_parsing_regexp = re.compile("^ *([A-Za-z0-9]+) (.+)$")
def Record2RORP(record_string):
	"""Given record_string, return RORPath

	For speed reasons, write the RORPath data dictionary directly
	instead of calling rorpath functions.  This depends on the 

	"""
	data_dict = {}
	index_list = [None] # put in list so we can modify using parse_line
	def process_line(line):
		"""Process given line, and modify data_dict or index_list"""
		if not line: return # skip empty lines
		match = line_parsing_regexp.search(line)
		if not match: raise ParsingError("Bad line: '%s'" % line)
		field, data = match.group(1), match.group(2)

		if field == "File":
			if data == ".": index_list[0] = ()
			else: index_list[0] = tuple(unquote_path(data).split("/"))
		elif field == "Type":
			if data == "None": data_dict['type'] = None
			else: data_dict['type'] = data
		elif field == "Size": data_dict['size'] = long(data)
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
		
	map(process_line, record_string.split("\n"))
	return rpath.RORPath(index_list[0], data_dict)

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


def write_rorp_iter_to_file(rorp_iter, file):
	"""Given iterator of RORPs, write records to (pre-opened) file object"""
	for rorp in rorp_iter: file.write(RORP2Record(rorp))

class rorp_extractor:
	"""Controls iterating rorps from metadata file"""
	def __init__(self, fileobj):
		self.fileobj = fileobj # holds file object we are reading from
		self.buf = "" # holds the next part of the file
		self.record_boundary_regexp = re.compile("\\nFile")
		self.at_end = 0 # True if we are at the end of the file
		self.blocksize = 32 * 1024

	def get_next_pos(self):
		"""Return position of next record in buffer"""
		while 1:
			m = self.record_boundary_regexp.search(self.buf)
			if m: return m.start(0)+1 # the +1 skips the newline
			else: # add next block to the buffer, loop again
				newbuf = self.fileobj.read(self.blocksize)
				if not newbuf:
					self.at_end = 1
					return len(self.buf)
				else: self.buf += newbuf

	def iterate(self):
		"""Return iterator over all records"""
		while 1:
			next_pos = self.get_next_pos()
			try: yield Record2RORP(self.buf[:next_pos])
			except ParsingError, e:
				log.Log("Error parsing metadata file: %s" % (e,), 2)
			if self.at_end: break
			self.buf = self.buf[next_pos:]
		assert not self.close()

	def skip_to_index(self, index):
		"""Scan through the file, set buffer to beginning of index record

		Here we make sure that the buffer always ends in a newline, so
		we will not be splitting lines in half.

		"""
		assert not self.buf or self.buf.endswith("\n")
		if not index: indexpath = "."
		else: indexpath = "/".join(index)
		# Must double all backslashes, because they will be
		# reinterpreted.  For instance, to search for index \n
		# (newline), it will be \\n (backslash n) in the file, so the
		# regular expression is "File \\\\n\\n" (File two backslash n
		# backslash n)
		double_quote = re.sub("\\\\", "\\\\\\\\", indexpath)
		begin_re = re.compile("(^|\\n)(File %s\\n)" % (double_quote,))
		while 1:
			m = begin_re.search(self.buf)
			if m:
				self.buf = self.buf[m.start(2):]
				return
			self.buf = self.fileobj.read(self.blocksize)
			self.buf += self.fileobj.readline()
			if not self.buf:
				self.at_end = 1
				return

	def iterate_starting_with(self, index):
		"""Iterate records whose index starts with given index"""
		self.skip_to_index(index)
		if self.at_end: return
		while 1:
			next_pos = self.get_next_pos()
			try: rorp = Record2RORP(self.buf[:next_pos])
			except ParsingError, e:
				log.Log("Error parsing metadata file: %s" % (e,), 2)
			else:
				if rorp.index[:len(index)] != index: break
				yield rorp
			if self.at_end: break
			self.buf = self.buf[next_pos:]
		assert not self.close()

	def close(self):
		"""Return value of closing associated file"""
		return self.fileobj.close()


metadata_rp = None
metadata_fileobj = None
def OpenMetadata(rp = None, compress = 1):
	"""Open the Metadata file for writing, return metadata fileobj"""
	global metadata_rp, metadata_fileobj
	assert not metadata_fileobj, "Metadata file already open"
	if rp: metadata_rp = rp
	else:
		if compress: typestr = 'snapshot.gz'
		else: typestr = 'snapshot'
		metadata_rp = Globals.rbdir.append("mirror_metadata.%s.%s" %
										   (Time.curtimestr, typestr))
	metadata_fileobj = metadata_rp.open("wb", compress = compress)

def WriteMetadata(rorp):
	"""Write metadata of rorp to file"""
	global metadata_fileobj
	metadata_fileobj.write(RORP2Record(rorp))

def CloseMetadata():
	"""Close the metadata file"""
	global metadata_rp, metadata_fileobj
	assert metadata_fileobj, "Metadata file not open"
	try: fileno = metadata_fileobj.fileno() # will not work if GzipFile
	except AttributeError: fileno = metadata_fileobj.fileobj.fileno()
	os.fsync(fileno)
	result = metadata_fileobj.close()
	metadata_fileobj = None
	metadata_rp.setdata()
	return result

def GetMetadata(rp, restrict_index = None, compressed = None):
	"""Return iterator of metadata from given metadata file rp"""
	if compressed is None:
		if rp.isincfile():
			compressed = rp.inc_compressed
			assert rp.inc_type == "data" or rp.inc_type == "snapshot"
		else: compressed = rp.get_indexpath().endswith(".gz")

	fileobj = rp.open("rb", compress = compressed)
	if restrict_index is None: return rorp_extractor(fileobj).iterate()
	else: return rorp_extractor(fileobj).iterate_starting_with(restrict_index)

def GetMetadata_at_time(rbdir, time, restrict_index = None, rblist = None):
	"""Scan through rbdir, finding metadata file at given time, iterate

	If rdlist is given, use that instead of listing rddir.  Time here
	is exact, we don't take the next one older or anything.  Returns
	None if no matching metadata found.

	"""
	if rblist is None: rblist = map(lambda x: rbdir.append(x),
									robust.listrp(rbdir))
	for rp in rblist:
		if (rp.isincfile() and
			(rp.getinctype() == "data" or rp.getinctype() == "snapshot") and
			rp.getincbase_str() == "mirror_metadata"):
			if rp.getinctime() == time: return GetMetadata(rp, restrict_index)
	return None


