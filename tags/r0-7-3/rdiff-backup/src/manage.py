execfile("restore.py")

#######################################################################
#
# manage - list, delete, and otherwise manage increments
#

class ManageException(Exception): pass

class Manage:
	def get_incobjs(datadir):
		"""Return Increments objects given the rdiff-backup data directory"""
		return map(IncObj, Manage.find_incrps_with_base(datadir, "increments"))

	def find_incrps_with_base(dir_rp, basename):
		"""Return list of incfiles with given basename in dir_rp"""
		rps = map(dir_rp.append, dir_rp.listdir())
		incrps = filter(RPath.isincfile, rps)
		result = filter(lambda rp: rp.getincbase_str() == basename, incrps)
		Log("find_incrps_with_base: found %d incs" % len(result), 6)
		return result
	
	def describe_root_incs(datadir):
		"""Return a string describing all the the root increments"""
		result = []
		currentrps = Manage.find_incrps_with_base(datadir, "current_mirror")
		if not currentrps:
			Log("Warning: no current mirror marker found", 1)
		elif len(currentrps) > 1:
			Log("Warning: multiple mirror markers found", 1)
		for rp in currentrps:
			result.append("Found mirror marker %s" % rp.path)
			result.append("Indicating latest mirror taken at %s" %
						  Time.stringtopretty(rp.getinctime()))
		result.append("---------------------------------------------"
					  "-------------")

		# Sort so they are in reverse order by time
		time_w_incobjs = map(lambda io: (-io.time, io),
							 Manage.get_incobjs(datadir))
		time_w_incobjs.sort()
		incobjs = map(lambda x: x[1], time_w_incobjs)
		result.append("Found %d increments:" % len(incobjs))
		result.append("\n------------------------------------------\n".join(
			map(IncObj.full_description, incobjs)))
		return "\n".join(result)

	def delete_earlier_than(baserp, time):
		"""Deleting increments older than time in directory baserp

		time is in seconds.  It will then delete any empty directories
		in the tree.  To process the entire backup area, the
		rdiff-backup-data directory should be the root of the tree.

		"""
		def yield_files(rp):
			yield rp
			if rp.isdir():
				for filename in rp.listdir():
					for sub_rp in yield_files(rp.append(filename)):
						yield sub_rp

		for rp in yield_files(baserp):
			if ((rp.isincfile() and
				 Time.stringtotime(rp.getinctime()) < time) or
				(rp.isdir() and not rp.listdir())):
				Log("Deleting increment file %s" % rp.path, 5)
				rp.delete()

MakeStatic(Manage)


class IncObj:
	"""Increment object - represent a completed increment"""
	def __init__(self, incrp):
		"""IncObj initializer

		incrp is an RPath of a path like increments.TIMESTR.dir
		standing for the root of the increment.

		"""
		if not incrp.isincfile():
			raise ManageException("%s is not an inc file" % incrp.path)
		self.incrp = incrp
		self.time = Time.stringtotime(incrp.getinctime())

	def getbaserp(self):
		"""Return rp of the incrp without extensions"""
		return self.incrp.getincbase()

	def pretty_time(self):
		"""Return a formatted version of inc's time"""
		return Time.timetopretty(self.time)

	def full_description(self):
		"""Return string describing increment"""
		s = ["Increment file %s" % self.incrp.path,
			 "Date: %s" % self.pretty_time()]
		return "\n".join(s)
