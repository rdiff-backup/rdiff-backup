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

"""High level functions for mirroring and mirror+incrementing"""

from __future__ import generators
import Globals, metadata, rorpiter, TempFile, Hardlink, robust, increment, \
	   rpath, static, log, selection, Time, Rdiff, statistics

def Mirror(src_rpath, dest_rpath):
	"""Turn dest_rpath into a copy of src_rpath"""
	SourceS = src_rpath.conn.backup.SourceStruct
	DestS = dest_rpath.conn.backup.DestinationStruct

	DestS.init_statistics()
	source_rpiter = SourceS.get_source_select()
	dest_sigiter = DestS.process_source_get_sigs(dest_rpath, source_rpiter, 0)
	source_diffiter = SourceS.get_diffs(src_rpath, dest_sigiter)
	DestS.patch(dest_rpath, source_diffiter)
	DestS.write_statistics()

def Mirror_and_increment(src_rpath, dest_rpath, inc_rpath):
	"""Mirror + put increments in tree based at inc_rpath"""
	SourceS = src_rpath.conn.backup.SourceStruct
	DestS = dest_rpath.conn.backup.DestinationStruct

	DestS.init_statistics()
	source_rpiter = SourceS.get_source_select()
	dest_sigiter = DestS.process_source_get_sigs(dest_rpath, source_rpiter, 1)
	source_diffiter = SourceS.get_diffs(src_rpath, dest_sigiter)
	DestS.patch_and_increment(dest_rpath, source_diffiter, inc_rpath)
	DestS.write_statistics()


class SourceStruct:
	"""Hold info used on source side when backing up"""
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
		def get_one_diff(dest_sig):
			src_rp = baserp.new_index(dest_sig.index)
			diff_rorp = src_rp.getRORPath()
			if dest_sig.isflaglinked():
				diff_rorp.flaglinked(dest_sig.get_link_flag())
			elif dest_sig.isreg() and src_rp.isreg():
				diff_rorp.setfile(Rdiff.get_delta_sigrp(dest_sig, src_rp))
				diff_rorp.set_attached_filetype('diff')
			else:
				diff_rorp.set_attached_filetype('snapshot')
				if src_rp.isreg(): diff_rorp.setfile(src_rp.open("rb"))
			return diff_rorp

		for dest_sig in dest_sigiter:
			diff = robust.check_common_error(None, get_one_diff, [dest_sig])
			if diff: yield diff

static.MakeClass(SourceStruct)


class DestinationStruct:
	"""Hold info used by destination side when backing up"""
	def init_statistics(cls):
		"""Set cls.stats to StatFileObj object"""
		cls.statfileobj = statistics.init_statfileobj()

	def write_statistics(cls):
		"""Write statistics file"""
		statistics.write_active_statfileobj()

	def get_dest_select(cls, rpath, use_metadata = 1):
		"""Return destination select rorpath iterator

		If metadata file doesn't exist, select all files on
		destination except rdiff-backup-data directory.

		"""
		if use_metadata:
			metadata_iter = metadata.GetMetadata_at_time(Globals.rbdir,
														 Time.prevtime)
			if metadata_iter: return metadata_iter
			log.Log("Warning: Metadata file not found.\n"
					"Metadata will be read from filesystem.", 2)

		sel = selection.Select(rpath)
		sel.parse_rbdir_exclude()
		return sel.set_iter()

	def dest_iter_filter(cls, dest_iter):
		"""Destination rorps pass through this - record stats"""
		for dest_rorp in dest_iter:
			cls.statfileobj.add_dest_file(dest_rorp)
			Hardlink.add_rorp(dest_rorp, source = 0)
			yield dest_rorp

	def src_iter_filter(cls, source_iter):
		"""Source rorps pass through this - record stats, write metadata"""
		metadata.OpenMetadata()
		for src_rorp in source_iter:
			cls.statfileobj.add_source_file(src_rorp)
			Hardlink.add_rorp(src_rorp, source = 1)
			metadata.WriteMetadata(src_rorp)
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
		for index in rorpiter.get_dissimilar_indicies(source_iter, dest_iter,
													  cls.statfileobj):
			dest_rp = baserp.new_index(index)
			dest_sig = dest_rp.getRORPath()
			if Globals.preserve_hardlinks and Hardlink.islinked(dest_rp):
				dest_sig.flaglinked(Hardlink.get_link_index(dest_rp))
			elif dest_rp.isreg():
				dest_sig.setfile(Rdiff.get_signature(dest_rp))
			yield dest_sig

	def patch(cls, dest_rpath, source_diffiter, start_index = ()):
		"""Patch dest_rpath with an rorpiter of diffs"""
		ITR = rorpiter.IterTreeReducer(PatchITRB, [dest_rpath])
		for diff in rorpiter.FillInIter(source_diffiter, dest_rpath):
			log.Log("Processing changed file " + diff.get_indexpath(), 5)
			ITR(diff.index, diff)
		ITR.Finish()
		dest_rpath.setdata()

	def patch_and_increment(cls, dest_rpath, source_diffiter, inc_rpath):
		"""Patch dest_rpath with rorpiter of diffs and write increments"""
		ITR = rorpiter.IterTreeReducer(IncrementITRB, [dest_rpath, inc_rpath])
		for diff in rorpiter.FillInIter(source_diffiter, dest_rpath):
			log.Log("Processing changed file " + diff.get_indexpath(), 5)
			ITR(diff.index, diff)
		ITR.Finish()
		dest_rpath.setdata()

static.MakeClass(DestinationStruct)


class PatchITRB(rorpiter.ITRBranch):
	"""Patch an rpath with the given diff iters (use with IterTreeReducer)

	The main complication here involves directories.  We have to
	finish processing the directory after what's in the directory, as
	the directory may have inappropriate permissions to alter the
	contents or the dir's mtime could change as we change the
	contents.

	"""
	def __init__(self, basis_root_rp):
		"""Set basis_root_rp, the base of the tree to be incremented"""
		self.basis_root_rp = basis_root_rp
		assert basis_root_rp.conn is Globals.local_connection
		self.statfileobj = (statistics.get_active_statfileobj() or
							statistics.StatFileObj())
		self.dir_replacement, self.dir_update = None, None
		self.cached_rp = None

	def get_rp_from_root(self, index):
		"""Return RPath by adding index to self.basis_root_rp"""
		if not self.cached_rp or self.cached_rp.index != index:
			self.cached_rp = self.basis_root_rp.new_index(index)
		return self.cached_rp

	def can_fast_process(self, index, diff_rorp):
		"""True if diff_rorp and mirror are not directories"""
		rp = self.get_rp_from_root(index)
		return not diff_rorp.isdir() and not rp.isdir()

	def fast_process(self, index, diff_rorp):
		"""Patch base_rp with diff_rorp (case where neither is directory)"""
		rp = self.get_rp_from_root(index)
		tf = TempFile.new(rp)
		self.patch_to_temp(rp, diff_rorp, tf)
		tf.rename(rp)

	def patch_to_temp(self, basis_rp, diff_rorp, new):
		"""Patch basis_rp, writing output in new, which doesn't exist yet"""
		if diff_rorp.isflaglinked():
			Hardlink.link_rp(diff_rorp, new, self.basis_root_rp)
		elif diff_rorp.get_attached_filetype() == 'snapshot':
			rpath.copy(diff_rorp, new)
		else:
			assert diff_rorp.get_attached_filetype() == 'diff'
			Rdiff.patch_local(basis_rp, diff_rorp, new)
		if new.lstat(): rpath.copy_attribs(diff_rorp, new)

	def start_process(self, index, diff_rorp):
		"""Start processing directory - record information for later"""
		base_rp = self.base_rp = self.get_rp_from_root(index)
		assert diff_rorp.isdir() or base_rp.isdir() or not base_rp.index
		if diff_rorp.isdir(): self.prepare_dir(diff_rorp, base_rp)
		else: self.set_dir_replacement(diff_rorp, base_rp)

	def set_dir_replacement(self, diff_rorp, base_rp):
		"""Set self.dir_replacement, which holds data until done with dir

		This is used when base_rp is a dir, and diff_rorp is not.

		"""
		assert diff_rorp.get_attached_filetype() == 'snapshot'
		self.dir_replacement = TempFile.new(base_rp)
		rpath.copy_with_attribs(diff_rorp, self.dir_replacement)
		if base_rp.isdir(): base_rp.chmod(0700)

	def prepare_dir(self, diff_rorp, base_rp):
		"""Prepare base_rp to turn into a directory"""
		self.dir_update = diff_rorp.getRORPath() # make copy in case changes
		if not base_rp.isdir():
			if base_rp.lstat(): base_rp.delete()
			base_rp.mkdir()
		base_rp.chmod(0700)

	def end_process(self):
		"""Finish processing directory"""
		if self.dir_update:
			assert self.base_rp.isdir()
			rpath.copy_attribs(self.dir_update, self.base_rp)
		else:
			assert self.dir_replacement
			self.base_rp.rmdir()
			self.dir_replacement.rename(self.base_rp)


class IncrementITRB(PatchITRB):
	"""Patch an rpath with the given diff iters and write increments

	Like PatchITRB, but this time also write increments.

	"""
	def __init__(self, basis_root_rp, inc_root_rp):
		self.inc_root_rp = inc_root_rp
		self.cached_incrp = None
		PatchITRB.__init__(self, basis_root_rp)

	def get_incrp(self, index):
		"""Return inc RPath by adding index to self.basis_root_rp"""
		if not self.cached_incrp or self.cached_incrp.index != index:
			self.cached_incrp = self.inc_root_rp.new_index(index)
		return self.cached_incrp

	def fast_process(self, index, diff_rorp):
		"""Patch base_rp with diff_rorp and write increment (neither is dir)"""
		rp = self.get_rp_from_root(index)
		tf = TempFile.new(rp)
		self.patch_to_temp(rp, diff_rorp, tf)
		increment.Increment(tf, rp, self.get_incrp(index))
		tf.rename(rp)

	def start_process(self, index, diff_rorp):
		"""Start processing directory"""
		base_rp = self.base_rp = self.get_rp_from_root(index)
		assert diff_rorp.isdir() or base_rp.isdir()
		if diff_rorp.isdir():
			increment.Increment(diff_rorp, base_rp, self.get_incrp(index))
			self.prepare_dir(diff_rorp, base_rp)
		else:
			self.set_dir_replacement(diff_rorp, base_rp)
			increment.Increment(self.dir_replacement, base_rp,
								self.get_incrp(index))

