from __future__ import generators
execfile("manage.py")

#######################################################################
#
# highlevel - High level functions for mirroring, mirror & inc, etc.
#

class SkipFileException(Exception):
	"""Signal that the current file should be skipped but then continue

	This exception will often be raised when there is problem reading
	an individual file, but it makes sense for the rest of the backup
	to keep going.

	"""
	pass


class HighLevel:
	"""High level static functions

	The design of some of these functions is represented on the
	accompanying diagram.

	"""
	def Mirror(src_rpath, dest_rpath, checkpoint = 1,
			   session_info = None, write_finaldata = 1):
		"""Turn dest_rpath into a copy of src_rpath

		Checkpoint true means to checkpoint periodically, otherwise
		not.  If session_info is given, try to resume Mirroring from
		that point.  If write_finaldata is true, save extra data files
		like hardlink_data.  If it is false, make a complete mirror.

		"""
		SourceS = src_rpath.conn.HLSourceStruct
		DestS = dest_rpath.conn.HLDestinationStruct

		SourceS.set_session_info(session_info)
		DestS.set_session_info(session_info)
		src_init_dsiter = SourceS.split_initial_dsiter()
		dest_sigiter = DestS.get_sigs(dest_rpath, src_init_dsiter)
		diffiter = SourceS.get_diffs_and_finalize(dest_sigiter)
		DestS.patch_and_finalize(dest_rpath, diffiter,
								 checkpoint, write_finaldata)

		dest_rpath.setdata()

	def Mirror_and_increment(src_rpath, dest_rpath, inc_rpath,
							 session_info = None):
		"""Mirror + put increments in tree based at inc_rpath"""
		SourceS = src_rpath.conn.HLSourceStruct
		DestS = dest_rpath.conn.HLDestinationStruct

		SourceS.set_session_info(session_info)
		DestS.set_session_info(session_info)
		if not session_info: dest_rpath.conn.SaveState.touch_last_file()
		src_init_dsiter = SourceS.split_initial_dsiter()
		dest_sigiter = DestS.get_sigs(dest_rpath, src_init_dsiter)
		diffiter = SourceS.get_diffs_and_finalize(dest_sigiter)
		DestS.patch_increment_and_finalize(dest_rpath, diffiter, inc_rpath)

		dest_rpath.setdata()
		inc_rpath.setdata()

MakeStatic(HighLevel)


class HLSourceStruct:
	"""Hold info used by HL on the source side"""
	_session_info = None # set to si if resuming
	def set_session_info(cls, session_info):
		cls._session_info = session_info

	def iterate_from(cls):
		"""Supply more aruments to DestructiveStepping.Iterate_from"""
		if cls._session_info is None: Globals.select_source.set_iter()
		else: Globals.select_source.set_iter(cls._session_info.last_index)
		return Globals.select_source

	def split_initial_dsiter(cls):
		"""Set iterators of all dsrps from rpath, returning one"""
		dsiter = cls.iterate_from()
		initial_dsiter1, cls.initial_dsiter2 = Iter.multiplex(dsiter, 2)
		return initial_dsiter1

	def get_diffs_and_finalize(cls, sigiter):
		"""Return diffs and finalize any dsrp changes remaining

		Return a rorpiterator with files included of signatures of
		dissimilar files.  This is the last operation run on the local
		filestream, so finalize dsrp writes.

		"""
		collated = RORPIter.CollateIterators(cls.initial_dsiter2, sigiter)
		finalizer = DestructiveSteppingFinalizer()
		def diffs():
			for dsrp, dest_sig in collated:
				if dest_sig:
					if dest_sig.isplaceholder(): yield dest_sig
					else:
						try: yield RORPIter.diffonce(dest_sig, dsrp)
						except (IOError, OSError, RdiffException):
							Log.exception()
							Log("Error producing a diff of %s" %
								dsrp and dsrp.path)
				if dsrp: finalizer(dsrp.index, dsrp)
			finalizer.Finish()
		return diffs()

MakeClass(HLSourceStruct)


class HLDestinationStruct:
	"""Hold info used by HL on the destination side"""
	_session_info = None # set to si if resuming
	def set_session_info(cls, session_info):
		cls._session_info = session_info

	def iterate_from(cls):
		"""Return selection iterator to iterate all the mirror files"""
		if cls._session_info is None: Globals.select_mirror.set_iter()
		else: Globals.select_mirror.set_iter(cls._session_info.last_index)
		return Globals.select_mirror

	def split_initial_dsiter(cls):
		"""Set initial_dsiters (iteration of all dsrps from rpath)"""
		result, cls.initial_dsiter2 = Iter.multiplex(cls.iterate_from(), 2)
		return result

	def get_dissimilar(cls, baserp, src_init_iter, dest_init_iter):
		"""Get dissimilars

		Returns an iterator which enumerates the dsrps which are
		different on the source and destination ends.  The dsrps do
		not necessarily exist on the destination end.

		Also, to prevent the system from getting backed up on the
		remote end, if we don't get enough dissimilars, stick in a
		placeholder every so often, like fiber.  The more
		placeholders, the more bandwidth used, but if there aren't
		enough, lots of memory will be used because files will be
		accumulating on the source side.  How much will accumulate
		will depend on the Globals.conn_bufsize value.

		"""
		collated = RORPIter.CollateIterators(src_init_iter, dest_init_iter)
		def compare(src_rorp, dest_dsrp):
			"""Return dest_dsrp if they are different, None if the same"""
			if not dest_dsrp:
				dest_dsrp = cls.get_dsrp(baserp, src_rorp.index)
				if dest_dsrp.lstat():
					Log("Warning: Found unexpected destination file %s, "
						"not processing it." % dest_dsrp.path, 2)
					return None
			elif (src_rorp and src_rorp == dest_dsrp and
				  (not Globals.preserve_hardlinks or
				   Hardlink.rorp_eq(src_rorp, dest_dsrp))):
				return None
			if src_rorp and src_rorp.isreg() and Hardlink.islinked(src_rorp):
				dest_dsrp.flaglinked()
			return dest_dsrp

		def generate_dissimilar():
			counter = 0
			for src_rorp, dest_dsrp in collated:
				if Globals.preserve_hardlinks:
					if src_rorp: Hardlink.add_rorp(src_rorp, 1)
					if dest_dsrp: Hardlink.add_rorp(dest_dsrp, None)
				dsrp = compare(src_rorp, dest_dsrp)
				if dsrp:
					counter = 0
					yield dsrp
				elif counter == 20:
					placeholder = RORPath(src_rorp.index)
					placeholder.make_placeholder()
					counter = 0
					yield placeholder
				else: counter += 1
		return generate_dissimilar()

	def get_sigs(cls, baserp, src_init_iter):
		"""Return signatures of all dissimilar files"""
		dest_iters1 = cls.split_initial_dsiter()
		dissimilars = cls.get_dissimilar(baserp, src_init_iter, dest_iters1)
		return RORPIter.Signatures(dissimilars)

	def get_dsrp(cls, dest_rpath, index):
		"""Return initialized dsrp based on dest_rpath with given index"""
		dsrp = DSRPath(None, dest_rpath.conn, dest_rpath.base, index)
		if Globals.quoting_enabled: dsrp.quote_path()
		return dsrp

	def get_finalizer(cls):
		"""Return finalizer, starting from session info if necessary"""
		old_finalizer = cls._session_info and cls._session_info.finalizer
		if old_finalizer: return old_finalizer
		else: return DestructiveSteppingFinalizer()

	def get_ITR(cls, inc_rpath):
		"""Return ITR, starting from state if necessary"""
		if cls._session_info and cls._session_info.ITR:
			return cls._session_info.ITR
		else:
			iitr = IncrementITR(inc_rpath)
			iitr.override_changed()
			return iitr

	def patch_and_finalize(cls, dest_rpath, diffs,
						   checkpoint = 1, write_finaldata = 1):
		"""Apply diffs and finalize"""
		collated = RORPIter.CollateIterators(diffs, cls.initial_dsiter2)
		finalizer = cls.get_finalizer()
		dsrp = None
		
		def error_checked():
			"""Inner writing loop, check this for errors"""
			indexed_tuple = collated.next()
			Log("Processing %s" % str(indexed_tuple), 7)
			diff_rorp, dsrp = indexed_tuple
			if not dsrp: dsrp = cls.get_dsrp(dest_rpath, diff_rorp.index)
			if diff_rorp and not diff_rorp.isplaceholder():
				RORPIter.patchonce_action(None, dsrp, diff_rorp).execute()
			finalizer(dsrp.index, dsrp)
			return dsrp

		try:
			while 1:
				try: dsrp = cls.check_skip_error(error_checked, dsrp)
				except StopIteration: break
				if checkpoint: SaveState.checkpoint_mirror(finalizer, dsrp)
		except: cls.handle_last_error(dsrp, finalizer)
		finalizer.Finish()
		if Globals.preserve_hardlinks and write_finaldata:
			Hardlink.final_writedata()
		if checkpoint: SaveState.checkpoint_remove()

	def patch_increment_and_finalize(cls, dest_rpath, diffs, inc_rpath):
		"""Apply diffs, write increment if necessary, and finalize"""
		collated = RORPIter.CollateIterators(diffs, cls.initial_dsiter2)
		finalizer, ITR = cls.get_finalizer(), cls.get_ITR(inc_rpath)
		dsrp = None

		def error_checked():
			"""Inner writing loop, catch variety of errors from this"""
			indexed_tuple = collated.next()
			Log("Processing %s" % str(indexed_tuple), 7)
			diff_rorp, dsrp = indexed_tuple
			index = indexed_tuple.index
			if not dsrp: dsrp = cls.get_dsrp(dest_rpath, index)
			if diff_rorp and diff_rorp.isplaceholder(): diff_rorp = None
			ITR(index, diff_rorp, dsrp)
			finalizer(index, dsrp)
			return dsrp

		try:
			while 1:
				try: dsrp = cls.check_skip_error(error_checked, dsrp)
				except StopIteration: break
				SaveState.checkpoint_inc_backup(ITR, finalizer, dsrp)
			cls.check_skip_error(ITR.Finish, dsrp)
			cls.check_skip_error(finalizer.Finish, dsrp)
		except: cls.handle_last_error(dsrp, finalizer, ITR)
		if Globals.preserve_hardlinks: Hardlink.final_writedata()
		SaveState.checkpoint_remove()

	def check_skip_error(cls, thunk, dsrp):
		"""Run thunk, catch certain errors skip files"""
		try: return thunk()
		except (EnvironmentError, SkipFileException, DSRPPermError,
				RPathException), exp:
			Log.exception()
			if (not isinstance(exc, EnvironmentError) or
				(errno.errorcode[exp[0]] in
				 ['EPERM', 'ENOENT', 'EACCES', 'EBUSY', 'EEXIST',
				  'ENOTDIR', 'ENAMETOOLONG', 'EINTR', 'ENOTEMPTY',
				  'EIO', # reported by docv
				  'ETXTBSY' # reported by Campbell on some NT system
				  ])):
				Log("Skipping file because of error after %s" %
					(dsrp and dsrp.index,), 2)
				return None
			else: raise

	def handle_last_error(cls, dsrp, finalizer, ITR = None):
		"""If catch fatal error, try to checkpoint before exiting"""
		Log.exception(1)
		if ITR: SaveState.checkpoint_inc_backup(ITR, finalizer, dsrp, 1)
		else: SaveState.checkpoint_mirror(finalizer, dsrp, 1)
		if Globals.preserve_hardlinks: Hardlink.final_checkpoint(Globals.rbdir)
		SaveState.touch_last_file_definitive()
		raise

MakeClass(HLDestinationStruct)
