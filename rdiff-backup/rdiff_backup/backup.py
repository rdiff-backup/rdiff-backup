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

	source_rpiter = SourceS.get_source_select()
	DestS.set_rorp_cache(dest_rpath, source_rpiter, 0)
	dest_sigiter = DestS.get_sigs()
	source_diffiter = SourceS.get_diffs(dest_sigiter)
	DestS.patch(dest_rpath, source_diffiter)

def Mirror_and_increment(src_rpath, dest_rpath, inc_rpath):
	"""Mirror + put increments in tree based at inc_rpath"""
	SourceS = src_rpath.conn.backup.SourceStruct
	DestS = dest_rpath.conn.backup.DestinationStruct

	source_rpiter = SourceS.get_source_select()
	DestS.set_rorp_cache(dest_rpath, source_rpiter, 1)
	dest_sigiter = DestS.get_sigs()
	source_diffiter = SourceS.get_diffs(dest_sigiter)
	DestS.patch_and_increment(dest_rpath, source_diffiter, inc_rpath)


class SourceStruct:
	"""Hold info used on source side when backing up"""
	source_select = None # will be set to source Select iterator
	def set_source_select(cls, rpath, tuplelist, *filelists):
		"""Initialize select object using tuplelist

		Note that each list in filelists must each be passed as
		separate arguments, so each is recognized as a file by the
		connection.  Otherwise we will get an error because a list
		containing files can't be pickled.

		Also, cls.source_select needs to be cached so get_diffs below
		can retrieve the necessary rps.

		"""
		sel = selection.Select(rpath)
		sel.ParseArgs(tuplelist, filelists)
		sel.set_iter()
		cache_size = Globals.pipeline_max_length * 2 # 2 because to and from
		cls.source_select = rorpiter.CacheIndexable(sel, cache_size)

	def get_source_select(cls):
		"""Return source select iterator, set by set_source_select"""
		return cls.source_select

	def get_diffs(cls, dest_sigiter):
		"""Return diffs of any files with signature in dest_sigiter"""
		source_rps = cls.source_select
		def get_one_diff(dest_sig):
			src_rp = (source_rps.get(dest_sig.index) or
					  rpath.RORPath(dest_sig.index))
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

	def set_rorp_cache(cls, baserp, source_iter, for_increment):
		"""Initialize cls.CCPP, the destination rorp cache

		for_increment should be true if we are mirror+incrementing,
		false if we are just mirroring.

		"""
		dest_iter = cls.get_dest_select(baserp, for_increment)
		collated = rorpiter.Collate2Iters(source_iter, dest_iter)
		cls.CCPP = CacheCollatedPostProcess(collated,
											Globals.pipeline_max_length*2)
		
	def get_sigs(cls):
		"""Yield signatures of any changed destination files"""
		for src_rorp, dest_rorp in cls.CCPP:
			if (src_rorp and dest_rorp and src_rorp == dest_rorp and
				(not Globals.preserve_hardlinks or
				 Hardlink.rorp_eq(src_rorp, dest_rorp))): continue
			index = src_rorp and src_rorp.index or dest_rorp.index
			cls.CCPP.flag_changed(index)
			if (Globals.preserve_hardlinks and
				Hardlink.islinked(src_rorp or dest_rorp)):
				dest_sig = rpath.RORPath(index)
				dest_sig.flaglinked(Hardlink.get_link_index(dest_sig))
			elif dest_rorp:
				dest_sig = dest_rorp.getRORPath()
				if dest_rorp.isreg():
					dest_sig.setfile(Rdiff.get_signature(dest_rorp))
			else: dest_sig = rpath.RORPath(index)
			yield dest_sig			

	def patch(cls, dest_rpath, source_diffiter, start_index = ()):
		"""Patch dest_rpath with an rorpiter of diffs"""
		ITR = rorpiter.IterTreeReducer(PatchITRB, [dest_rpath, cls.CCPP])
		for diff in rorpiter.FillInIter(source_diffiter, dest_rpath):
			log.Log("Processing changed file " + diff.get_indexpath(), 5)
			ITR(diff.index, diff)
		ITR.Finish()
		cls.CCPP.close()
		dest_rpath.setdata()

	def patch_and_increment(cls, dest_rpath, source_diffiter, inc_rpath):
		"""Patch dest_rpath with rorpiter of diffs and write increments"""
		ITR = rorpiter.IterTreeReducer(IncrementITRB,
									   [dest_rpath, inc_rpath, cls.CCPP])
		for diff in rorpiter.FillInIter(source_diffiter, dest_rpath):
			log.Log("Processing changed file " + diff.get_indexpath(), 5)
			ITR(diff.index, diff)
		ITR.Finish()
		cls.CCPP.close()
		dest_rpath.setdata()

static.MakeClass(DestinationStruct)


class CacheCollatedPostProcess:
	"""Cache a collated iter of (source_rorp, dest_rp) pairs

	This is necessary for two reasons:

	1.  The patch function may need the original source_rorp or
	    dest_rp information, which is not present in the diff it
	    receives.

	2.  The metadata must match what is stored in the destination
	    directory.  If there is an error we do not update the dest
	    directory for that file, and the old metadata is used.  Thus
	    we cannot write any metadata until we know the file has been
	    procesed correctly.

	The class caches older source_rorps and dest_rps so the patch
	function can retrieve them if necessary.  The patch function can
	also update the processed correctly flag.  When an item falls out
	of the cache, we assume it has been processed, and write the
	metadata for it.

	"""
	def __init__(self, collated_iter, cache_size):
		"""Initialize new CCWP."""
		self.iter = collated_iter # generates (source_rorp, dest_rorp) pairs
		self.cache_size = cache_size
		self.statfileobj = statistics.init_statfileobj()
		metadata.OpenMetadata()

		# the following should map indicies to lists [source_rorp,
		# dest_rorp, changed_flag, success_flag] where changed_flag
		# should be true if the rorps are different, and success_flag
		# should be true if dest_rorp has been successfully updated to
		# source_rorp.  They both default to false.
		self.cache_dict = {}
		self.cache_indicies = []

	def __iter__(self): return self

	def next(self):
		"""Return next (source_rorp, dest_rorp) pair.  StopIteration passed"""
		source_rorp, dest_rorp = self.iter.next()
		self.pre_process(source_rorp, dest_rorp)
		index = source_rorp and source_rorp.index or dest_rorp.index
		self.cache_dict[index] = [source_rorp, dest_rorp, 0, 0]
		self.cache_indicies.append(index)

		if len(self.cache_indicies) > self.cache_size: self.shorten_cache()
		return source_rorp, dest_rorp

	def pre_process(self, source_rorp, dest_rorp):
		"""Do initial processing on source_rorp and dest_rorp

		It will not be clear whether source_rorp and dest_rorp have
		errors at this point, so don't do anything which assumes they
		will be backed up correctly.

		"""
		if source_rorp: Hardlink.add_rorp(source_rorp, source = 1)
		if dest_rorp: Hardlink.add_rorp(dest_rorp, source = 0)

	def shorten_cache(self):
		"""Remove one element from cache, possibly adding it to metadata"""
		first_index = self.cache_indicies[0]
		del self.cache_indicies[0]
		old_source_rorp, old_dest_rorp, changed_flag, success_flag = \
						 self.cache_dict[first_index]
		del self.cache_dict[first_index]
		self.post_process(old_source_rorp, old_dest_rorp,
						  changed_flag, success_flag)

	def post_process(self, source_rorp, dest_rorp, changed, success):
		"""Post process source_rorp and dest_rorp.

		changed will be true if the files have changed.  success will
		be true if the files have been successfully updated (this is
		always false for un-changed files).

		"""
		if not changed or success:
			self.statfileobj.add_source_file(source_rorp)
			self.statfileobj.add_dest_file(dest_rorp)
		if success:
			self.statfileobj.add_changed(source_rorp, dest_rorp)
			metadata_rorp = source_rorp
		else:
			metadata_rorp = dest_rorp
			if changed: self.statfileobj.add_error()
		if metadata_rorp and metadata_rorp.lstat():
			metadata.WriteMetadata(metadata_rorp)

	def flag_success(self, index):
		"""Signal that the file with given index was updated successfully"""
		self.cache_dict[index][3] = 1

	def flag_changed(self, index):
		"""Signal that the file with given index has changed"""
		self.cache_dict[index][2] = 1

	def get_rorps(self, index):
		"""Retrieve (source_rorp, dest_rorp) from cache"""
		return self.cache_dict[index][:2]

	def get_source_rorp(self, index):
		"""Retrieve source_rorp with given index from cache"""
		return self.cache_dict[index][0]

	def close(self):
		"""Process the remaining elements in the cache"""
		while self.cache_indicies: self.shorten_cache()
		metadata.CloseMetadata()
		statistics.write_active_statfileobj()


class PatchITRB(rorpiter.ITRBranch):
	"""Patch an rpath with the given diff iters (use with IterTreeReducer)

	The main complication here involves directories.  We have to
	finish processing the directory after what's in the directory, as
	the directory may have inappropriate permissions to alter the
	contents or the dir's mtime could change as we change the
	contents.

	"""
	def __init__(self, basis_root_rp, rorp_cache):
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
		rpath.rename(tf, rp)

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
			if self.dir_replacement.lstat():
				rpath.rename(self.dir_replacement, self.base_rp)


class IncrementITRB(PatchITRB):
	"""Patch an rpath with the given diff iters and write increments

	Like PatchITRB, but this time also write increments.

	"""
	def __init__(self, basis_root_rp, inc_root_rp, rorp_cache):
		self.inc_root_rp = inc_root_rp
		self.cached_incrp = None
		PatchITRB.__init__(self, basis_root_rp, rorp_cache)

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
		rpath.rename(tf, rp)

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

