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
					   'IncrementFileSize')
	stat_time_attrs = ('StartTime', 'EndTime')
	stat_attrs = stat_time_attrs + stat_file_attrs

	# Set all stats to None, indicating info not available
	for attr in stat_attrs: locals()[attr] = None

	def get_stat(self, attribute):
		"""Get a statistic"""
		try: return self.__dict__[attribute]
		except KeyError:
			# this may be a hack, but seems no good way to get attrs in python
			return eval("self.%s" % attribute)

	def set_stat(self, attr, value):
		"""Set attribute to given value"""
		self.__dict__[attr] = value

	def get_stats_string(self):
		"""Return string printing out statistics"""
		slist = ["%s %s" % (attr, self.get_stat(attr))
				 for attr in self.stat_attrs
				 if self.get_stat(attr) is not None]
		return "\n".join(slist)

	def init_stats_from_string(self, s):
		"""Initialize attributes from string, return self for convenience"""
		def error(line): raise StatsException("Bad line '%s'" % line)

		for line in s.split("\n"):
			if not line: continue
			line_parts = line.split()
			if len(line_parts) < 2: error(line)
			attr, value_string = line_parts[:2]
			if not attr in self.stat_attrs: error(line)
			try: self.set_stat(attr, long(value_string))
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
		self.init_stats_from_string(fp.read())
		fp.close()
		return self

	def stats_equal(self, s):
		"""Return true if s has same statistics as self"""
		assert isinstance(s, StatsObj)
		for attr in self.stat_file_attrs:
			if self.get_stat(attr) != s.get_stat(attr): return None
		return 1


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
					self.IncrementFileSize += inc_rp and inc_rp.getsize() or 0
			else: # new file was created
				self.NewFiles += 1
				self.NewFileSize += mirror_dsrp.getsize()
				self.IncrementFileSize += inc_rp and inc_rp.getsize() or 0
		else:
			if self.mirror_base_exists: # file was deleted from mirror
				self.MirrorFiles += 1
				self.MirrorFileSize += self.mirror_base_size
				self.DeletedFiles += 1
				self.DeletedFileSize += self.mirror_base_size
				self.IncrementFileSize += inc_rp and inc_rp.getsize() or 0
			else: assert None # One of before and after should exist

	def add_file_stats(self, subinstance):
		"""Add all file statistics from subinstance to current totals"""
		for attr in self.stat_file_attrs:
			self.set_stat(attr,
						  self.get_stat(attr) + subinstance.get_stat(attr))
