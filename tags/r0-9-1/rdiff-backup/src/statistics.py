# Copyright 2002 Ben Escoto
#
# This file is part of rdiff-backup.
#
# rdiff-backup is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, Inc., 675 Mass Ave, Cambridge MA
# 02139, USA; either version 2 of the License, or (at your option) any
# later version; incorporated herein by reference.

"""Generate and process aggregated backup information"""

from lazy import *


class StatsException(Exception): pass

class StatsObj:
	"""Contains various statistics, provide string conversion functions"""

	stat_file_attrs = ('SourceFiles', 'SourceFileSize',
					   'MirrorFiles', 'MirrorFileSize',
					   'NewFiles', 'NewFileSize',
					   'DeletedFiles', 'DeletedFileSize',
					   'ChangedFiles',
					   'ChangedSourceSize', 'ChangedMirrorSize',
					   'IncrementFiles', 'IncrementFileSize')
	stat_misc_attrs = ('Errors',)
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

	def get_stats_line(self, index, use_repr = 1):
		"""Return one line abbreviated version of full stats string"""
		file_attrs = map(lambda attr: str(self.get_stat(attr)),
						 self.stat_file_attrs)
		if not index: filename = "."
		else:
			filename = apply(os.path.join, index)
			if use_repr:
				# use repr to quote newlines in relative filename, then
				# take of leading and trailing quote.
				filename = repr(filename)[1:-1]
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
		return self.get_timestats_string() + self.get_filestats_string()

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
		if self.Errors is not None:
			timelist.append("Errors %d\n" % self.Errors)
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

	def get_byte_summary_string(self, byte_count):
		"""Turn byte count into human readable string like "7.23GB" """
		for abbrev_bytes, abbrev_string in self.byte_abbrev_list:
			if byte_count >= abbrev_bytes:
				# Now get 3 significant figures
				abbrev_count = float(byte_count)/abbrev_bytes
				if abbrev_count >= 100: precision = 0
				elif abbrev_count >= 10: precision = 1
				else: precision = 2
				return "%%.%df %s" % (precision, abbrev_string) \
					   % (abbrev_count,)
		byte_count = round(byte_count)
		if byte_count == 1: return "1 byte"
		else: return "%d bytes" % (byte_count,)

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
		tf = TempFileManager.new(rp)
		def init_thunk():
			fp = tf.open("w")
			fp.write(self.get_stats_string())
			fp.close()
		Robust.make_tf_robustaction(init_thunk, (tf,), (rp,)).execute()

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


class StatsITR(IterTreeReducer, StatsObj):
	"""Keep track of per directory statistics

	This is subclassed by the mirroring and incrementing ITRs.

	"""
	def __init__(self, *args):
		"""StatsITR initializer - zero out statistics"""
		attr_dict = self.__dict__
		for attr in StatsObj.stat_file_attrs: attr_dict[attr] = 0
		self.ElapsedTime = self.Filename = None
		IterTreeReducer.__init__(self, *args)

	def start_stats(self, mirror_dsrp):
		"""Record status of mirror dsrp

		This is called before the mirror is processed so we remember
		the old state.

		"""
		if mirror_dsrp.lstat():
			self.mirror_base_exists = 1
			self.mirror_base_size = self.stats_getsize(mirror_dsrp)
		else: self.mirror_base_exists = None

	def stats_getsize(self, rp):
		"""Return size of rp, with error checking"""
		try: return rp.getsize()
		except KeyError: return 0

	def end_stats(self, diff_rorp, mirror_dsrp, inc_rp = None):
		"""Set various statistics after mirror processed"""
		if mirror_dsrp.lstat():
			source_size = self.stats_getsize(mirror_dsrp)
			self.SourceFiles += 1
			self.SourceFileSize += source_size
			if self.mirror_base_exists:
				self.MirrorFiles += 1
				self.MirrorFileSize += self.mirror_base_size
				if diff_rorp: # otherwise no change
					self.ChangedFiles += 1
					self.ChangedSourceSize += source_size
					self.ChangedMirrorSize += self.mirror_base_size
					self.stats_incr_incfiles(inc_rp)
			else: # new file was created
				self.NewFiles += 1
				self.NewFileSize += source_size
				self.stats_incr_incfiles(inc_rp)
		else:
			if self.mirror_base_exists: # file was deleted from mirror
				self.MirrorFiles += 1
				self.MirrorFileSize += self.mirror_base_size
				self.DeletedFiles += 1
				self.DeletedFileSize += self.mirror_base_size
				self.stats_incr_incfiles(inc_rp)

	def stats_incr_incfiles(self, inc_rp):
		"""Increment IncrementFile statistics"""
		if inc_rp:
			self.IncrementFiles += 1
			self.IncrementFileSize += self.stats_getsize(inc_rp)

	def add_file_stats(self, subinstance):
		"""Add all file statistics from subinstance to current totals"""
		for attr in self.stat_file_attrs:
			self.__dict__[attr] += subinstance.__dict__[attr]


from log import *
from increment import *
from robust import *
import Globals
