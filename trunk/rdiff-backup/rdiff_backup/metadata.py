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

import re, log, Globals, rpath

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
