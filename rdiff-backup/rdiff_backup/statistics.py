execfile("filename_mapping.py")

#######################################################################
#
# statistics - Generate and process aggregated backup information
#

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
	stat_time_attrs = ('StartTime', 'EndTime', 'ElapsedTime')
	stat_attrs = ('Filename',) + stat_time_attrs + stat_file_attrs

	# Below, the second value in each pair is true iff the value
	# indicates a number of bytes
	stat_file_pairs = (('SourceFiles', None), ('SourceFileSize', 1),
					   ('MirrorFiles', None), ('MirrorFileSize', 1),
					   ('NewFiles', None), ('NewFileSize', 1),
					   ('DeletedFiles', None), ('DeletedFileSize', 1),
					   ('ChangedFiles', None),
					   ('ChangedSourceSize', 1), ('ChangedMirrorSize', 1),
					   ('IncrementFiles', None), ('IncrementFileSize', 1))

	# Set all stats to None, indicating info not available
	for attr in stat_attrs: locals()[attr] = None

	# This is used in get_byte_summary_string below
	byte_abbrev_list = ((1024*1024*1024*1024, "TB"),
						(1024*1024*1024, "GB"),
						(1024*1024, "MB"),
						(1024, "KB"))

	def get_stat(self, attribute):
		"""Get a statistic"""
		try: return self.__dict__[attribute]
		except KeyError:
			# this may be a hack, but seems no good way to get attrs in python
			return eval("self.%s" % attribute)

	def set_stat(self, attr, value):
		"""Set attribute to given value"""
		self.__dict__[attr] = value

	def get_stats_line(self, index):
		"""Return one line abbreviated version of full stats string"""
		file_attrs = map(lambda attr: str(self.get_stat(attr)),
						 self.stat_file_attrs)
		if not index: filename = "."
		else:
			# use repr to quote newlines in relative filename, then
			# take of leading and trailing quote.
			filename = repr(apply(os.path.join, index))[1:-1]
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
	# zero out file statistics
	for attr in StatsObj.stat_file_attrs: locals()[attr] = 0

	def start_stats(self, mirror_dsrp):
		"""Record status of mirror dsrp

		This is called before the mirror is processed so we remember
		the old state.

		"""
		if mirror_dsrp.lstat():
			self.mirror_base_exists = 1
			self.mirror_base_size = mirror_dsrp.getsize()
		else: self.mirror_base_exists = None

	def end_stats(self, diff_rorp, mirror_dsrp, inc_rp = None):
		"""Set various statistics after mirror processed"""
		if mirror_dsrp.lstat():
			self.SourceFiles += 1
			self.SourceFileSize += mirror_dsrp.getsize()
			if self.mirror_base_exists:
				self.MirrorFiles += 1
				self.MirrorFileSize += self.mirror_base_size
				if diff_rorp: # otherwise no change
					self.ChangedFiles += 1
					self.ChangedSourceSize += mirror_dsrp.getsize()
					self.ChangedMirrorSize += self.mirror_base_size
					if inc_rp:
						self.IncrementFiles += 1
						self.IncrementFileSize += inc_rp.getsize()
			else: # new file was created
				self.NewFiles += 1
				self.NewFileSize += mirror_dsrp.getsize()
				if inc_rp:
					self.IncrementFiles += 1
					self.IncrementFileSize += inc_rp.getsize()
		else:
			if self.mirror_base_exists: # file was deleted from mirror
				self.MirrorFiles += 1
				self.MirrorFileSize += self.mirror_base_size
				self.DeletedFiles += 1
				self.DeletedFileSize += self.mirror_base_size
				if inc_rp:
					self.IncrementFiles += 1
					self.IncrementFileSize += inc_rp.getsize()

	def add_file_stats(self, subinstance):
		"""Add all file statistics from subinstance to current totals"""
		for attr in self.stat_file_attrs:
			self.set_stat(attr,
						  self.get_stat(attr) + subinstance.get_stat(attr))


class Stats:
	"""Misc statistics methods, pertaining to dir and session stat files"""
	# This is the RPath of the directory statistics file, and the
	# associated open file.  It will hold a line of statistics for
	# each directory that is backed up.
	_dir_stats_rp = None
	_dir_stats_fp = None

	# This goes at the beginning of the directory statistics file and
	# explains the format.
	_dir_stats_header = """# rdiff-backup directory statistics file
#
# Each line is in the following format:
# RelativeDirName %s
""" % " ".join(StatsObj.stat_file_attrs)

	def open_dir_stats_file(cls):
		"""Open directory statistics file, write header"""
		assert not cls._dir_stats_fp, "Directory file already open"

		if Globals.compression: suffix = "data.gz"
		else: suffix = "data"
		cls._dir_stats_rp = Inc.get_inc(Globals.rbdir.append(
			"directory_statistics"), Time.curtime, suffix)

		if cls._dir_stats_rp.lstat():
			Log("Warning, statistics file %s already exists, appending", 2)
			cls._dir_stats_fp = cls._dir_stats_rp.open("ab",
													   Globals.compression)
		else: cls._dir_stats_fp = \
			  cls._dir_stats_rp.open("wb", Globals.compression)
		cls._dir_stats_fp.write(cls._dir_stats_header)

	def write_dir_stats_line(cls, statobj, index):
		"""Write info from statobj about rpath to statistics file"""
		cls._dir_stats_fp.write(statobj.get_stats_line(index) +"\n")

	def close_dir_stats_file(cls):
		"""Close directory statistics file if its open"""
		if cls._dir_stats_fp:
			cls._dir_stats_fp.close()
			cls._dir_stats_fp = None

	def write_session_statistics(cls, statobj):
		"""Write session statistics into file, log"""
		stat_inc = Inc.get_inc(Globals.rbdir.append("session_statistics"),
							   Time.curtime, "data")
		statobj.StartTime = Time.curtime
		statobj.EndTime = time.time()

		# include hardlink data and dir stats in size of increments
		if Globals.preserve_hardlinks and Hardlink.final_inc:
			# include hardlink data in size of increments
			statobj.IncrementFiles += 1
			statobj.IncrementFileSize += Hardlink.final_inc.getsize()
		if cls._dir_stats_rp and cls._dir_stats_rp.lstat():
			statobj.IncrementFiles += 1
			statobj.IncrementFileSize += cls._dir_stats_rp.getsize()

		statobj.write_stats_to_rp(stat_inc)
		if Globals.print_statistics:
			message = statobj.get_stats_logstring("Session statistics")
			Log.log_to_file(message)
			Globals.client_conn.sys.stdout.write(message)

MakeClass(Stats)

