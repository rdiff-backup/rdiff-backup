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
import Globals, MiscStats, metadata, rorpiter, TempFile, Hardlink, \
	   robust, increment, rpath, lazy, static, log, selection, Time, Rdiff


def Mirror(src_rpath, dest_rpath):
	"""Turn dest_rpath into a copy of src_rpath"""
	SourceS = src_rpath.conn.highlevel.HLSourceStruct
	DestS = dest_rpath.conn.highlevel.HLDestinationStruct

	source_rpiter = SourceS.get_source_select()
	dest_sigiter = DestS.process_source_get_sigs(dest_rpath,
												 source_rpiter, 0)
	source_diffiter = SourceS.get_diffs(src_rpath, dest_sigiter)
	DestS.patch(dest_rpath, source_diffiter)

def Mirror_and_increment(src_rpath, dest_rpath, inc_rpath):
	"""Mirror + put increments in tree based at inc_rpath"""
	SourceS = src_rpath.conn.highlevel.HLSourceStruct
	DestS = dest_rpath.conn.highlevel.HLDestinationStruct

	source_rpiter = SourceS.get_source_select()
	dest_sigiter = DestS.process_source_get_sigs(dest_rpath,
												 source_rpiter, 1)
	source_diffiter = SourceS.get_diffs(src_rpath, dest_sigiter)
	DestS.patch_and_increment(dest_rpath, source_diffiter, inc_rpath)


class HLSourceStruct:
	"""Hold info used by HL on the source side"""
	source_select = None # will be set to source Select iterator
	def set_source_select(cls, rpath, tuplelist, *filelists):
		"""Initialize select object using tuplelist

		Note that each list in filelists must each be passed as
		separate arguments, so each is recognized as a file by the
		connection.  Otherwise we will get an error because a list
		containing files can't be pickled.

		"""
		sel = selection.Select(rpath)
		sel.ParseArgs(tuplelist, filelists)
		cls.source_select = sel.set_iter()

	def get_source_select(cls):
		"""Return source select iterator, set by set_source_select"""
		return cls.source_select

	def get_diffs(cls, baserp, dest_sigiter):
		"""Return diffs of any files with signature in dest_sigiter"""
		for dest_sig in dest_sigiter:
			src_rp = baserp.new_index(dest_sig.index)
			diff_rorp = src_rp.getRORPath()
			if dest_sig.isflaglinked(): diff_rorp.flaglinked()
			elif dest_sig.isreg() and src_rp.isreg():
				diff_rorp.setfile(Rdiff.get_delta_sigrp(dest_sig, src_rp))
				diff_rorp.set_attached_filetype('diff')
			else:
				diff_rorp.set_attached_filetype('snapshot')
				if src_rp.isreg(): diff_rorp.setfile(src_rp.open("rb"))
			yield diff_rorp

static.MakeClass(HLSourceStruct)


class HLDestinationStruct:
	"""Hold info used by HL on the destination side"""
	def get_dest_select(cls, rpath, use_metadata = 1):
		"""Return destination select rorpath iterator

		If metadata file doesn't exist, select all files on
		destination except rdiff-backup-data directory.

		"""
		if use_metadata:
			metadata_iter = metadata.GetMetadata_at_time(Globals.rbdir,
														 Time.curtime)
			if metadata_iter: return metadata_iter
			log.Log("Warning: Metadata file not found.\n"
					"Metadata will be read from filesystem.", 2)

		sel = selection.Select(rpath)
		sel.parse_rbdir_exclude()
		return sel.set_iter()

	def dest_iter_filter(cls, dest_iter):
		"""Destination rorps pass through this - record stats"""
		for dest_rorp in dest_iter:
			# XXX Statistics process
			Hardlink.add_rorp(dest_rorp, source = 0)
			yield dest_rorp

	def src_iter_filter(cls, source_iter):
		"""Source rorps pass through this - record stats, write metadata"""
		metadata.OpenMetadata()
		for src_rorp in source_iter:
			Hardlink.add_rorp(src_rorp, source = 1)
			metadata.WriteMetadata(src_rorp)
			#XXXX Statistics process
			yield src_rorp
		metadata.CloseMetadata()

	def process_source_get_sigs(cls, baserp, source_iter, for_increment):
		"""Process the source rorpiter and return signatures of dest dir

		Write all metadata to file, then return signatures of any
		destination files that have changed.  for_increment should be
		true if we are mirror+incrementing, and false if we are just
		mirroring.

		"""
		source_iter = cls.src_iter_filter(source_iter)
		dest_iter = cls.dest_iter_filter(cls.get_dest_select(baserp,
															 for_increment))
		for index in rorpiter.get_dissimilar_indicies(source_iter, dest_iter):
			dest_rp = baserp.new_index(index)
			dest_sig = dest_rp.getRORPath()
			if Globals.preserve_hardlinks and Hardlink.islinked(dest_rp):
				dest_sig.flaglinked()
			elif dest_rp.isreg():
				dest_sig.setfile(Rdiff.get_signature(dest_rp))
			yield dest_sig

	def patch(cls, dest_rpath, source_diffiter):
		"""Patch dest_rpath with an rorpiter of diffs"""
		ITR = rorpiter.IterTreeReducer(increment.PatchITRB, [dest_rpath])
		for diff in rorpiter.FillInIter(source_diffiter, dest_rpath):
			ITR(diff.index, diff)
		ITR.Finish()
		dest_rpath.setdata()

	def patch_and_increment(cls, dest_rpath, source_diffiter, inc_rpath):
		"""Patch dest_rpath with rorpiter of diffs and write increments"""
		ITR = rorpiter.IterTreeReducer(increment.IncrementITRB,
									   [dest_rpath, inc_rpath])
		for diff in rorpiter.FillInIter(source_diffiter, dest_rpath):
			ITR(diff.index, diff)
		ITR.Finish()
		dest_rpath.setdata()

	def patch_increment_and_finalize(cls, dest_rpath, diffs, inc_rpath):
		"""Apply diffs, write increment if necessary, and finalize"""
		collated = rorpiter.CollateIterators(diffs, cls.initial_dsiter2)
		#finalizer, ITR = cls.get_finalizer(), cls.get_ITR(inc_rpath)
		finalizer, ITR = None, cls.get_ITR(inc_rpath)
		MiscStats.open_dir_stats_file()
		dsrp, finished_dsrp = None, None

		try:
			for indexed_tuple in collated:
				log.Log(lambda: "Processing %s" % str(indexed_tuple), 7)
				diff_rorp, dsrp = indexed_tuple
				index = indexed_tuple.index
				if not dsrp: dsrp = cls.get_dsrp(dest_rpath, index)
				if diff_rorp and diff_rorp.isplaceholder(): diff_rorp = None
				ITR(index, diff_rorp, dsrp)
				#finalizer(index, dsrp)
				finished_dsrp = dsrp
			ITR.Finish()
			#finalizer.Finish()
		except: cls.handle_last_error(finished_dsrp, finalizer, ITR)

		if Globals.preserve_hardlinks: Hardlink.final_writedata()
		MiscStats.close_dir_stats_file()
		MiscStats.write_session_statistics(ITR.root_branch)

	def handle_last_error(cls, dsrp, finalizer, ITR):
		"""If catch fatal error, try to checkpoint before exiting"""
		log.Log.exception(1, 2)
		robust.TracebackArchive.log()
		#SaveState.checkpoint(ITR, finalizer, dsrp, 1)
		#if Globals.preserve_hardlinks: Hardlink.final_checkpoint(Globals.rbdir)
		#SaveState.touch_last_file_definitive()
		raise

static.MakeClass(HLDestinationStruct)

