from __future__ import generators
execfile("rorpiter.py")

#######################################################################
#
# destructive-stepping - Deal with side effects from traversing trees
#

class DSRPath(RPath):
	"""Destructive Stepping RPath

	Sometimes when we traverse the directory tree, even when we just
	want to read files, we have to change things, like the permissions
	of a file or directory in order to read it, or the file's access
	times.  This class is like an RPath, but the permission and time
	modifications are delayed, so that they can be done at the very
	end when they won't be disturbed later.

	"""
	def __init__(self, *args):
		self.perms_delayed = self.times_delayed = None
		RPath.__init__(self, *args)

	def __getstate__(self):
		"""Return picklable state.  See RPath __getstate__."""
		assert self.conn is Globals.local_connection # Can't pickle a conn
		pickle_dict = {}
		for attrib in ['index', 'data', 'perms_delayed', 'times_delayed',
					   'newperms', 'newtimes', 'path', 'base']:
			if self.__dict__.has_key(attrib):
				pickle_dict[attrib] = self.__dict__[attrib]
		return pickle_dict

	def __setstate__(self, pickle_dict):
		"""Set state from object produced by getstate"""
		self.conn = Globals.local_connection
		for attrib in pickle_dict.keys():
			self.__dict__[attrib] = pickle_dict[attrib]

	def delay_perm_writes(self):
		"""Signal that permission writing should be delayed until the end"""
		self.perms_delayed = 1
		self.newperms = None

	def delay_time_changes(self):
		"""Signal that time changes should also be delayed until the end"""
		self.times_delayed = 1
		self.newtimes = None

	def chmod(self, permissions):
		"""Change permissions, delaying if self.perms_delayed is set"""
		if self.perms_delayed:
			self.newperms = 1
			self.data['perms'] = permissions
		else: RPath.chmod(self, permissions)

	def chmod_bypass(self, permissions):
		"""Change permissions without updating the data dictionary"""
		self.conn.os.chmod(self.path, permissions)
		self.perms_delayed = self.newperms = 1

	def remember_times(self):
		"""Mark times as changed so they can be restored later"""
		self.times_delayed = self.newtimes = 1

	def settime(self, accesstime, modtime):
		"""Change times, delaying if self.times_delayed is set"""
		if self.times_delayed:
			self.newtimes = 1
			self.data['atime'] = accesstime
			self.data['mtime'] = modtime
		else: RPath.settime(self, accesstime, modtime)

	def settime_bypass(self, accesstime, modtime):
		"""Change times without updating data dictionary"""
		self.conn.os.utime(self.path, (accesstime, modtime))

	def setmtime(self, modtime):
		"""Change mtime, delaying if self.times_delayed is set"""
		if self.times_delayed:
			self.newtimes = 1
			self.data['mtime'] = modtime
		else: RPath.setmtime(self, modtime)

	def setmtime_bypass(self, modtime):
		"""Change mtime without updating data dictionary"""
		self.conn.os.utime(self.path, (time.time(), modtime))

	def restoretimes(self):
		"""Write times in self.data back to file"""
		RPath.settime(self, self.data['atime'], self.data['mtime'])

	def restoreperms(self):
		"""Write permissions in self.data back to file"""
		RPath.chmod(self, self.data['perms'])

	def write_changes(self):
		"""Write saved up permission/time changes"""
		if not self.lstat(): return # File has been deleted in meantime

		if self.perms_delayed and self.newperms:
			self.conn.os.chmod(self.path, self.getperms())
		if self.times_delayed:
			if self.data.has_key('atime'):
				self.settime_bypass(self.getatime(), self.getmtime())
			elif self.newtimes and self.data.has_key('mtime'):
				self.setmtime_bypass(self.getmtime())


class DestructiveStepping:
	"""Destructive stepping"""
	def initialize(dsrpath, source):
		"""Change permissions of dsrpath, possibly delay writes

		Abort if we need to access something and can't.  If the file
		is on the source partition, just log warning and return true.
		Return false if everything good to go.

		"""
		if not source or Globals.change_source_perms:
			dsrpath.delay_perm_writes()

		def warn(err):
			Log("Received error '%s' when dealing with file %s, skipping..."
				% (err, dsrpath.path), 1)

		def abort():
			Log.FatalError("Missing access to file %s - aborting." %
						   dsrpath.path)

		def try_chmod(perms):
			"""Try to change the perms.  If fail, return error."""
			try: dsrpath.chmod_bypass(perms)
			except os.error, err: return err
			return None

		if dsrpath.isreg() and not dsrpath.readable():
			if source:
				if Globals.change_source_perms and dsrpath.isowner():
					err = try_chmod(0400)
					if err:
						warn(err)
						return 1
				else:
					warn("No read permissions")
					return 1
			elif not Globals.change_mirror_perms or try_chmod(0600): abort()
		elif dsrpath.isdir():
			if source and (not dsrpath.readable() or not dsrpath.executable()):
				if Globals.change_source_perms and dsrpath.isowner():
					err = try_chmod(0500)
					if err:
						warn(err)
						return 1
				else:
					warn("No read or exec permissions")
					return 1
			elif not source and not dsrpath.hasfullperms():
				if Globals.change_mirror_perms: try_chmod(0700)

		# Permissions above; now try to preserve access times if necessary
		if (source and (Globals.preserve_atime or
						Globals.change_source_perms) or
			not source):
			# These are the circumstances under which we will have to
			# touch up a file's times after we are done with it
			dsrpath.remember_times()
		return None

	def Finalizer(initial_state = None):
		"""Return a finalizer that can work on an iterator of dsrpaths

		The reason we have to use an IterTreeReducer is that some files
		should be updated immediately, but for directories we sometimes
		need to update all the files in the directory before finally
		coming back to it.

		"""
		return IterTreeReducer(lambda x: None, lambda x,y: None, None,
							   lambda dsrpath, x, y: dsrpath.write_changes(),
							   initial_state)

MakeStatic(DestructiveStepping)
