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

"""Read increment files and restore to original"""

from __future__ import generators
import tempfile, os, cStringIO
import Globals, Time, Rdiff, Hardlink, rorpiter, selection, rpath, \
	   log, static, robust, metadata, statistics, TempFile, eas_acls


# This should be set to selection.Select objects over the source and
# mirror directories respectively.
_select_source = None
_select_mirror = None

# This will be set to the time of the current mirror
_mirror_time = None
# This will be set to the exact time to restore to (not restore_to_time)
_rest_time = None


class RestoreError(Exception): pass

def Restore(mirror_rp, inc_rpath, target, restore_to_time):
	"""Recursively restore mirror and inc_rpath to target at rest_time"""
	MirrorS = mirror_rp.conn.restore.MirrorStruct
	TargetS = target.conn.restore.TargetStruct

	MirrorS.set_mirror_and_rest_times(restore_to_time)
	MirrorS.initialize_rf_cache(mirror_rp, inc_rpath)
	target_iter = TargetS.get_initial_iter(target)
	diff_iter = MirrorS.get_diffs(target_iter)
	TargetS.patch(target, diff_iter)
	MirrorS.close_rf_cache()

def get_inclist(inc_rpath):
	"""Returns increments with given base"""
	dirname, basename = inc_rpath.dirsplit()
	parent_dir = inc_rpath.__class__(inc_rpath.conn, dirname, ())
	if not parent_dir.isdir(): return [] # inc directory not created yet
	index = inc_rpath.index

	inc_list = []
	for filename in parent_dir.listdir():
		inc = parent_dir.append(filename)
		if inc.isincfile() and inc.getincbase_str() == basename:
			inc_list.append(inc)
	return inc_list

def ListChangedSince(mirror_rp, inc_rp, restore_to_time):
	"""List the changed files under mirror_rp since rest time

	Notice the output is an iterator of RORPs.  We do this because we
	want to give the remote connection the data in buffered
	increments, and this is done automatically for rorp iterators.
	Encode the lines in the first element of the rorp's index.

	"""
	assert mirror_rp.conn is Globals.local_connection, "Run locally only"
	MirrorStruct.set_mirror_and_rest_times(restore_to_time)
	MirrorStruct.initialize_rf_cache(mirror_rp, inc_rp)

	old_iter = MirrorStruct.get_mirror_rorp_iter(_rest_time, 1)
	cur_iter = MirrorStruct.get_mirror_rorp_iter(_mirror_time, 1)
	collated = rorpiter.Collate2Iters(old_iter, cur_iter)
	for old_rorp, cur_rorp in collated:
		if not old_rorp: change = "new"
		elif not cur_rorp: change = "deleted"
		elif old_rorp == cur_rorp: continue
		else: change = "changed"
		path_desc = (old_rorp and old_rorp.get_indexpath() or
					 cur_rorp.get_indexpath())
		yield rpath.RORPath(("%-7s %s" % (change, path_desc),))
	MirrorStruct.close_rf_cache()

def ListAtTime(mirror_rp, inc_rp, time):
	"""List the files in archive at the given time

	Output is a RORP Iterator with info in index.  See ListChangedSince.

	"""
	assert mirror_rp.conn is Globals.local_connection, "Run locally only"
	MirrorStruct.set_mirror_and_rest_times(time)
	MirrorStruct.initialize_rf_cache(mirror_rp, inc_rp)

	old_iter = MirrorStruct.get_mirror_rorp_iter(_rest_time, 1)
	for rorp in old_iter: yield rorp
	

class MirrorStruct:
	"""Hold functions to be run on the mirror side"""
	_select = None # If selection command line arguments given, use Select here
	def set_mirror_and_rest_times(cls, restore_to_time):
		"""Set global variabels _mirror_time and _rest_time on mirror conn"""
		global _mirror_time, _rest_time
		_mirror_time = cls.get_mirror_time()
		_rest_time = cls.get_rest_time(restore_to_time)

	def get_mirror_time(cls):
		"""Return time (in seconds) of latest mirror"""
		cur_mirror_incs = get_inclist(Globals.rbdir.append("current_mirror"))
		if not cur_mirror_incs:
			log.Log.FatalError("Could not get time of current mirror")
		elif len(cur_mirror_incs) > 1:
			log.Log("Warning, two different times for current mirror found", 2)
		return cur_mirror_incs[0].getinctime()

	def get_rest_time(cls, restore_to_time):
		"""Return older time, if restore_to_time is in between two inc times

		There is a slightly tricky reason for doing this: The rest of the
		code just ignores increments that are older than restore_to_time.
		But sometimes we want to consider the very next increment older
		than rest time, because rest_time will be between two increments,
		and what was actually on the mirror side will correspond to the
		older one.

		So here we assume all rdiff-backup events were recorded in
		"increments" increments, and if it's in-between we pick the
		older one here.

		"""
		inctimes = cls.get_increment_times()
		older_times = filter(lambda time: time <= restore_to_time, inctimes)
		if older_times: return max(older_times)
		else: # restore time older than oldest increment, just return that
			return min(inctimes)

	def get_increment_times(cls, rp = None):
		"""Return list of times of backups, including current mirror"""
		if not _mirror_time: return_list = [cls.get_mirror_time()]
		else: return_list = [_mirror_time]
		if not rp or not rp.index: rp = Globals.rbdir.append("increments")
		for inc in get_inclist(rp): return_list.append(inc.getinctime())
		return return_list

	def initialize_rf_cache(cls, mirror_base, inc_base):
		"""Set cls.rf_cache to CachedRF object"""
		inc_list = get_inclist(inc_base)
		rf = RestoreFile(mirror_base, inc_base, get_inclist(inc_base))
		cls.mirror_base, cls.inc_base = mirror_base, inc_base
		cls.root_rf = rf
		cls.rf_cache = CachedRF(rf)

	def close_rf_cache(cls):
		"""Run anything remaining on CachedRF object"""
		cls.rf_cache.close()

	def get_mirror_rorp_iter(cls, rest_time = None, require_metadata = None):
		"""Return iter of mirror rps at given restore time

		Usually we can use the metadata file, but if this is
		unavailable, we may have to build it from scratch.

		If the cls._select object is set, use it to filter out the
		unwanted files from the metadata_iter.

		"""
		if rest_time is None: rest_time = _rest_time

		rorp_iter = eas_acls.GetCombinedMetadataIter(
			Globals.rbdir, rest_time, restrict_index = cls.mirror_base.index,
			acls = Globals.write_acls, eas = Globals.write_eas)
		if not rorp_iter:
			if require_metadata:
				log.Log.FatalError("Mirror metadata not found")
			log.Log("Warning: Mirror metadata not found, "
					"reading from directory", 2)
			rorp_iter = cls.get_rorp_iter_from_rf(cls.root_rf)

		if cls._select:
			rorp_iter = selection.FilterIter(cls._select, rorp_iter)
		return rorp_iter

	def set_mirror_select(cls, target_rp, select_opts, *filelists):
		"""Initialize the mirror selection object"""
		assert select_opts, "If no selection options, don't use selector"
		cls._select = selection.Select(target_rp)
		cls._select.ParseArgs(select_opts, filelists)

	def get_rorp_iter_from_rf(cls, rf):
		"""Recursively yield mirror rorps from rf"""
		rorp = rf.get_attribs()
		yield rorp
		if rorp.isdir():
			for sub_rf in rf.yield_sub_rfs():
				for attribs in cls.get_rorp_iter_from_rf(sub_rf):
					yield attribs

	def subtract_indicies(cls, index, rorp_iter):
		"""Subtract index from index of each rorp in rorp_iter

		subtract_indicies and add_indicies are necessary because we
		may not be restoring from the root index.

		"""
		if index == (): return rorp_iter
		def get_iter():
			for rorp in rorp_iter:
				assert rorp.index[:len(index)] == index, (rorp.index, index)
				rorp.index = rorp.index[len(index):]
				yield rorp
		return get_iter()

	def get_diffs(cls, target_iter):
		"""Given rorp iter of target files, return diffs

		Here the target_iter doesn't contain any actual data, just
		attribute listings.  Thus any diffs we generate will be
		snapshots.

		"""
		mir_iter = cls.subtract_indicies(cls.mirror_base.index,
										 cls.get_mirror_rorp_iter())
		collated = rorpiter.Collate2Iters(mir_iter, target_iter)
		return cls.get_diffs_from_collated(collated)

	def get_diffs_from_collated(cls, collated):
		"""Get diff iterator from collated"""
		for mir_rorp, target_rorp in collated:
			if Globals.preserve_hardlinks and mir_rorp:
				Hardlink.add_rorp(mir_rorp, target_rorp)
			if (not target_rorp or not mir_rorp or
				not mir_rorp == target_rorp or
				(Globals.preserve_hardlinks and not
				 Hardlink.rorp_eq(mir_rorp, target_rorp))):
				diff = cls.get_diff(mir_rorp, target_rorp)
			else: diff = None
			if Globals.preserve_hardlinks and mir_rorp:
				Hardlink.del_rorp(mir_rorp)
			if diff: yield diff

	def get_diff(cls, mir_rorp, target_rorp):
		"""Get a diff for mir_rorp at time"""
		if not mir_rorp: mir_rorp = rpath.RORPath(target_rorp.index)
		elif Globals.preserve_hardlinks and Hardlink.islinked(mir_rorp):
			mir_rorp.flaglinked(Hardlink.get_link_index(mir_rorp))
		elif mir_rorp.isreg():
			expanded_index = cls.mirror_base.index + mir_rorp.index
			mir_rorp.setfile(cls.rf_cache.get_fp(expanded_index))
		mir_rorp.set_attached_filetype('snapshot')
		return mir_rorp

static.MakeClass(MirrorStruct)


class TargetStruct:
	"""Hold functions to be run on the target side when restoring"""
	def get_initial_iter(cls, target):
		"""Return a selection object iterating the rorpaths in target"""
		return selection.Select(target).set_iter()

	def patch(cls, target, diff_iter):
		"""Patch target with the diffs from the mirror side

		This function and the associated ITRB is similar to the
		patching code in backup.py, but they have different error
		correction requirements, so it seemed easier to just repeat it
		all in this module.

		"""
		ITR = rorpiter.IterTreeReducer(PatchITRB, [target])
		for diff in rorpiter.FillInIter(diff_iter, target):
			log.Log("Processing changed file " + diff.get_indexpath(), 5)
			ITR(diff.index, diff)
		ITR.Finish()
		target.setdata()

static.MakeClass(TargetStruct)


class CachedRF:
	"""Store RestoreFile objects until they are needed

	The code above would like to pretend it has random access to RFs,
	making one for a particular index at will.  However, in general
	this involves listing and filtering a directory, which can get
	expensive.

	Thus, when a CachedRF retrieves an RestoreFile, it creates all the
	RFs of that directory at the same time, and doesn't have to
	recalculate.  It assumes the indicies will be in order, so the
	cache is deleted if a later index is requested.

	"""
	def __init__(self, root_rf):
		"""Initialize CachedRF, self.rf_list variable"""
		self.root_rf = root_rf
		self.rf_list = [] # list should filled in index order
		if Globals.process_uid != 0:
			self.perm_changer = PermissionChanger(root_rf.mirror_rp)

	def list_rfs_in_cache(self, index):
		"""Used for debugging, return indicies of cache rfs for printing"""
		s1 = "-------- Cached RF for %s -------" % (index,)
		s2 = " ".join([str(rf.index) for rf in self.rf_list])
		s3 = "--------------------------"
		return "\n".join((s1, s2, s3))

	def get_rf(self, index):
		"""Return RestoreFile of given index, or None"""
		while 1:
			if not self.rf_list:
				if not self.add_rfs(index): return None
			rf = self.rf_list[0]
			if rf.index == index:
				if Globals.process_uid != 0: self.perm_changer(rf.mirror_rp)
				return rf
			elif rf.index > index:
				# Try to add earlier indicies.  But if first is
				# already from same directory, or we can't find any
				# from that directory, then we know it can't be added.
				if (index[:-1] == rf.index[:-1] or not
					self.add_rfs(index)): return None
			else: del self.rf_list[0]

	def get_fp(self, index):
		"""Return the file object (for reading) of given index"""
		rf = self.get_rf(index)
		if not rf:
			log.Log("""Error: Unable to retrieve data for file %s!
The cause is probably data loss from the destination directory.""" %
					(index and "/".join(index) or '.',), 2)
			return cStringIO.StringIO('')
		return self.get_rf(index).get_restore_fp()

	def add_rfs(self, index):
		"""Given index, add the rfs in that same directory

		Returns false if no rfs are available, which usually indicates
		an error.

		"""
		if not index: return self.root_rf
		parent_index = index[:-1]
		temp_rf = RestoreFile(self.root_rf.mirror_rp.new_index(parent_index),
							  self.root_rf.inc_rp.new_index(parent_index), [])
		if Globals.process_uid != 0: self.perm_changer(temp_rf.mirror_rp)
		new_rfs = list(temp_rf.yield_sub_rfs())
		if not new_rfs:
			log.Log("Warning: No RFs added for index %s" % (index,), 2)
			return 0
		self.rf_list[0:0] = new_rfs
		return 1

	def close(self):
		"""Finish remaining rps in PermissionChanger"""
		if Globals.process_uid != 0: self.perm_changer.finish()


class RestoreFile:
	"""Hold data about a single mirror file and its related increments

	self.relevant_incs will be set to a list of increments that matter
	for restoring a regular file.  If the patches are to mirror_rp, it
	will be the first element in self.relevant.incs

	"""
	def __init__(self, mirror_rp, inc_rp, inc_list):
		assert mirror_rp.index == inc_rp.index, \
			   ("mirror and inc indicies don't match: %s %s" %
				(mirror_rp.get_indexpath(), inc_rp.get_indexpath()))
		self.index = mirror_rp.index
		self.mirror_rp = mirror_rp
		self.inc_rp, self.inc_list = inc_rp, inc_list
		self.set_relevant_incs()

	def relevant_incs_string(self):
		"""Return printable string of relevant incs, used for debugging"""
		l = ["---- Relevant incs for %s" % ("/".join(self.index),)]
		l.extend(["%s %s %s" % (inc.getinctype(), inc.lstat(), inc.path)
				  for inc in self.relevant_incs])
		l.append("--------------------------------")
		return "\n".join(l)

	def set_relevant_incs(self):
		"""Set self.relevant_incs to increments that matter for restoring

		relevant_incs is sorted newest first.  If mirror_rp matters,
		it will be (first) in relevant_incs.

		"""
		self.mirror_rp.inc_type = 'snapshot'
		self.mirror_rp.inc_compressed = 0
		if not self.inc_list or _rest_time >= _mirror_time:
			self.relevant_incs = [self.mirror_rp]
			return

		newer_incs = self.get_newer_incs()
		i = 0
		while(i < len(newer_incs)):
			# Only diff type increments require later versions
			if newer_incs[i].getinctype() != "diff": break
			i = i+1
		self.relevant_incs = newer_incs[:i+1]
		if (not self.relevant_incs or
			self.relevant_incs[-1].getinctype() == "diff"):
			self.relevant_incs.append(self.mirror_rp)
		self.relevant_incs.reverse() # return in reversed order
		
	def get_newer_incs(self):
		"""Return list of newer incs sorted by time (increasing)

		Also discard increments older than rest_time (rest_time we are
		assuming is the exact time rdiff-backup was run, so no need to
		consider the next oldest increment or any of that)

		"""
		incpairs = []
		for inc in self.inc_list:
			time = inc.getinctime()
			if time >= _rest_time: incpairs.append((time, inc))
		incpairs.sort()
		return [pair[1] for pair in incpairs]

	def get_attribs(self):
		"""Return RORP with restored attributes, but no data

		This should only be necessary if the metadata file is lost for
		some reason.  Otherwise the file provides all data.  The size
		will be wrong here, because the attribs may be taken from
		diff.

		"""
		last_inc = self.relevant_incs[-1]
		if last_inc.getinctype() == 'missing': return rpath.RORPath(self.index)

		rorp = last_inc.getRORPath()
		rorp.index = self.index
		if last_inc.getinctype() == 'dir': rorp.data['type'] = 'dir'
		return rorp

	def get_restore_fp(self):
		"""Return file object of restored data"""
		if not self.relevant_incs[-1].isreg():
			log.Log("""Warning: Could not restore file %s!

A regular file was indicated by the metadata, but could not be
constructed from existing increments because last increment had type
%s.  Instead of the actual file's data, an empty length file will be
created.  This error is probably caused by data loss in the
rdiff-backup destination directory, or a bug in rdiff-backup""" %
					(self.mirror_rp.path, self.relevant_incs[-1].lstat()), 2)
			return cStringIO.StringIO('')
		current_fp = self.get_first_fp()
		for inc_diff in self.relevant_incs[1:]:
			log.Log("Applying patch %s" % (inc_diff.get_indexpath(),), 7)
			assert inc_diff.getinctype() == 'diff'
			delta_fp = inc_diff.open("rb", inc_diff.isinccompressed())
			new_fp = tempfile.TemporaryFile()
			Rdiff.write_patched_fp(current_fp, delta_fp, new_fp)
			new_fp.seek(0)
			current_fp = new_fp
		return current_fp

	def get_first_fp(self):
		"""Return first file object from relevant inc list"""
		first_inc = self.relevant_incs[0]
		assert first_inc.getinctype() == 'snapshot'
		if not first_inc.isinccompressed(): return first_inc.open("rb")

		# current_fp must be a real (uncompressed) file
		current_fp = tempfile.TemporaryFile()
		fp = first_inc.open("rb", compress = 1)
		rpath.copyfileobj(fp, current_fp)
		assert not fp.close()
		current_fp.seek(0)
		return current_fp

	def yield_sub_rfs(self):
		"""Return RestoreFiles under current RestoreFile (which is dir)"""
		if not self.mirror_rp.isdir() and not self.inc_rp.isdir():
			log.Log("""Warning: directory %s seems to be missing from backup!

This is probably due to files being deleted manually from the
rdiff-backup destination directory.  In general you shouldn't do this,
as data loss may result.\n""" % (self.mirror_rp.get_indexpath(),), 2)
			return
		if self.mirror_rp.isdir():
			mirror_iter = self.yield_mirrorrps(self.mirror_rp)
		else: mirror_iter = iter([])
		if self.inc_rp.isdir():
			inc_pair_iter = self.yield_inc_complexes(self.inc_rp)
		else: inc_pair_iter = iter([])
		collated = rorpiter.Collate2Iters(mirror_iter, inc_pair_iter)

		for mirror_rp, inc_pair in collated:
			if not inc_pair:
				inc_rp = self.inc_rp.new_index(mirror_rp.index)
				inc_list = []
			else: inc_rp, inc_list = inc_pair
			if not mirror_rp:
				mirror_rp = self.mirror_rp.new_index(inc_rp.index)
			yield self.__class__(mirror_rp, inc_rp, inc_list)

	def yield_mirrorrps(self, mirrorrp):
		"""Yield mirrorrps underneath given mirrorrp"""
		assert mirrorrp.isdir()
		for filename in robust.listrp(mirrorrp):
			rp = mirrorrp.append(filename)
			if rp.index != ('rdiff-backup-data',): yield rp

	def yield_inc_complexes(self, inc_rpath):
		"""Yield (sub_inc_rpath, inc_list) IndexedTuples from given inc_rpath

		Finds pairs under directory inc_rpath.  sub_inc_rpath will just be
		the prefix rp, while the rps in inc_list should actually exist.

		"""
		if not inc_rpath.isdir(): return
		inc_dict = {} # dictionary of basenames:IndexedTuples(index, inc_list)
		dirlist = robust.listrp(inc_rpath)

		def affirm_dict_indexed(basename):
			"""Make sure the rid dictionary has given basename as key"""
			if not inc_dict.has_key(basename):
				sub_inc_rp = inc_rpath.append(basename)
				inc_dict[basename] = rorpiter.IndexedTuple(sub_inc_rp.index,
														   (sub_inc_rp, []))

		def add_to_dict(filename):
			"""Add filename to the inc tuple dictionary"""
			rp = inc_rpath.append(filename)
			if rp.isincfile() and rp.getinctype() != 'data':
				basename = rp.getincbase_str()
				affirm_dict_indexed(basename)
				inc_dict[basename][1].append(rp)
			elif rp.isdir(): affirm_dict_indexed(filename)

		for filename in dirlist: add_to_dict(filename)
		keys = inc_dict.keys()
		keys.sort()
		for key in keys: yield inc_dict[key]


class PatchITRB(rorpiter.ITRBranch):
	"""Patch an rpath with the given diff iters (use with IterTreeReducer)

	The main complication here involves directories.  We have to
	finish processing the directory after what's in the directory, as
	the directory may have inappropriate permissions to alter the
	contents or the dir's mtime could change as we change the
	contents.

	This code was originally taken from backup.py.  However, because
	of different error correction requirements, it is repeated here.

	"""
	def __init__(self, basis_root_rp):
		"""Set basis_root_rp, the base of the tree to be incremented"""
		self.basis_root_rp = basis_root_rp
		assert basis_root_rp.conn is Globals.local_connection
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


class PermissionChanger:
	"""Change the permission of mirror files and directories

	The problem is that mirror files and directories may need their
	permissions changed in order to be read and listed, and then
	changed back when we are done.  This class hooks into the CachedRF
	object to know when an rp is needed.

	"""
	def __init__(self, root_rp):
		self.root_rp = root_rp
		self.current_index = ()
		# Below is a list of (index, rp, old_perm) triples in reverse
		# order that need clearing
		self.open_index_list = []

	def __call__(self, rp):
		"""Given rpath, change permissions up and including rp"""
		index, old_index = rp.index, self.current_index
		self.current_index = index
		if not index or index == old_index: return
		assert index > old_index, (index, old_index)
		self.restore_old(rp, index)
		self.add_new(rp, old_index, index)

	def restore_old(self, rp, index):
		"""Restore permissions for indicies we are done with"""
		while self.open_index_list:
			old_index, old_rp, old_perms = self.open_index_list[0]
			if index[:len(old_index)] > old_index: old_rp.chmod(old_perms)
			else: break
			del self.open_index_list[0]

	def add_new(self, rp, old_index, index):
		"""Change permissions of directories between old_index and index"""
		for rp in self.get_new_rp_list(rp, old_index, index):
			if ((rp.isreg() and not rp.readable()) or
				(rp.isdir() and not rp.hasfullperms())):
				old_perms = rp.getperms()
				self.open_index_list.insert(0, (index, rp, old_perms))
				if rp.isreg(): rp.chmod(0400 | old_perms)
				else: rp.chmod(0700 | old_perms)

	def get_new_rp_list(self, rp, old_index, index):
		"""Return list of new rp's between old_index and index"""
		for i in range(len(index)-1, -1, -1):
			if old_index[:i] == index[:i]:
				common_prefix_len = i
				break
		else: assert 0

		new_rps = []
		for total_len in range(common_prefix_len+1, len(index)):
			new_rps.append(self.root_rp.new_index(index[:total_len]))
		new_rps.append(rp)
		return new_rps

	def finish(self):
		"""Restore any remaining rps"""
		for index, rp, perms in self.open_index_list: rp.chmod(perms)
