from __future__ import generators
execfile("filelist.py")

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
	def Mirror(src_rpath, dest_rpath, checkpoint = 1, session_info = None):
		"""Turn dest_rpath into a copy of src_rpath

		Checkpoint true means to checkpoint periodically, otherwise
		not.  If session_info is given, try to resume Mirroring from
		that point.

		"""
		SourceS = src_rpath.conn.HLSourceStruct
		DestS = dest_rpath.conn.HLDestinationStruct

		SourceS.set_session_info(session_info)
		DestS.set_session_info(session_info)
		src_init_dsiter = SourceS.split_initial_dsiter(src_rpath)
		dest_sigiter = DestS.get_sigs(dest_rpath, src_init_dsiter)
		diffiter = SourceS.get_diffs_and_finalize(dest_sigiter)
		DestS.patch_and_finalize(dest_rpath, diffiter, checkpoint)

		dest_rpath.setdata()

	def Mirror_and_increment(src_rpath, dest_rpath, inc_rpath,
							 session_info = None):
		"""Mirror + put increments in tree based at inc_rpath"""
		SourceS = src_rpath.conn.HLSourceStruct
		DestS = dest_rpath.conn.HLDestinationStruct

		SourceS.set_session_info(session_info)
		DestS.set_session_info(session_info)
		if not session_info: dest_rpath.conn.SaveState.touch_last_file()
		src_init_dsiter = SourceS.split_initial_dsiter(src_rpath)
		dest_sigiter = DestS.get_sigs(dest_rpath, src_init_dsiter)
		diffiter = SourceS.get_diffs_and_finalize(dest_sigiter)
		DestS.patch_increment_and_finalize(dest_rpath, diffiter, inc_rpath)

		dest_rpath.setdata()
		inc_rpath.setdata()

	def Restore(rest_time, mirror_base, baseinc_tup, target_base):
		"""Like Restore.RestoreRecursive but check arguments"""
		if not isinstance(target_base, DSRPath):
			target_base = DSRPath(target_base.conn, target_base.base,
								  target_base.index, target_base.data)
		Restore.RestoreRecursive(rest_time, mirror_base,
								 baseinc_tup, target_base)

MakeStatic(HighLevel)


class HLSourceStruct:
	"""Hold info used by HL on the source side"""
	_session_info = None # set to si if resuming
	def set_session_info(cls, session_info):
		cls._session_info = session_info

	def iterate_from(cls, rpath):
		"""Supply more aruments to DestructiveStepping.Iterate_from"""
		if cls._session_info:
			return DestructiveStepping.Iterate_from(rpath, 1,
									   cls._session_info.last_index)
		else: return DestructiveStepping.Iterate_from(rpath, 1)

	def split_initial_dsiter(cls, rpath):
		"""Set iterators of all dsrps from rpath, returning one"""
		dsiter = cls.iterate_from(rpath)
		initial_dsiter1, cls.initial_dsiter2 = Iter.multiplex(dsiter, 2)
		return initial_dsiter1

	def get_diffs_and_finalize(cls, sigiter):
		"""Return diffs and finalize any dsrp changes remaining

		Return a rorpiterator with files included of signatures of
		dissimilar files.  This is the last operation run on the local
		filestream, so finalize dsrp writes.

		"""
		collated = RORPIter.CollateIterators(cls.initial_dsiter2, sigiter)
		finalizer = DestructiveStepping.Finalizer()
		def diffs():
			for dsrp, dest_sig in collated:
				try:
					if dest_sig:
						if dest_sig.isplaceholder(): yield dest_sig
						else: yield RORPIter.diffonce(dest_sig, dsrp)
					if dsrp: finalizer(dsrp)
				except (IOError, OSError, RdiffException):
					Log.exception()
					Log("Error processing %s, skipping" %
						str(dest_sig.index), 2)
			finalizer.getresult()
		return diffs()

MakeClass(HLSourceStruct)


class HLDestinationStruct:
	"""Hold info used by HL on the destination side"""
	_session_info = None # set to si if resuming
	def set_session_info(cls, session_info):
		cls._session_info = session_info

	def iterate_from(cls, rpath):
		"""Supply more arguments to DestructiveStepping.Iterate_from"""
		if cls._session_info:
			return DestructiveStepping.Iterate_from(rpath, None,
							       cls._session_info.last_index)
		else: return DestructiveStepping.Iterate_from(rpath, None)

	def split_initial_dsiter(cls, rpath):
		"""Set initial_dsiters (iteration of all dsrps from rpath)"""
		dsiter = cls.iterate_from(rpath)
		result, cls.initial_dsiter2 = Iter.multiplex(dsiter, 2)
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
		def generate_dissimilar():
			counter = 0
			for src_rorp, dest_dsrp in collated:
				if not dest_dsrp:
					dsrp = DSRPath(baserp.conn, baserp.base, src_rorp.index)
					if dsrp.lstat():
						Log("Warning: Found unexpected destination file %s."
							% dsrp.path, 2)
						if DestructiveStepping.isexcluded(dsrp, None): continue
					counter = 0
					yield dsrp
				elif not src_rorp or not src_rorp == dest_dsrp:
					counter = 0
					yield dest_dsrp
				else: # source and destinition both exist and are same
					if counter == 20:
						placeholder = RORPath(src_rorp.index)
						placeholder.make_placeholder()
						counter = 0
						yield placeholder
					else: counter += 1
		return generate_dissimilar()

	def get_sigs(cls, baserp, src_init_iter):
		"""Return signatures of all dissimilar files"""
		dest_iters1 = cls.split_initial_dsiter(baserp)
		dissimilars = cls.get_dissimilar(baserp, src_init_iter, dest_iters1)
		return RORPIter.Signatures(dissimilars)

	def get_dsrp(cls, dest_rpath, index):
		"""Return initialized dsrp based on dest_rpath with given index"""
		dsrp = DSRPath(dest_rpath.conn, dest_rpath.base, index)
		DestructiveStepping.initialize(dsrp, None)
		return dsrp

	def get_finalizer(cls):
		"""Return finalizer, starting from session info if necessary"""
		init_state = cls._session_info and cls._session_info.finalizer_state
		return DestructiveStepping.Finalizer(init_state)

	def get_ITR(cls, inc_rpath):
		"""Return ITR, starting from state if necessary"""
		init_state = cls._session_info and cls._session_info.ITR_state
		return Inc.make_patch_increment_ITR(inc_rpath, init_state)

	def patch_and_finalize(cls, dest_rpath, diffs, checkpoint = 1):
		"""Apply diffs and finalize"""
		collated = RORPIter.CollateIterators(diffs, cls.initial_dsiter2)
		finalizer = cls.get_finalizer()
		dsrp = None
		
		def error_checked():
			"""Inner writing loop, check this for errors"""
			indexed_tuple = collated.next()
			Log("Processing %s" % str(indexed_tuple), 7)
			diff_rorp, dsrp = indexed_tuple
			if not dsrp:
				dsrp = cls.get_dsrp(dest_rpath, diff_rorp.index)
				DestructiveStepping.initialize(dsrp, None)
			if diff_rorp and not diff_rorp.isplaceholder():
				RORPIter.patchonce_action(None, dsrp, diff_rorp).execute()
			finalizer(dsrp)
			return dsrp

		try:
			while 1:
				try: dsrp = cls.check_skip_error(error_checked)
				except StopIteration: break
				if checkpoint: SaveState.checkpoint_mirror(finalizer, dsrp)
		except: cls.handle_last_error(dsrp, finalizer)
		finalizer.getresult()
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
			if not dsrp:
				dsrp = cls.get_dsrp(dest_rpath, indexed_tuple.index)
				DestructiveStepping.initialize(dsrp, None)
				indexed_tuple = IndexedTuple(indexed_tuple.index,
											 (diff_rorp, dsrp))
			if diff_rorp and diff_rorp.isplaceholder():
				indexed_tuple = IndexedTuple(indexed_tuple.index,
											 (None, dsrp))
			ITR(indexed_tuple)
			finalizer(dsrp)
			return dsrp

		try:
			while 1:
				try: dsrp = cls.check_skip_error(error_checked)
				except StopIteration: break
				SaveState.checkpoint_inc_backup(ITR, finalizer, dsrp)
		except: cls.handle_last_error(dsrp, finalizer, ITR)
		ITR.getresult()
		finalizer.getresult()
		SaveState.checkpoint_remove()

	def check_skip_error(cls, thunk):
		"""Run thunk, catch certain errors skip files"""
		try: return thunk()
		except (IOError, OSError, SkipFileException), exp:
			Log.exception()
			if (not isinstance(exp, IOError) or
				(isinstance(exp, IOError) and
				 (exp[0] in [2,  # Means that a file is missing
							 5,  # Reported by docv (see list)
							 13, # Permission denied IOError
							 20, # Means a directory changed to non-dir
							 26, # Requested by Campbell (see list) -
                                 # happens on some NT systems
							 36] # filename too long
				 ))):
				Log("Skipping file", 2)
				return None
			else: raise

	def handle_last_error(cls, dsrp, finalizer, ITR = None):
		"""If catch fatal error, try to checkpoint before exiting"""
		Log.exception(1)
		if ITR: SaveState.checkpoint_inc_backup(ITR, finalizer, dsrp, 1)
		else: SaveState.checkpoint_mirror(finalizer, dsrp, 1)
		SaveState.touch_last_file_definitive()
		raise

MakeClass(HLDestinationStruct)
