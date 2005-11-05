# Copyright 2002, 2003 Ben Escoto
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
import errno
import Globals, metadata, rorpiter, TempFile, Hardlink, robust, increment, \
	   rpath, static, log, selection, Time, Rdiff, statistics, iterfile, \
	   hash

def Mirror(src_rpath, dest_rpath):
	"""Turn dest_rpath into a copy of src_rpath"""
	log.Log("Starting mirror %s to %s" % (src_rpath.path, dest_rpath.path), 4)
	SourceS = src_rpath.conn.backup.SourceStruct
	DestS = dest_rpath.conn.backup.DestinationStruct

	source_rpiter = SourceS.get_source_select()
	DestS.set_rorp_cache(dest_rpath, source_rpiter, 0)
	dest_sigiter = DestS.get_sigs(dest_rpath)
	source_diffiter = SourceS.get_diffs(dest_sigiter)
	DestS.patch(dest_rpath, source_diffiter)

def Mirror_and_increment(src_rpath, dest_rpath, inc_rpath):
	"""Mirror + put increments in tree based at inc_rpath"""
	log.Log("Starting increment operation %s to %s" %
			(src_rpath.path, dest_rpath.path), 4)
	SourceS = src_rpath.conn.backup.SourceStruct
	DestS = dest_rpath.conn.backup.DestinationStruct

	source_rpiter = SourceS.get_source_select()
	DestS.set_rorp_cache(dest_rpath, source_rpiter, 1)
	dest_sigiter = DestS.get_sigs(dest_rpath)
	source_diffiter = SourceS.get_diffs(dest_sigiter)
	DestS.patch_and_increment(dest_rpath, source_diffiter, inc_rpath)


class SourceStruct:
	"""Hold info used on source side when backing up"""
	_source_select = None # will be set to source Select iterator
	def set_source_select(cls, rpath, tuplelist, *filelists):
		"""Initialize select object using tuplelist

		Note that each list in filelists must each be passed as
		separate arguments, so each is recognized as a file by the
		connection.  Otherwise we will get an error because a list
		containing files can't be pickled.

		Also, cls._source_select needs to be cached so get_diffs below
		can retrieve the necessary rps.

		"""
		sel = selection.Select(rpath)
		sel.ParseArgs(tuplelist, filelists)
		sel.set_iter()
		cache_size = Globals.pipeline_max_length * 3 # to and from+leeway
		cls._source_select = rorpiter.CacheIndexable(sel, cache_size)
		Globals.set('select_mirror', sel)

	def get_source_select(cls):
		"""Return source select iterator, set by set_source_select"""
		return cls._source_select

	def get_diffs(cls, dest_sigiter):
		"""Return diffs of any files with signature in dest_sigiter"""
		source_rps = cls._source_select
		error_handler = robust.get_error_handler("ListError")
		def attach_snapshot(diff_rorp, src_rp):
			"""Attach file of snapshot to diff_rorp, w/ error checking"""
			fileobj = robust.check_common_error(
				error_handler, rpath.RPath.open, (src_rp, "rb"))
			if fileobj: diff_rorp.setfile(hash.FileWrapper(fileobj))
			else: diff_rorp.zero()
			diff_rorp.set_attached_filetype('snapshot')

		def attach_diff(diff_rorp, src_rp, dest_sig):
			"""Attach file of diff to diff_rorp, w/ error checking"""
			fileobj = robust.check_common_error(
				error_handler, Rdiff.get_delta_sigrp_hash, (dest_sig, src_rp))
			if fileobj:
				diff_rorp.setfile(fileobj)
				diff_rorp.set_attached_filetype('diff')
			else:
				diff_rorp.zero()
				diff_rorp.set_attached_filetype('snapshot')
				
		for dest_sig in dest_sigiter:
			if dest_sig is iterfile.MiscIterFlushRepeat:
				yield iterfile.MiscIterFlush # Flush buffer when get_sigs does
				continue
			src_rp = (source_rps.get(dest_sig.index) or
					  rpath.RORPath(dest_sig.index))
			diff_rorp = src_rp.getRORPath()
			if dest_sig.isflaglinked():
				diff_rorp.flaglinked(dest_sig.get_link_flag())
			elif dest_sig.isreg() and src_rp.isreg():
				attach_diff(diff_rorp, src_rp, dest_sig)
			elif src_rp.isreg():
				attach_snapshot(diff_rorp, src_rp)
				dest_sig.close_if_necessary()
			else: diff_rorp.set_attached_filetype('snapshot')
			yield diff_rorp

static.MakeClass(SourceStruct)


class DestinationStruct:
	"""Hold info used by destination side when backing up"""
	def get_dest_select(cls, rpath, use_metadata = 1):
		"""Return destination select rorpath iterator

		If metadata file doesn't exist, select all files on
		destination except rdiff-backup-data directory.

		"""
		def get_iter_from_fs():
			"""Get the combined iterator from the filesystem"""
			sel = selection.Select(rpath)
			sel.parse_rbdir_exclude()
			return sel.set_iter()

		metadata.SetManager()
		if use_metadata:
			rorp_iter = metadata.ManagerObj.GetAtTime(Time.prevtime)
			if rorp_iter: return rorp_iter
		return get_iter_from_fs()

	def set_rorp_cache(cls, baserp, source_iter, for_increment):
		"""Initialize cls.CCPP, the destination rorp cache

		for_increment should be true if we are mirror+incrementing,
		false if we are just mirroring.

		"""
		dest_iter = cls.get_dest_select(baserp, for_increment)
		collated = rorpiter.Collate2Iters(source_iter, dest_iter)
		cls.CCPP = CacheCollatedPostProcess(
			collated, Globals.pipeline_max_length*4, baserp)
		# pipeline len adds some leeway over just*3 (to and from and back)
		
	def get_sigs(cls, dest_base_rpath):
		"""Yield signatures of any changed destination files

		If we are backing up across a pipe, we must flush the pipeline
		every so often so it doesn't get congested on destination end.

		"""
		flush_threshold = int(Globals.pipeline_max_length/2)
		num_rorps_skipped = 0
		for src_rorp, dest_rorp in cls.CCPP:
			if (src_rorp and dest_rorp and src_rorp == dest_rorp and
				(not Globals.preserve_hardlinks or
				 Hardlink.rorp_eq(src_rorp, dest_rorp))):
				num_rorps_skipped += 1
				if (Globals.backup_reader is not Globals.backup_writer and
					num_rorps_skipped > flush_threshold):
					num_rorps_skipped = 0
					yield iterfile.MiscIterFlushRepeat
			else:
				index = src_rorp and src_rorp.index or dest_rorp.index
				sig = cls.get_one_sig(dest_base_rpath, index,
									  src_rorp, dest_rorp)
				if sig:
					cls.CCPP.flag_changed(index)
					yield sig

	def get_one_sig(cls, dest_base_rpath, index, src_rorp, dest_rorp):
		"""Return a signature given source and destination rorps"""
		if (Globals.preserve_hardlinks and src_rorp and
			Hardlink.islinked(src_rorp)):
			dest_sig = rpath.RORPath(index)
			dest_sig.flaglinked(Hardlink.get_link_index(src_rorp))
		elif dest_rorp:
			dest_sig = dest_rorp.getRORPath()
			if dest_rorp.isreg():
				sig_fp = cls.get_one_sig_fp(dest_base_rpath.new_index(index))
				if sig_fp is None: return None
				dest_sig.setfile(sig_fp)
		else: dest_sig = rpath.RORPath(index)
		return dest_sig			

	def get_one_sig_fp(cls, dest_rp):
		"""Return a signature fp of given index, corresponding to reg file"""
		if not dest_rp.isreg():
			log.ErrorLog.write_if_open("UpdateError", dest_rp,
				"File changed from regular file before signature")
			return None
		if Globals.process_uid != 0 and not dest_rp.readable():
			# This branch can happen with root source and non-root
			# destination.  Permissions are changed permanently, which
			# should propogate to the diffs
			assert dest_rp.isowner(), 'no ownership of %s' % (dest_rp.path,)
			dest_rp.chmod(0400 | dest_rp.getperms())
		return Rdiff.get_signature(dest_rp)
				
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
	"""Cache a collated iter of (source_rorp, dest_rorp) pairs

	This is necessary for three reasons:

	1.  The patch function may need the original source_rorp or
	    dest_rp information, which is not present in the diff it
	    receives.

	2.  The metadata must match what is stored in the destination
	    directory.  If there is an error, either we do not update the
	    dest directory for that file and the old metadata is used, or
	    the file is deleted on the other end..  Thus we cannot write
	    any metadata until we know the file has been procesed
	    correctly.

	3.  We may lack permissions on certain destination directories.
	    The permissions of these directories need to be relaxed before
	    we enter them to computer signatures, and then reset after we
	    are done patching everything inside them.

	4.  We need some place to put hashes (like SHA1) after computing
	    them and before writing them to the metadata.

	The class caches older source_rorps and dest_rps so the patch
	function can retrieve them if necessary.  The patch function can
	also update the processed correctly flag.  When an item falls out
	of the cache, we assume it has been processed, and write the
	metadata for it.

	"""
	def __init__(self, collated_iter, cache_size, dest_root_rp):
		"""Initialize new CCWP."""
		self.iter = collated_iter # generates (source_rorp, dest_rorp) pairs
		self.cache_size = cache_size
		self.dest_root_rp = dest_root_rp

		self.statfileobj = statistics.init_statfileobj()
		if Globals.file_statistics: statistics.FileStats.init()
		self.metawriter = metadata.ManagerObj.GetWriter()

		# the following should map indicies to lists
		# [source_rorp, dest_rorp, changed_flag, success_flag, increment]

		# changed_flag should be true if the rorps are different, and

		# success_flag should be 1 if dest_rorp has been successfully
		# updated to source_rorp, and 2 if the destination file is
		# deleted entirely.  They both default to false (0).
		
		# increment holds the RPath of the increment file if one
		# exists.  It is used to record file statistics.
		
		self.cache_dict = {}
		self.cache_indicies = []

		# Contains a list of pairs (destination_rps, permissions) to
		# be used to reset the permissions of certain directories
		# after we're finished with them
		self.dir_perms_list = []

		# A dictionary of {index: source_rorp}.  We use this to
		# hold the digest of a hard linked file so it only needs to be
		# computed once.
		self.inode_digest_dict = {}

	def __iter__(self): return self

	def next(self):
		"""Return next (source_rorp, dest_rorp) pair.  StopIteration passed"""
		source_rorp, dest_rorp = self.iter.next()
		self.pre_process(source_rorp, dest_rorp)
		index = source_rorp and source_rorp.index or dest_rorp.index
		self.cache_dict[index] = [source_rorp, dest_rorp, 0, 0, None]
		self.cache_indicies.append(index)

		if len(self.cache_indicies) > self.cache_size: self.shorten_cache()
		return source_rorp, dest_rorp

	def pre_process(self, source_rorp, dest_rorp):
		"""Do initial processing on source_rorp and dest_rorp

		It will not be clear whether source_rorp and dest_rorp have
		errors at this point, so don't do anything which assumes they
		will be backed up correctly.

		"""
		if Globals.preserve_hardlinks and source_rorp:
			if Hardlink.add_rorp(source_rorp, dest_rorp):
				self.inode_digest_dict[source_rorp.index] = source_rorp
		if (dest_rorp and dest_rorp.isdir() and Globals.process_uid != 0
			and dest_rorp.getperms() % 01000 < 0700):
			self.unreadable_dir_init(source_rorp, dest_rorp)

	def unreadable_dir_init(self, source_rorp, dest_rorp):
		"""Initialize an unreadable dir.

		Make it readable, and if necessary, store the old permissions
		in self.dir_perms_list so the old perms can be restored.

		"""
		dest_rp = self.dest_root_rp.new_index(dest_rorp.index)
		dest_rp.chmod(0700 | dest_rorp.getperms())
		if source_rorp and source_rorp.isdir():
			self.dir_perms_list.append((dest_rp, source_rorp.getperms()))

	def shorten_cache(self):
		"""Remove one element from cache, possibly adding it to metadata"""
		first_index = self.cache_indicies[0]
		del self.cache_indicies[0]
		try: (old_source_rorp, old_dest_rorp, changed_flag,
			  success_flag, inc) = self.cache_dict[first_index]
		except KeyError: # probably caused by error in file system (dup)
			log.Log("Warning index %s missing from CCPP cache" %
					(first_index,),2)
			return
		del self.cache_dict[first_index]
		self.post_process(old_source_rorp, old_dest_rorp,
						  changed_flag, success_flag, inc)
		if self.dir_perms_list: self.reset_dir_perms(first_index)

	def post_process(self, source_rorp, dest_rorp, changed, success, inc):
		"""Post process source_rorp and dest_rorp.

		The point of this is to write statistics and metadata.

		changed will be true if the files have changed.  success will
		be true if the files have been successfully updated (this is
		always false for un-changed files).

		"""
		if Globals.preserve_hardlinks and source_rorp:
			if Hardlink.del_rorp(source_rorp):
				del self.inode_digest_dict[source_rorp.index]

		if not changed or success:
			if source_rorp: self.statfileobj.add_source_file(source_rorp)
			if dest_rorp: self.statfileobj.add_dest_file(dest_rorp)
		if success == 0: metadata_rorp = dest_rorp
		elif success == 1: metadata_rorp = source_rorp
		else: metadata_rorp = None # in case deleted because of ListError
		if success == 1 or success == 2: 
			self.statfileobj.add_changed(source_rorp, dest_rorp)

		if metadata_rorp and metadata_rorp.lstat():
			self.metawriter.write_object(metadata_rorp)
		if Globals.file_statistics:
			statistics.FileStats.update(source_rorp, dest_rorp, changed, inc)

	def reset_dir_perms(self, current_index):
		"""Reset the permissions of directories when we have left them"""
		dir_rp, perms = self.dir_perms_list[-1]
		dir_index = dir_rp.index
		if (current_index > dir_index and
			current_index[:len(dir_index)] != dir_index):
			dir_rp.chmod(perms) # out of directory, reset perms now

	def in_cache(self, index):
		"""Return true if given index is cached"""
		return self.cache_dict.has_key(index)

	def flag_success(self, index):
		"""Signal that the file with given index was updated successfully"""
		self.cache_dict[index][3] = 1

	def flag_deleted(self, index):
		"""Signal that the destination file was deleted"""
		self.cache_dict[index][3] = 2

	def flag_changed(self, index):
		"""Signal that the file with given index has changed"""
		self.cache_dict[index][2] = 1

	def set_inc(self, index, inc):
		"""Set the increment of the current file"""
		self.cache_dict[index][4] = inc

	def get_rorps(self, index):
		"""Retrieve (source_rorp, dest_rorp) from cache"""
		return self.cache_dict[index][:2]

	def get_source_rorp(self, index):
		"""Retrieve source_rorp with given index from cache"""
		assert index >= self.cache_indicies[0], \
			   ("CCPP index out of order: %s %s" %
				(repr(index), repr(self.cache_indicies[0])))
		return self.cache_dict[index][0]

	def get_mirror_rorp(self, index):
		"""Retrieve mirror_rorp with given index from cache"""
		return self.cache_dict[index][1]

	def update_hash(self, index, sha1sum):
		"""Update the source rorp's SHA1 hash"""
		self.get_source_rorp(index).set_sha1(sha1sum)

	def update_hardlink_hash(self, diff_rorp):
		"""Tag associated source_rorp with same hash diff_rorp points to"""
		orig_rorp = self.inode_digest_dict[diff_rorp.get_link_flag()]
		if orig_rorp.has_sha1():
			new_source_rorp = self.get_source_rorp(diff_rorp.index)
			new_source_rorp.set_sha1(orig_rorp.get_sha1())

	def close(self):
		"""Process the remaining elements in the cache"""
		while self.cache_indicies: self.shorten_cache()
		while self.dir_perms_list:
			dir_rp, perms = self.dir_perms_list.pop()
			dir_rp.chmod(perms)
		self.metawriter.close()
		metadata.ManagerObj.ConvertMetaToDiff()

		if Globals.print_statistics: statistics.print_active_stats()
		if Globals.file_statistics: statistics.FileStats.close()
		statistics.write_active_statfileobj()


class PatchITRB(rorpiter.ITRBranch):
	"""Patch an rpath with the given diff iters (use with IterTreeReducer)

	The main complication here involves directories.  We have to
	finish processing the directory after what's in the directory, as
	the directory may have inappropriate permissions to alter the
	contents or the dir's mtime could change as we change the
	contents.

	"""
	def __init__(self, basis_root_rp, CCPP):
		"""Set basis_root_rp, the base of the tree to be incremented"""
		self.basis_root_rp = basis_root_rp
		assert basis_root_rp.conn is Globals.local_connection
		self.statfileobj = (statistics.get_active_statfileobj() or
							statistics.StatFileObj())
		self.dir_replacement, self.dir_update = None, None
		self.cached_rp = None
		self.CCPP = CCPP
		self.error_handler = robust.get_error_handler("UpdateError")

	def get_rp_from_root(self, index):
		"""Return RPath by adding index to self.basis_root_rp"""
		if not self.cached_rp or self.cached_rp.index != index:
			self.cached_rp = self.basis_root_rp.new_index(index)
		return self.cached_rp

	def check_long_name(self, func, *args):
		"""Execute function, checking for ENAMETOOLONG error"""
		try: result = func(*args)
		except OSError, exc:
			if (errno.errorcode.has_key(exc[0]) and
				errno.errorcode[exc[0]] == 'ENAMETOOLONG'):
				self.error_handler(exc, args[0])
				return None
			else: raise
		return result

	def can_fast_process(self, index, diff_rorp):
		"""True if diff_rorp and mirror are not directories"""
		rp = self.check_long_name(self.get_rp_from_root, index)
		# filename too long error qualifies (hack)
		return not rp or (not diff_rorp.isdir() and not rp.isdir())

	def fast_process(self, index, diff_rorp):
		"""Patch base_rp with diff_rorp (case where neither is directory)"""
		rp = self.check_long_name(self.get_rp_from_root, index)
		if not rp: return
		tf = TempFile.new(rp)
		if self.patch_to_temp(rp, diff_rorp, tf):
			if tf.lstat():
				rpath.rename(tf, rp)
				self.CCPP.flag_success(index)
			elif rp.lstat():
				rp.delete()
				self.CCPP.flag_deleted(index)
		else: 
			tf.setdata()
			if tf.lstat(): tf.delete()

	def patch_to_temp(self, basis_rp, diff_rorp, new):
		"""Patch basis_rp, writing output in new, which doesn't exist yet

		Returns true if able to write new as desired, false if
		UpdateError or similar gets in the way.

		"""
		if diff_rorp.isflaglinked():
			self.patch_hardlink_to_temp(diff_rorp, new)
		elif diff_rorp.get_attached_filetype() == 'snapshot':
			if not self.patch_snapshot_to_temp(diff_rorp, new):
				return 0
		elif not self.patch_diff_to_temp(basis_rp, diff_rorp, new):
			return 0
		if new.lstat() and not diff_rorp.isflaglinked():
			rpath.copy_attribs(diff_rorp, new)
		return self.matches_cached_rorp(diff_rorp, new)

	def patch_hardlink_to_temp(self, diff_rorp, new):
		"""Hardlink diff_rorp to temp, update hash if necessary"""
		Hardlink.link_rp(diff_rorp, new, self.basis_root_rp)
		self.CCPP.update_hardlink_hash(diff_rorp)

	def patch_snapshot_to_temp(self, diff_rorp, new):
		"""Write diff_rorp to new, return true if successful"""
		if diff_rorp.isspecial():
			self.write_special(diff_rorp, new)
			rpath.copy_attribs(diff_rorp, new)
			return 1
		
		report = robust.check_common_error(self.error_handler, rpath.copy,
										   (diff_rorp, new))
		if isinstance(report, hash.Report):
			self.CCPP.update_hash(diff_rorp.index, report.sha1_digest)
			return 1
		return report != 0 # if == 0, error_handler caught something

	def patch_diff_to_temp(self, basis_rp, diff_rorp, new):
		"""Apply diff_rorp to basis_rp, write output in new"""
		assert diff_rorp.get_attached_filetype() == 'diff'
		report = robust.check_common_error(self.error_handler,
			      Rdiff.patch_local, (basis_rp, diff_rorp, new))
		if isinstance(report, hash.Report):
			self.CCPP.update_hash(diff_rorp.index, report.sha1_digest)
			return 1
		return report != 0 # if report == 0, error

	def matches_cached_rorp(self, diff_rorp, new_rp):
		"""Return true if new_rp matches cached src rorp

		This is a final check to make sure the temp file just written
		matches the stats which we got earlier.  If it doesn't it
		could confuse the regress operation.  This is only necessary
		for regular files.

		"""
		if not new_rp.isreg(): return 1
		cached_rorp = self.CCPP.get_source_rorp(diff_rorp.index)
		if cached_rorp and cached_rorp.equal_loose(new_rp): return 1
		log.ErrorLog.write_if_open("UpdateError", diff_rorp, "Updated mirror "
					  "temp file %s does not match source" % (new_rp.path,))
		return 0

	def write_special(self, diff_rorp, new):
		"""Write diff_rorp (which holds special file) to new"""
		eh = robust.get_error_handler("SpecialFileError")
		if robust.check_common_error(eh, rpath.copy, (diff_rorp, new)) == 0:
			new.setdata()
			if new.lstat(): new.delete()
			new.touch()

	def start_process(self, index, diff_rorp):
		"""Start processing directory - record information for later"""
		base_rp = self.base_rp = self.get_rp_from_root(index)
		assert diff_rorp.isdir() or base_rp.isdir() or not base_rp.index
		if diff_rorp.isdir(): self.prepare_dir(diff_rorp, base_rp)
		elif self.set_dir_replacement(diff_rorp, base_rp):
			self.CCPP.flag_success(index)

	def set_dir_replacement(self, diff_rorp, base_rp):
		"""Set self.dir_replacement, which holds data until done with dir

		This is used when base_rp is a dir, and diff_rorp is not.
		Returns 1 for success or 0 for failure

		"""
		assert diff_rorp.get_attached_filetype() == 'snapshot'
		self.dir_replacement = TempFile.new(base_rp)
		if not self.patch_to_temp(None, diff_rorp, self.dir_replacement):
			if self.dir_replacement.lstat(): self.dir_replacement.delete()
			# Was an error, so now restore original directory
			rpath.copy_with_attribs(self.CCPP.get_mirror_rorp(diff_rorp.index),
									self.dir_replacement)
			return 0
		else: return 1

	def prepare_dir(self, diff_rorp, base_rp):
		"""Prepare base_rp to turn into a directory"""
		self.dir_update = diff_rorp.getRORPath() # make copy in case changes
		if not base_rp.isdir():
			if base_rp.lstat(): base_rp.delete()
			base_rp.mkdir()
			self.CCPP.flag_success(diff_rorp.index)
		else: # maybe no change, so query CCPP before tagging success
			if self.CCPP.in_cache(diff_rorp.index):
				self.CCPP.flag_success(diff_rorp.index)

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
		rp = self.check_long_name(self.get_rp_from_root, index)
		if not rp: return
		tf = TempFile.new(rp)
		if self.patch_to_temp(rp, diff_rorp, tf):
			inc = self.check_long_name(increment.Increment,
									   tf, rp, self.get_incrp(index))
			if inc is not None:
				self.CCPP.set_inc(index, inc)
				if inc.isreg():
					inc.fsync_with_dir() # Write inc before rp changed
				if tf.lstat():
					rpath.rename(tf, rp)
					self.CCPP.flag_success(index)
				elif rp.lstat():
					rp.delete()
					self.CCPP.flag_deleted(index)
				return # normal return, otherwise error occurred
		tf.setdata()
		if tf.lstat(): tf.delete()

	def start_process(self, index, diff_rorp):
		"""Start processing directory"""
		base_rp = self.base_rp = self.get_rp_from_root(index)
		assert diff_rorp.isdir() or base_rp.isdir()
		if diff_rorp.isdir():
			inc = self.check_long_name(increment.Increment,
								 diff_rorp, base_rp, self.get_incrp(index))
			if inc and inc.isreg():
				inc.fsync_with_dir() # must write inc before rp changed
			self.prepare_dir(diff_rorp, base_rp)
		elif self.set_dir_replacement(diff_rorp, base_rp):
			inc = self.check_long_name(increment.Increment,
						self.dir_replacement, base_rp, self.get_incrp(index))
			if inc:
				self.CCPP.set_inc(index, inc)
				self.CCPP.flag_success(index)


