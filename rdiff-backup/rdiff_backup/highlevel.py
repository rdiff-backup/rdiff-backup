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

"""High level functions for mirroring, mirror & inc, etc."""

from __future__ import generators
from static import *

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
	def Mirror(src_rpath, dest_rpath, inc_rpath = None, session_info = None):
		"""Turn dest_rpath into a copy of src_rpath

		If inc_rpath is true, then this is the initial mirroring of an
		incremental backup, so checkpoint and write to data_dir.
		Otherwise only mirror and don't create any extra files.

		"""
		SourceS = src_rpath.conn.HLSourceStruct
		DestS = dest_rpath.conn.HLDestinationStruct

		SourceS.set_session_info(session_info)
		DestS.set_session_info(session_info)
		src_init_dsiter = SourceS.split_initial_dsiter()
		dest_sigiter = DestS.get_sigs(dest_rpath, src_init_dsiter)
		diffiter = SourceS.get_diffs_and_finalize(dest_sigiter)
		if inc_rpath:
			DestS.patch_w_datadir_writes(dest_rpath, diffiter, inc_rpath)
		else: DestS.patch_and_finalize(dest_rpath, diffiter)

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
		else: Globals.select_source.set_iter(cls._session_info.last_index, 1)
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
		finalizer = IterTreeReducer(DestructiveSteppingFinalizer, [])
		def error_handler(exc, dest_sig, dsrp):
			Log("Error %s producing a diff of %s" %
				(exc, dsrp and dsrp.path), 2)
			return None
			
		def diffs():
			for dsrp, dest_sig in collated:
				if dest_sig:
					if dest_sig.isplaceholder(): yield dest_sig
					else:
						diff = Robust.check_common_error(
							error_handler, RORPIter.diffonce, [dest_sig, dsrp])
						if diff: yield diff
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
		"""Return signatures of all dissimilar files

		Also writes all metadata to the metadata file.

		"""
		dest_iters1 = cls.split_initial_dsiter()
		def duplicate_with_write(src_init_iter):
			"""Return iterator but write metadata of what passes through"""
			metadata.OpenMetadata()
			for rorp in src_init_iter:
				metadata.WriteMetadata(rorp)
				yield rorp
			metadata.CloseMetadata()
		dup = duplicate_with_write(src_init_iter)
		dissimilars = cls.get_dissimilar(baserp, dup, dest_iters1)
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
		else: return IterTreeReducer(DestructiveSteppingFinalizer, [])

	def get_ITR(cls, inc_rpath):
		"""Return ITR, starting from state if necessary"""
		if cls._session_info and cls._session_info.ITR:
			return cls._session_info.ITR
		else:
			iitr = IterTreeReducer(IncrementITRB, [inc_rpath])
			iitr.root_branch.override_changed()
			Globals.ITRB = iitr.root_branch
			iitr.root_branch.Errors = 0
			return iitr

	def get_MirrorITR(cls, inc_rpath):
		"""Return MirrorITR, starting from state if available"""
		if cls._session_info and cls._session_info.ITR:
			return cls._session_info.ITR
		ITR = IterTreeReducer(MirrorITRB, [inc_rpath])
		Globals.ITRB = ITR.root_branch
		ITR.root_branch.Errors = 0
		return ITR

	def patch_and_finalize(cls, dest_rpath, diffs):
		"""Apply diffs and finalize"""
		collated = RORPIter.CollateIterators(diffs, cls.initial_dsiter2)
		finalizer = cls.get_finalizer()
		diff_rorp, dsrp = None, None

		def patch(diff_rorp, dsrp):
			if not dsrp: dsrp = cls.get_dsrp(dest_rpath, diff_rorp.index)
			if diff_rorp and not diff_rorp.isplaceholder():
				RORPIter.patchonce_action(None, dsrp, diff_rorp).execute()
			return dsrp

		def error_handler(exc, diff_rorp, dsrp):
			filename = dsrp and dsrp.path or os.path.join(*diff_rorp.index)
			Log("Error: %s processing file %s" % (exc, filename), 2)
		
		for indexed_tuple in collated:
			Log(lambda: "Processing %s" % str(indexed_tuple), 7)
			diff_rorp, dsrp = indexed_tuple
			dsrp = Robust.check_common_error(error_handler, patch,
											 [diff_rorp, dsrp])
			finalizer(dsrp.index, dsrp)
		finalizer.Finish()

	def patch_w_datadir_writes(cls, dest_rpath, diffs, inc_rpath):
		"""Apply diffs and finalize, with checkpointing and statistics"""
		collated = RORPIter.CollateIterators(diffs, cls.initial_dsiter2)
		finalizer, ITR = cls.get_finalizer(), cls.get_MirrorITR(inc_rpath)
		MiscStats.open_dir_stats_file()
		dsrp, finished_dsrp = None, None

		try:
			for indexed_tuple in collated:
				Log(lambda: "Processing %s" % str(indexed_tuple), 7)
				diff_rorp, dsrp = indexed_tuple
				if not dsrp: dsrp = cls.get_dsrp(dest_rpath, diff_rorp.index)
				if diff_rorp and diff_rorp.isplaceholder(): diff_rorp = None
				ITR(dsrp.index, diff_rorp, dsrp)
				finalizer(dsrp.index, dsrp)
				SaveState.checkpoint(ITR, finalizer, dsrp)
				finished_dsrp = dsrp
			ITR.Finish()
			finalizer.Finish()
		except: cls.handle_last_error(finished_dsrp, finalizer, ITR)

		if Globals.preserve_hardlinks: Hardlink.final_writedata()
		MiscStats.close_dir_stats_file()
		MiscStats.write_session_statistics(ITR.root_branch)
		SaveState.checkpoint_remove()

	def patch_increment_and_finalize(cls, dest_rpath, diffs, inc_rpath):
		"""Apply diffs, write increment if necessary, and finalize"""
		collated = RORPIter.CollateIterators(diffs, cls.initial_dsiter2)
		finalizer, ITR = cls.get_finalizer(), cls.get_ITR(inc_rpath)
		MiscStats.open_dir_stats_file()
		dsrp, finished_dsrp = None, None

		try:
			for indexed_tuple in collated:
				Log(lambda: "Processing %s" % str(indexed_tuple), 7)
				diff_rorp, dsrp = indexed_tuple
				index = indexed_tuple.index
				if not dsrp: dsrp = cls.get_dsrp(dest_rpath, index)
				if diff_rorp and diff_rorp.isplaceholder(): diff_rorp = None
				ITR(index, diff_rorp, dsrp)
				finalizer(index, dsrp)
				SaveState.checkpoint(ITR, finalizer, dsrp)
				finished_dsrp = dsrp
			ITR.Finish()
			finalizer.Finish()
		except: cls.handle_last_error(finished_dsrp, finalizer, ITR)

		if Globals.preserve_hardlinks: Hardlink.final_writedata()
		MiscStats.close_dir_stats_file()
		MiscStats.write_session_statistics(ITR.root_branch)
		SaveState.checkpoint_remove()

	def handle_last_error(cls, dsrp, finalizer, ITR):
		"""If catch fatal error, try to checkpoint before exiting"""
		Log.exception(1, 2)
		TracebackArchive.log()
		SaveState.checkpoint(ITR, finalizer, dsrp, 1)
		if Globals.preserve_hardlinks: Hardlink.final_checkpoint(Globals.rbdir)
		SaveState.touch_last_file_definitive()
		raise

MakeClass(HLDestinationStruct)

from log import *
from rpath import *
from robust import *
from increment import *
from destructive_stepping import *
from rorpiter import *
import Globals, Hardlink, MiscStats, metadata
