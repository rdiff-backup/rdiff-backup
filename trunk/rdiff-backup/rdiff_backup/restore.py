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

"""Read increment files and restore to original"""

from __future__ import generators
import tempfile, os
import Globals, Time, Rdiff, Hardlink, rorpiter, selection, rpath, \
	   log, backup, static, robust, metadata


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
	"""List the changed files under mirror_rp since rest time"""
	MirrorS = mirror_rp.conn.restore.MirrorStruct
	MirrorS.set_mirror_and_rest_times(restore_to_time)
	MirrorS.initialize_rf_cache(mirror_rp, inc_rp)

	cur_iter = MirrorS.get_mirror_rorp_iter(_mirror_time, 1)
	old_iter = MirrorS.get_mirror_rorp_iter(_rest_time, 1)
	collated = rorpiter.Collate2Iters(old_iter, cur_iter)
	for old_rorp, cur_rorp in collated:
		if not old_rorp: change = "new"
		elif not cur_rorp: change = "deleted"
		elif old_rorp == cur_rorp: continue
		else: change = "changed"
		path_desc = (old_rorp and old_rorp.get_indexpath() or
					 cur_rorp.get_indexpath())
		print "%-7s %s" % (change, path_desc)


class MirrorStruct:
	"""Hold functions to be run on the mirror side"""
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
		global _rest_time
		base_incs = get_inclist(Globals.rbdir.append("increments"))
		if not base_incs: return _mirror_time
		inctimes = [inc.getinctime() for inc in base_incs]
		inctimes.append(_mirror_time)
		older_times = filter(lambda time: time <= restore_to_time, inctimes)
		if older_times: return max(older_times)
		else: # restore time older than oldest increment, just return that
			return min(inctimes)

	def initialize_rf_cache(cls, mirror_base, inc_base):
		"""Set cls.rf_cache to CachedRF object"""
		inc_list = get_inclist(inc_base)
		rf = RestoreFile(mirror_base, inc_base, get_inclist(inc_base))
		cls.mirror_base, cls.inc_base = mirror_base, inc_base
		cls.root_rf = rf
		cls.rf_cache = CachedRF(rf)

	def get_mirror_rorp_iter(cls, rest_time = None, require_metadata = None):
		"""Return iter of mirror rps at given restore time

		Usually we can use the metadata file, but if this is
		unavailable, we may have to build it from scratch.

		"""
		if rest_time is None: rest_time = _rest_time
		metadata_iter = metadata.GetMetadata_at_time(Globals.rbdir,
				 rest_time, restrict_index = cls.mirror_base.index)
		if metadata_iter: return metadata_iter
		if require_metadata: log.Log.FatalError("Mirror metadata not found")
		log.Log("Warning: Mirror metadata not found, "
				"reading from directory", 2)
		return cls.get_rorp_iter_from_rf(cls.root_rf)

	def get_rorp_iter_from_rf(cls, rf):
		"""Recursively yield mirror rorps from rf"""
		rorp = rf.get_attribs()
		yield rorp
		if rorp.isdir():
			for sub_rf in rf.yield_sub_rfs():
				for rorp in yield_attribs(sub_rf): yield rorp

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
			if Globals.preserve_hardlinks:
				if mir_rorp: Hardlink.add_rorp(mir_rorp, source = 1)
				if target_rorp: Hardlink.add_rorp(target_rorp, source = 0)

			if (not target_rorp or not mir_rorp or
				not mir_rorp == target_rorp or
				(Globals.preserve_hardlinks and not
				 Hardlink.rorp_eq(mir_rorp, target_rorp))):
				yield cls.get_diff(mir_rorp, target_rorp)

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

		This function was already written for use when backing up, so
		just use that.

		"""
		backup.DestinationStruct.patch(target, diff_iter)

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

	def list_rfs_in_cache(self, index):
		"""Used for debugging, return indicies of cache rfs for printing"""
		s1 = "-------- Cached RF for %s -------" % (index,)
		s2 = " ".join([str(rf.index) for rf in self.rf_list])
		s3 = "--------------------------"
		return "\n".join((s1, s2, s3))

	def get_rf(self, index):
		"""Return RestoreFile of given index"""
		while 1:
			if not self.rf_list: self.add_rfs(index)
			rf = self.rf_list.pop(0)
			if rf.index < index: continue
			elif rf.index == index: return rf
			self.rf_list.insert(0, rf)
			self.add_rfs(index)

	def get_fp(self, index):
		"""Return the file object (for reading) of given index"""
		return self.get_rf(index).get_restore_fp()

	def add_rfs(self, index):
		"""Given index, add the rfs in that same directory"""
		if not index: return self.root_rf
		parent_index = index[:-1]
		temp_rf = RestoreFile(self.root_rf.mirror_rp.new_index(parent_index),
							  self.root_rf.inc_rp.new_index(parent_index), [])
		new_rfs = list(temp_rf.yield_sub_rfs())
		assert new_rfs, "No RFs added for index %s" % index
		self.rf_list[0:0] = new_rfs

class RestoreFile:
	"""Hold data about a single mirror file and its related increments

	self.relevant_incs will be set to a list of increments that matter
	for restoring a regular file.  If the patches are to mirror_rp, it
	will be the first element in self.relevant.incs

	"""
	def __init__(self, mirror_rp, inc_rp, inc_list):
		assert mirror_rp.index == inc_rp.index, (mirror_rp, inc_rp)
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
		assert self.relevant_incs[-1].isreg(), "Not a regular file"
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
		assert self.mirror_rp.isdir() or self.inc_rp.isdir()
		mirror_iter = self.yield_mirrorrps(self.mirror_rp)
		inc_pair_iter = self.yield_inc_complexes(self.inc_rp)
		collated = rorpiter.Collate2Iters(mirror_iter, inc_pair_iter)

		for mirror_rp, inc_pair in collated:
			if not inc_pair:
				inc_rp = self.inc_rp.new_index(mirror_rp.index)
				inc_list = []
			else: inc_rp, inc_list = inc_pair
			if not mirror_rp:
				mirror_rp = self.mirror_rp.new_index(inc_rp.index)
			yield RestoreFile(mirror_rp, inc_rp, inc_list)

	def yield_mirrorrps(self, mirrorrp):
		"""Yield mirrorrps underneath given mirrorrp"""
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
