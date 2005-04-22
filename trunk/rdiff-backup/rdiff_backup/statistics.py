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

"""Generate and process aggregated backup information"""

import re, os, time
import Globals, Time, increment, log, static, metadata

class StatsException(Exception): pass

class StatsObj:
	"""Contains various statistics, provide string conversion functions"""
	# used when quoting files in get_stats_line
	space_regex = re.compile(" ")

	stat_file_attrs = ('SourceFiles', 'SourceFileSize',
					   'MirrorFiles', 'MirrorFileSize',
					   'NewFiles', 'NewFileSize',
					   'DeletedFiles', 'DeletedFileSize',
					   'ChangedFiles',
					   'ChangedSourceSize', 'ChangedMirrorSize',
					   'IncrementFiles', 'IncrementFileSize')
	stat_misc_attrs = ('Errors', 'TotalDestinationSizeChange')
	stat_time_attrs = ('StartTime', 'EndTime', 'ElapsedTime')
	stat_attrs = (('Filename',) + stat_time_attrs +
				  stat_misc_attrs + stat_file_attrs)

	# Below, the second value in each pair is true iff the value
	# indicates a number of bytes
	stat_file_pairs = (('SourceFiles', None), ('SourceFileSize', 1),
					   ('MirrorFiles', None), ('MirrorFileSize', 1),
					   ('NewFiles', None), ('NewFileSize', 1),
					   ('DeletedFiles', None), ('DeletedFileSize', 1),
					   ('ChangedFiles', None),
					   ('ChangedSourceSize', 1), ('ChangedMirrorSize', 1),
					   ('IncrementFiles', None), ('IncrementFileSize', 1))

	# This is used in get_byte_summary_string below
	byte_abbrev_list = ((1024*1024*1024*1024, "TB"),
						(1024*1024*1024, "GB"),
						(1024*1024, "MB"),
						(1024, "KB"))

	def __init__(self):
		"""Set attributes to None"""
		for attr in self.stat_attrs: self.__dict__[attr] = None

	def get_stat(self, attribute):
		"""Get a statistic"""
		return self.__dict__[attribute]

	def set_stat(self, attr, value):
		"""Set attribute to given value"""
		self.__dict__[attr] = value

	def increment_stat(self, attr):
		"""Add 1 to value of attribute"""
		self.__dict__[attr] += 1

	def add_to_stat(self, attr, value):
		"""Add value to given attribute"""
		self.__dict__[attr] += value

	def get_total_dest_size_change(self):
		"""Return total destination size change

		This represents the total change in the size of the
		rdiff-backup destination directory.

		"""
		addvals = [self.NewFileSize, self.ChangedSourceSize,
				   self.IncrementFileSize]
		subtractvals = [self.DeletedFileSize, self.ChangedMirrorSize]
		for val in addvals + subtractvals:
			if val is None:
				result = None
				break
		else: 
			def addlist(l): return reduce(lambda x,y: x+y, l)
			result = addlist(addvals) - addlist(subtractvals)
		self.TotalDestinationSizeChange = result
		return result

	def get_stats_line(self, index, use_repr = 1):
		"""Return one line abbreviated version of full stats string"""
		file_attrs = map(lambda attr: str(self.get_stat(attr)),
						 self.stat_file_attrs)
		if not index: filename = "."
		else:
			filename = apply(os.path.join, index)
			if use_repr:
				# use repr to quote newlines in relative filename, then
				# take of leading and trailing quote and quote spaces.
				filename = self.space_regex.sub("\\x20", repr(filename)[1:-1])
		return " ".join([filename,] + file_attrs)

	def set_stats_from_line(self, line):
		"""Set statistics from given line"""
		def error(): raise StatsException("Bad line '%s'" % line)
		if line[-1] == "\n": line = line[:-1]
		lineparts = line.split(" ")
		if len(lineparts) < len(stat_file_attrs): error()
		for attr, val_string in zip(stat_file_attrs,
									lineparts[-len(stat_file_attrs):]):
			try: val = long(val_string)
			except ValueError:
				try: val = float(val_string)
				except ValueError: error()
			self.set_stat(attr, val)
		return self

	def get_stats_string(self):
		"""Return extended string printing out statistics"""
		return "%s%s%s" % (self.get_timestats_string(),
						   self.get_filestats_string(),
						   self.get_miscstats_string())

	def get_timestats_string(self):
		"""Return portion of statistics string dealing with time"""
		timelist = []
		if self.StartTime is not None:
			timelist.append("StartTime %.2f (%s)\n" %
						(self.StartTime, Time.timetopretty(self.StartTime)))
		if self.EndTime is not None:
			timelist.append("EndTime %.2f (%s)\n" %
							(self.EndTime, Time.timetopretty(self.EndTime)))
		if self.ElapsedTime or (self.StartTime is not None and
								self.EndTime is not None):
			if self.ElapsedTime is None:
				self.ElapsedTime = self.EndTime - self.StartTime
			timelist.append("ElapsedTime %.2f (%s)\n" %
				   (self.ElapsedTime, Time.inttopretty(self.ElapsedTime)))
		return "".join(timelist)

	def get_filestats_string(self):
		"""Return portion of statistics string about files and bytes"""
		def fileline(stat_file_pair):
			"""Return zero or one line of the string"""
			attr, in_bytes = stat_file_pair
			val = self.get_stat(attr)
			if val is None: return ""
			if in_bytes:
				return "%s %s (%s)\n" % (attr, val,
										 self.get_byte_summary_string(val))
			else: return "%s %s\n" % (attr, val)

		return "".join(map(fileline, self.stat_file_pairs))

	def get_miscstats_string(self):
		"""Return portion of extended stat string about misc attributes"""
		misc_string = ""
		tdsc = self.get_total_dest_size_change()
		if tdsc is not None:
			misc_string += ("TotalDestinationSizeChange %s (%s)\n" %
							(tdsc, self.get_byte_summary_string(tdsc)))
		if self.Errors is not None: misc_string += "Errors %d\n" % self.Errors
		return misc_string

	def get_byte_summary_string(self, byte_count):
		"""Turn byte count into human readable string like "7.23GB" """
		if byte_count < 0:
			sign = "-"
			byte_count = -byte_count
		else: sign = ""

		for abbrev_bytes, abbrev_string in self.byte_abbrev_list:
			if byte_count >= abbrev_bytes:
				# Now get 3 significant figures
				abbrev_count = float(byte_count)/abbrev_bytes
				if abbrev_count >= 100: precision = 0
				elif abbrev_count >= 10: precision = 1
				else: precision = 2
				return "%s%%.%df %s" % (sign, precision, abbrev_string) \
					   % (abbrev_count,)
		byte_count = round(byte_count)
		if byte_count == 1: return sign + "1 byte"
		else: return "%s%d bytes" % (sign, byte_count)

	def get_stats_logstring(self, title):
		"""Like get_stats_string, but add header and footer"""
		header = "--------------[ %s ]--------------" % title
		footer = "-" * len(header)
		return "%s\n%s%s\n" % (header, self.get_stats_string(), footer)

	def set_stats_from_string(self, s):
		"""Initialize attributes from string, return self for convenience"""
		def error(line): raise StatsException("Bad line '%s'" % line)

		for line in s.split("\n"):
			if not line: continue
			line_parts = line.split()
			if len(line_parts) < 2: error(line)
			attr, value_string = line_parts[:2]
			if not attr in self.stat_attrs: error(line)
			try:
				try: val1 = long(value_string)
				except ValueError: val1 = None
				val2 = float(value_string)
				if val1 == val2: self.set_stat(attr, val1) # use integer val
				else: self.set_stat(attr, val2) # use float
			except ValueError: error(line)
		return self

	def write_stats_to_rp(self, rp):
		"""Write statistics string to given rpath"""
		fp = rp.open("wb")
		fp.write(self.get_stats_string())
		assert not fp.close()

	def read_stats_from_rp(self, rp):
		"""Set statistics from rpath, return self for convenience"""
		fp = rp.open("r")
		self.set_stats_from_string(fp.read())
		fp.close()
		return self

	def stats_equal(self, s):
		"""Return true if s has same statistics as self"""
		assert isinstance(s, StatsObj)
		for attr in self.stat_file_attrs:
			if self.get_stat(attr) != s.get_stat(attr): return None
		return 1

	def set_to_average(self, statobj_list):
		"""Set self's attributes to average of those in statobj_list"""
		for attr in self.stat_attrs: self.set_stat(attr, 0)
		for statobj in statobj_list:
			for attr in self.stat_attrs:
				if statobj.get_stat(attr) is None: self.set_stat(attr, None)
				elif self.get_stat(attr) is not None:
					self.set_stat(attr, statobj.get_stat(attr) +
								  self.get_stat(attr))

		# Don't compute average starting/stopping time		
		self.StartTime = None
		self.EndTime = None

		for attr in self.stat_attrs:
			if self.get_stat(attr) is not None:
				self.set_stat(attr,
							  self.get_stat(attr)/float(len(statobj_list)))
		return self

	def get_statsobj_copy(self):
		"""Return new StatsObj object with same stats as self"""
		s = StatObj()
		for attr in self.stat_attrs: s.set_stat(attr, self.get_stat(attr))
		return s


class StatFileObj(StatsObj):
	"""Build on StatsObj, add functions for processing files"""
	def __init__(self, start_time = None):
		"""StatFileObj initializer - zero out file attributes"""
		StatsObj.__init__(self)
		for attr in self.stat_file_attrs: self.set_stat(attr, 0)
		if start_time is None: start_time = Time.curtime
		self.StartTime = start_time
		self.Errors = 0

	def add_source_file(self, src_rorp):
		"""Add stats of source file"""
		self.SourceFiles += 1
		if src_rorp.isreg(): self.SourceFileSize += src_rorp.getsize()

	def add_dest_file(self, dest_rorp):
		"""Add stats of destination size"""
		self.MirrorFiles += 1
		if dest_rorp.isreg(): self.MirrorFileSize += dest_rorp.getsize()

	def add_changed(self, src_rorp, dest_rorp):
		"""Update stats when src_rorp changes to dest_rorp"""
		if src_rorp and src_rorp.lstat() and dest_rorp and dest_rorp.lstat():
			self.ChangedFiles += 1
			if src_rorp.isreg(): self.ChangedSourceSize += src_rorp.getsize()
			if dest_rorp.isreg(): self.ChangedMirrorSize += dest_rorp.getsize()
		elif src_rorp and src_rorp.lstat():
			self.NewFiles += 1
			if src_rorp.isreg(): self.NewFileSize += src_rorp.getsize()
		elif dest_rorp and dest_rorp.lstat():
			self.DeletedFiles += 1
			if dest_rorp.isreg(): self.DeletedFileSize += dest_rorp.getsize()

	def add_increment(self, inc_rorp):
		"""Update stats with increment rorp"""
		self.IncrementFiles += 1
		if inc_rorp.isreg(): self.IncrementFileSize += inc_rorp.getsize()
		
	def add_error(self):
		"""Increment error stat by 1"""
		self.Errors += 1

	def finish(self, end_time = None):
		"""Record end time and set other stats"""
		if end_time is None: end_time = time.time()
		self.EndTime = end_time


_active_statfileobj = None
def init_statfileobj():
	"""Return new stat file object, record as active stat object"""
	global _active_statfileobj
	assert not _active_statfileobj, _active_statfileobj
	_active_statfileobj = StatFileObj()
	return _active_statfileobj

def get_active_statfileobj():
	"""Return active stat file object if it exists"""
	if _active_statfileobj: return _active_statfileobj
	else: return None

def record_error():
	"""Record error on active statfileobj, if there is one"""
	if _active_statfileobj: _active_statfileobj.add_error()

def process_increment(inc_rorp):
	"""Add statistics of increment rp incrp if there is active statfile"""
	if _active_statfileobj: _active_statfileobj.add_increment(inc_rorp)

def write_active_statfileobj():
	"""Write active StatFileObj object to session statistics file"""
	global _active_statfileobj
	assert _active_statfileobj
	rp_base = Globals.rbdir.append("session_statistics")
	session_stats_rp = increment.get_inc(rp_base, 'data', Time.curtime)
	_active_statfileobj.finish()
	_active_statfileobj.write_stats_to_rp(session_stats_rp)
	_active_statfileobj = None

def print_active_stats():
	"""Print statistics of active statobj to stdout and log"""
	global _active_statfileobj
	assert _active_statfileobj
	_active_statfileobj.finish()
	statmsg = _active_statfileobj.get_stats_logstring("Session statistics")
	log.Log.log_to_file(statmsg)
	Globals.client_conn.sys.stdout.write(statmsg)


class FileStats:
	"""Keep track of less detailed stats on file-by-file basis"""
	_fileobj, _rp = None, None
	_line_sep = None
	def init(cls):
		"""Open file stats object and prepare to write"""
		assert not (cls._fileobj or cls._rp), (cls._fileobj, cls._rp)
		rpbase = Globals.rbdir.append("file_statistics")
		suffix = Globals.compression and 'data.gz' or 'data'
		cls._rp = increment.get_inc(rpbase, suffix, Time.curtime)
		assert not cls._rp.lstat()
		cls._fileobj = cls._rp.open("wb", compress = Globals.compression)

		cls._line_sep = Globals.null_separator and '\0' or '\n'
		cls.write_docstring()
		cls.line_buffer = []

	def write_docstring(cls):
		"""Write the first line (a documentation string) into file"""
		cls._fileobj.write("# Format of each line in file statistics file:")
		cls._fileobj.write(cls._line_sep)
		cls._fileobj.write("# Filename Changed SourceSize MirrorSize "
						   "IncrementSize" + cls._line_sep)

	def update(cls, source_rorp, dest_rorp, changed, inc):
		"""Update file stats with given information"""
		if source_rorp: filename = source_rorp.get_indexpath()
		else: filename = dest_rorp.get_indexpath()
		filename = metadata.quote_path(filename)

		size_list = map(cls.get_size, [source_rorp, dest_rorp, inc])
		line = " ".join([filename, str(changed)] + size_list)
		cls.line_buffer.append(line)
		if len(cls.line_buffer) >= 100: cls.write_buffer()

	def get_size(cls, rorp):
		"""Return the size of rorp as string, or "NA" if not a regular file"""
		if not rorp: return "NA"
		if rorp.isreg(): return str(rorp.getsize())
		else: return "0"

	def write_buffer(cls):
		"""Write buffer to file because buffer is full

		The buffer part is necessary because the GzipFile.write()
		method seems fairly slow.

		"""
		assert cls.line_buffer and cls._fileobj
		cls.line_buffer.append('') # have join add _line_sep to end also
		cls._fileobj.write(cls._line_sep.join(cls.line_buffer))
		cls.line_buffer = []

	def close(cls):
		"""Close file stats file"""
		assert cls._fileobj, cls._fileobj
		if cls.line_buffer: cls.write_buffer()
		assert not cls._fileobj.close()
		cls._fileobj = cls._rp = None

static.MakeClass(FileStats)
