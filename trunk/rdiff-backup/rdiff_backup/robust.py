import tempfile
execfile("hardlink.py")

#######################################################################
#
# robust - code which prevents mirror from being corrupted, error-recovery
#
# Ideally no matter an instance of rdiff-backup gets aborted, no
# information should get lost.  The target directory should be left in
# a coherent state, and later instances of rdiff-backup should clean
# things up so there is no sign that anything ever got aborted or
# failed.
#
# Thus, files should be updated in an atomic way as possible.  Each
# file should be updated (and the corresponding diff files written) or
# not, and it should be clear which happened.  In general, I don't
# think this is possible, since the creation of the diff files and the
# changing of updated files cannot be guarateed to happen together.
# It is possible, I think, to record various information to files
# which would allow a later process to figure out what the last
# operation was, but this would add several file operations to the
# processing of each file, and I don't think, would be a good
# tradeoff.
#
# The compromise reached here is that diff files should be created
# just before the mirror files are updated, and each file update
# should be done with a rename operation on a file in the same
# directory.  Furthermore, every once in a while, rdiff-backup will
# record which file it just finished processing.  If any fatal errors
# are caught, it will also record the last processed file.  Future
# instances may not know exactly when the previous instance was
# aborted, but they will be able to narrow down the possibilities.

class RobustAction:
	"""Represents a file operation to be accomplished later"""
	def __init__(self, init_thunk, final_thunk, error_thunk):
		"""RobustAction initializer

		All the thunks are functions whose return value will be
		ignored.  init_thunk should not make any irreversible changes
		but prepare for the writing of the important data. final_thunk
		should be as short as possible and do the real work.
		error_thunk is run if there is an error in init_thunk or
		final_thunk.  Errors in init_thunk should be corrected by
		error_thunk as if nothing had been run in the first place.
		The functions take no arguments except for error_thunk, which
		receives the exception as its only argument.

		"""
		self.init_thunk = init_thunk
		self.final_thunk = final_thunk
		self.error_thunk = error_thunk

	def execute(self):
		"""Actually run the operation"""
		try:
			self.init_thunk()
			self.final_thunk()
		except Exception, exp: # Catch all errors
			Log.exception()
			self.error_thunk(exp)
			raise exp


class Robust:
	"""Contains various file operations made safer using tempfiles"""
	null_action = RobustAction(lambda: None, lambda: None, lambda e: None)
	def chain(robust_action_list):
		"""Return chain tying together a number of robust actions

		The whole chain will be aborted if some error occurs in
		initialization stage of any of the component actions.

		"""
		ras_with_completed_inits = []
		def init():
			for ra in robust_action_list:
				ras_with_completed_inits.append(ra)
				ra.init_thunk()
		def final():
			for ra in robust_action_list: ra.final_thunk()
		def error(exp):
			for ra in ras_with_completed_inits: ra.error_thunk(exp)
		return RobustAction(init, final, error)

	def chain_nested(robust_action_list):
		"""Like chain but final actions performed in reverse order"""
		ras_with_completed_inits = []
		def init():
			for ra in robust_action_list:
				ras_with_completed_inits.append(ra)
				ra.init_thunk()
		def final():
			ralist_copy = robust_action_list[:]
			ralist_copy.reverse()
			for ra in ralist_copy: ra.final_thunk()
		def error(exp):
			for ra in ras_with_completed_inits: ra.error_thunk(exp)
		return RobustAction(init, final, error)

	def make_tf_robustaction(init_thunk, tempfiles, final_renames = None):
		"""Shortcut RobustAction creator when only tempfiles involved

		Often the robust action will just consist of some initial
		stage, renaming tempfiles in the final stage, and deleting
		them if there is an error.  This function makes it easier to
		create RobustActions of that type.

		"""
		assert type(tempfiles) is types.TupleType, tempfiles
		if final_renames is None: final = lambda: None
		else:
			assert len(tempfiles) == len(final_renames)
			def final(): # rename tempfiles to final positions
				for i in range(len(tempfiles)):
					final_name = final_renames[i]
					if final_name:
						if final_name.isdir(): # Cannot rename over directory
							final_name.delete()
						tempfiles[i].rename(final_name)
		def error(exp):
			for tf in tempfiles: tf.delete()
		return RobustAction(init_thunk, final, error)

	def copy_action(rorpin, rpout):
		"""Return robust action copying rorpin to rpout

		The source can be a rorp or an rpath.  Does not recurse.  If
		directories copied, then just exit (output directory not
		overwritten).
		
		"""
		tfl = [None] # Need mutable object that init and final can access
		def init(): 
			if not (rorpin.isdir() and rpout.isdir()): # already a dir
				tfl[0] = TempFileManager.new(rpout)
				if rorpin.isreg(): tfl[0].write_from_fileobj(rorpin.open("rb"))
				else: RPath.copy(rorpin, tf)
		def final():
			if tfl[0] and tfl[0].lstat():
				if rpout.isdir(): rpout.delete()
				tfl[0].rename(rpout)
		return RobustAction(init, final, lambda e: tfl[0] and tfl[0].delete())

	def copy_with_attribs_action(rorpin, rpout):
		"""Like copy_action but also copy attributes"""
		tfl = [None] # Need mutable object that init and final can access
		def init(): 
			if not (rorpin.isdir() and rpout.isdir()): # already a dir
				tfl[0] = TempFileManager.new(rpout)
				if rorpin.isreg(): tfl[0].write_from_fileobj(rorpin.open("rb"))
				else: RPath.copy(rorpin, tfl[0])
				if tfl[0].lstat(): # Some files, like sockets, won't be created
					RPathStatic.copy_attribs(rorpin, tfl[0])
		def final():
			if rorpin.isdir() and rpout.isdir():
				RPath.copy_attribs(rorpin, rpout)
			elif tfl[0] and tfl[0].lstat():
				if rpout.isdir(): rpout.delete()
				tfl[0].rename(rpout)
		return RobustAction(init, final, lambda e: tfl[0] and tfl[0].delete())

	def copy_attribs_action(rorpin, rpout):
		"""Return action which just copies attributes

		Copying attributes is already pretty atomic, so just run
		normal sequence.

		"""
		def final(): RPath.copy_attribs(rorpin, rpout)
		return RobustAction(lambda: None, final, lambda e: None)

	def symlink_action(rpath, linktext):
		"""Return symlink action by moving one file over another"""
		tf = TempFileManager.new(rpath)
		def init(): tf.symlink(linktext)
		return Robust.make_tf_robustaction(init, (tf,), (rpath,))

	def destructive_write_action(rp, s):
		"""Return action writing string s to rpath rp in robust way

		This will overwrite any data currently in rp.

		"""
		tf = TempFileManager.new(rp)
		def init():
			fp = tf.open("wb")
			fp.write(s)
			assert not fp.close()
			tf.setdata()
		return Robust.make_tf_robustaction(init, (tf,), (rp,))

MakeStatic(Robust)


class TempFileManager:
	"""Manage temp files"""

	# This is a connection-specific list of temp files, to be cleaned
	# up before rdiff-backup exits.
	_tempfiles = []

	# To make collisions less likely, this gets put in the file name
	# and incremented whenever a new file is requested.
	_tfindex = 0

	def new(cls, rp_base, same_dir = 1):
		"""Return new tempfile that isn't in use.

		If same_dir, tempfile will be in same directory as rp_base.
		Otherwise, use tempfile module to get filename.

		"""
		conn = rp_base.conn
		if conn is not Globals.local_connection:
			return conn.TempFileManager.new(rp_base, same_dir)

		def find_unused(conn, dir):
			"""Find an unused tempfile with connection conn in directory dir"""
			while 1:
				if cls._tfindex > 100000000:
					Log("Resetting index", 2)
					cls._tfindex = 0
				tf = TempFile(conn, os.path.join(dir,
								       "rdiff-backup.tmp.%d" % cls._tfindex))
				cls._tfindex = cls._tfindex+1
				if not tf.lstat(): return tf

		if same_dir: tf = find_unused(conn, rp_base.dirsplit()[0])
		else: tf = TempFile(conn, tempfile.mktemp())
		cls._tempfiles.append(tf)
		return tf

	def remove_listing(cls, tempfile):
		"""Remove listing of tempfile"""
		if Globals.local_connection is not tempfile.conn:
			tempfile.conn.TempFileManager.remove_listing(tempfile)
		elif tempfile in cls._tempfiles: cls._tempfiles.remove(tempfile)

	def delete_all(cls):
		"""Delete all remaining tempfiles"""
		for tf in cls._tempfiles[:]: tf.delete()

MakeClass(TempFileManager)


class TempFile(RPath):
	"""Like an RPath, but keep track of which ones are still here"""
	def rename(self, rp_dest):
		"""Rename temp file to permanent location, possibly overwriting"""
		if self.isdir() and not rp_dest.isdir():
			# Cannot move a directory directly over another file
			rp_dest.delete()
			if (isinstance(rp_dest, DSRPath) and rp_dest.perms_delayed
				and not self.hasfullperms()):
				# If we are moving to a delayed perm directory, delay
				# permission change on destination.
				rp_dest.chmod(self.getperms())
				self.chmod(0700)
		RPathStatic.rename(self, rp_dest)

		# Sometimes this just seems to fail silently, as in one
		# hardlinked twin is moved over the other.  So check to make
		# sure below.
		self.setdata()
		if self.lstat():
			rp_dest.delete()
			RPathStatic.rename(self, rp_dest)
			self.setdata()
			if self.lstat(): raise OSError("Cannot rename tmp file correctly")
		TempFileManager.remove_listing(self)

	def delete(self):
		RPath.delete(self)
		TempFileManager.remove_listing(self)


class SaveState:
	"""Save state in the middle of backups for resuming later"""
	_last_file_sym = None # RPath of sym pointing to last file processed
	_last_file_definitive_rp = None # Touch this if last file is really last
	_last_checkpoint_time = 0 # time in seconds of last checkpoint
	_checkpoint_rp = None # RPath of checkpoint data pickle
	
	def init_filenames(cls, incrementing):
		"""Set rpaths of markers.  Assume rbdir already set.

		If incrementing, then indicate increment operation, otherwise
		indicate mirror.

		"""
		if not Globals.isbackup_writer:
			return Globals.backup_writer.SaveState.init_filenames(incrementing)

		assert Globals.local_connection is Globals.rbdir.conn, \
			   (Globals.rbdir.conn, Globals.backup_writer)

		if incrementing: cls._last_file_sym = Globals.rbdir.append(
			"last-file-incremented.%s.snapshot" % Time.curtimestr)
		else: cls._last_file_sym = Globals.rbdir.append(
			"last-file-mirrored.%s.snapshot" % Time.curtimestr)
		cls._checkpoint_rp = Globals.rbdir.append(
			"checkpoint-data.%s.snapshot" % Time.curtimestr)
		cls._last_file_definitive_rp = Globals.rbdir.append(
			"last-file-definitive.%s.snapshot" % Time.curtimestr)

	def touch_last_file(cls):
		"""Touch last file marker, indicating backup has begun"""
		cls._last_file_sym.touch()

	def touch_last_file_definitive(cls):
		"""Create last-file-definitive marker

		When a backup gets aborted, there may be time to indicate the
		last file successfully processed, and this should be touched.
		Sometimes when the abort is hard, there may be a last file
		indicated, but further files since then have been processed,
		in which case this shouldn't be touched.

		"""
		cls._last_file_definitive_rp.touch()

	def record_last_file_action(cls, last_file_rorp):
		"""Action recording last file to be processed as symlink in rbdir

		last_file_rorp is None means that no file is known to have
		been processed.

		"""
		if last_file_rorp:
			symtext = apply(os.path.join,
							('increments',) + last_file_rorp.index)
			return Robust.symlink_action(cls._last_file_sym, symtext)
		else: return RobustAction(lambda: None, cls.touch_last_file,
								  lambda exp: None)

	def checkpoint_inc_backup(cls, ITR, finalizer, last_file_rorp,
							  override = None):
		"""Save states of tree reducer and finalizer during inc backup

		If override is true, checkpoint even if one isn't due.

		"""
		if not override and not cls.checkpoint_needed(): return
		assert cls._checkpoint_rp, "_checkpoint_rp not set yet"

		cls._last_checkpoint_time = time.time()
		Log("Writing checkpoint time %s" % cls._last_checkpoint_time, 7)
		state_string = cPickle.dumps((ITR.getstate(), finalizer.getstate()))
		Robust.chain([Robust.destructive_write_action(cls._checkpoint_rp,
													  state_string),
					  cls.record_last_file_action(last_file_rorp)]).execute()

	def checkpoint_mirror(cls, finalizer, last_file_rorp, override = None):
		"""For a mirror, only finalizer and last_file should be saved"""
		if not override and not cls.checkpoint_needed(): return
		if not cls._checkpoint_rp:
			Log("Warning, _checkpoint_rp not set yet", 2)
			return

		cls._last_checkpoint_time = time.time()
		Log("Writing checkpoint time %s" % cls._last_checkpoint_time, 7)
		state_string = cPickle.dumps(finalizer.getstate())
		Robust.chain([Robust.destructive_write_action(cls._checkpoint_rp,
													  state_string),
					  cls.record_last_file_action(last_file_rorp)]).execute()

	def checkpoint_needed(cls):
		"""Returns true if another checkpoint is called for"""
		return (time.time() > cls._last_checkpoint_time +
				Globals.checkpoint_interval)

	def checkpoint_remove(cls):
		"""Remove all checkpointing data after successful operation"""
		for rp in Resume.get_relevant_rps(): rp.delete()
		if Globals.preserve_hardlinks: Hardlink.remove_all_checkpoints()

MakeClass(SaveState)


class Resume:
	"""Check for old aborted backups and resume if necessary"""
	_session_info_list = None # List of ResumeSessionInfo's, sorted by time
	def FindTime(cls, index, later_than = 0):
		"""For a given index, find the appropriate time to use for inc

		If it is clear which time to use (because it is determined by
		definitive records, or there are no aborted backup, etc.) then
		just return the appropriate time.  Otherwise, if an aborted
		backup was last checkpointed before the index, assume that it
		didn't get there, and go for the older time.  If an inc file
		is already present, the function will be rerun with later time
		specified.

		"""
		if Time.prevtime > later_than: return Time.prevtime # usual case

		for si in cls.get_sis_covering_index(index):
			if si.time > later_than: return si.time
		raise SkipFileException("Index %s already covered, skipping" %
								str(index))

	def get_sis_covering_index(cls, index):
		"""Return sorted list of SessionInfos which may cover index

		Aborted backup may be relevant unless index is lower and we
		are sure that it didn't go further.

		"""
		return filter(lambda session_info:
					  not ((session_info.last_index is None or
							session_info.last_index < index) and
						   session_info.last_definitive), 
				cls._session_info_list)

	def SetSessionInfo(cls):
		"""Read data directory and initialize _session_info"""
		silist = []
		rp_quad_dict = cls.group_rps_by_time(cls.get_relevant_rps())
		times = rp_quad_dict.keys()
		times.sort()
		for time in times:
			silist.append(cls.quad_to_si(time, rp_quad_dict[time]))
		cls._session_info_list = silist

	def get_relevant_rps(cls):
		"""Return list of relevant rpaths in rbdata directory"""
		relevant_bases = ['last-file-incremented', 'last-file-mirrored',
						  'checkpoint-data', 'last-file-definitive']
		rps = map(Globals.rbdir.append, Globals.rbdir.listdir())
		return filter(lambda rp: rp.isincfile()
					  and rp.getincbase_str() in relevant_bases, rps)

	def group_rps_by_time(cls, rplist):
		"""Take list of rps return time dict {time: quadlist}

		Times in seconds are the keys, values are triples of rps
		[last-file-incremented, last-file-mirrored, checkpoint-data,
		 last-is-definitive].

		"""
		result = {}
		for rp in rplist:
			time = Time.stringtotime(rp.getinctime())
			if result.has_key(time): quadlist = result[time]
			else: quadlist = [None, None, None, None]
			base_string = rp.getincbase_str()
			if base_string == 'last-file-incremented': quadlist[0] = rp
			elif base_string == 'last-file-mirrored': quadlist[1] = rp
			elif base_string == 'last-file-definitive': quadlist[3] = 1
			else:
				assert base_string == 'checkpoint-data'
				quadlist[2] = rp
			result[time] = quadlist
		return result

	def quad_to_si(cls, time, quad):
		"""Take time, quadlist, return associated ResumeSessionInfo"""
		increment_sym, mirror_sym, checkpoint_rp, last_definitive = quad
		assert not (increment_sym and mirror_sym) # both shouldn't exist
		ITR, finalizer = None, None
		if increment_sym:
			mirror = None
			last_index = cls.sym_to_index(increment_sym)
			if checkpoint_rp:
				ITR, finalizer = cls.unpickle_checkpoint(checkpoint_rp)
		elif mirror_sym:
			mirror = 1
			last_index = cls.sym_to_index(mirror_sym)
			if checkpoint_rp:
				finalizer = cls.unpickle_checkpoint(checkpoint_rp)
		return ResumeSessionInfo(mirror, time, last_index, last_definitive,
								 finalizer, ITR)

	def sym_to_index(cls, sym_rp):
		"""Read last file sym rp, return last file index

		If sym_rp is not a sym at all, return None, indicating that no
		file index was ever conclusively processed.

		"""
		if not sym_rp.issym(): return None
		link_components = sym_rp.readlink().split("/")
		assert link_components[0] == 'increments'
		return tuple(link_components[1:])

	def unpickle_checkpoint(cls, checkpoint_rp):
		"""Read data from checkpoint_rp and return unpickled data

		Return value is pair finalizer state for a mirror checkpoint,
		and (patch increment ITR, finalizer state) for increment
		checkpoint.

		"""
		fp = checkpoint_rp.open("rb")
		data = fp.read()
		fp.close()
		return cPickle.loads(data)

	def ResumeCheck(cls):
		"""Return relevant ResumeSessionInfo if there's one we should resume

		Also if find RSI to resume, reset current time to old resume
		time.

		"""
		cls.SetSessionInfo()
		if not cls._session_info_list:
			if Globals.resume == 1: 
				Log.FatalError("User specified resume, but no data on "
							   "previous backup found.")
			else: return None
		else:
			si = cls._session_info_list[-1]
			if (Globals.resume == 1 or
				(time.time() <= (si.time + Globals.resume_window) and
				 not Globals.resume == 0)):
				Log("Resuming aborted backup dated %s" %
					Time.timetopretty(si.time), 2)
				Time.setcurtime(si.time)
				if Globals.preserve_hardlinks:
					if (not si.last_definitive or not
						Hardlink.retrieve_checkpoint(Globals.rbdir, si.time)):
						Log("Hardlink information not successfully "
							"recovered.", 2)
				return si
			else:
				Log("Last backup dated %s was aborted, but we aren't "
					"resuming it." % Time.timetopretty(si.time), 2)
				return None
		assert 0

MakeClass(Resume)


class ResumeSessionInfo:
	"""Hold information about a previously aborted session"""
	def __init__(self, mirror, time, last_index,
				 last_definitive, finalizer_state = None, ITR_state = None):
		"""Class initializer

		time - starting time in seconds of backup
		mirror - true if backup was a mirror, false if increment
		last_index - Last confirmed index processed by backup, or None
		last_definitive - True is we know last_index is really last
		finalizer_state - finalizer reducer state if available
		ITR_state - For increment, ITM reducer state (assume mirror if NA)

		"""
		self.time = time
		self.mirror = mirror
		self.last_index = last_index
		self.last_definitive = last_definitive
		self.ITR_state, self.finalizer_state, = ITR_state, finalizer_state
