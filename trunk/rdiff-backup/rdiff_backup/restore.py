from __future__ import generators
execfile("increment.py")
import tempfile

#######################################################################
#
# restore - Read increment files and restore to original
#

class RestoreError(Exception): pass

class Restore:
	def Restore(inc_rpath, mirror, target, rest_time):
		"""Recursively restore inc_rpath and mirror to target at rest_time

		Like restore_recusive below, but with a more friendly
		interface (it converts to DSRPaths if necessary, finds the inc
		files with the appropriate base, and makes rid).

		rest_time is the time in seconds to restore to;

		inc_rpath should not be the name of an increment file, but the
		increment file shorn of its suffixes and thus should have the
		same index as mirror.

		"""
		if not isinstance(mirror, DSRPath):
			mirror = DSRPath(source = 1, mirror)
		if not isinstance(target, DSRPath):
			target = DSRPath(source = None, target)

		dirname, basename = inc_rpath.dirsplit()
		parent_dir = RPath(inc_rpath.conn, dirname, ())
		index = inc_rpath.index

		if inc_rpath.index:
			get_inc_ext = lambda filename: \
						  RPath(inc_rpath.conn, inc_rpath.base,
								inc_rpath.index[:-1] + (filename,))
		else: get_inc_ext = lambda filename: \
							RPath(inc_rpath.conn, os.join(dirname, filename))

		inc_list = []
		for filename in parent_dir.listdir():
			inc = get_inc_ext(filename)
			if inc.getincbase_str() == basename: inc_list.append(inc)

		rid = RestoreIncrementData(index, inc_rpath, inc_list)
		rid.sortincseq(rest_time)
		Restore.restore_recursive(index, mirror, rid, target, rest_time)

	def restore_recursive(index, mirror, rid, target, time):
		"""Recursive restore function.

		rid is a RestoreIncrementData object whose inclist is already
		sortedincseq'd, and target is the dsrp to restore to.

		Note that target may have a different index than mirror and
		rid, because we may be restoring a file whose index is, say
		('foo','bar') to a target whose path does not contain
		"foo/bar".

		"""
		assert isinstance(mirror, DSRPath) and isinstance(target, DSRPath)
		assert mirror.index == rid.index

		mirror_finalizer = DestructiveSteppingFinalizer()
		target_finalizer = DestructiveSteppingFinalizer()
		for rcd in Restore.yield_rcds(rid.index, mirror, rid, target, time):
			rcd.RestoreFile()
			if rcd.mirror: mirror_finalizer(rcd.mirror)
			target_finalizer(rcd.target)
		target_finalizer.Finish()
		mirror_finalizer.Finish()

	def yield_rcds(index, mirrorrp, rid, target, rest_time):
		"""Iterate RestoreCombinedData objects starting with given args

		rid is a RestoreCombinedData object.  target is an rpath where
		the created file should go.

		In this case the "mirror" directory is treated as the source,
		and we are actually copying stuff onto what Select considers
		the source directory.

		"""
		select_result = Globals.select_mirror.Select(target)
		if select_result == 0: return

		if mirrorrp and (not Globals.select_source.Select(mirrorrp) or
						 DestructiveStepping.initialize(mirrorrp, None)):
			mirrorrp = None
		rcd = RestoreCombinedData(rid, mirrorrp, target)

		if mirrorrp and mirrorrp.isdir() or rid and rid.inc_rpath.isdir():
			sub_rcds = Restore.yield_sub_rcds(index, mirrorrp, rid,
											  target, rest_time)
		else: sub_rcds = None

		if select_result == 1:
			yield rcd
			if sub_rcds:
				for sub_rcd in sub_rcds: yield sub_rcd
		elif select_result == 2:
			if sub_rcds:
				try: first = sub_rcds.next()
				except StopIteration: return # no tuples found inside, skip
				yield rcd
				yield first
				for sub_rcd in sub_rcds: yield sub_rcd

	def yield_collated_tuples_dir(index, mirrorrp, rid, target, rest_time):
		"""Yield collated tuples from inside given args"""
		if not Restore.check_dir_exists(mirrorrp, inc_tup): return
		mirror_iter = Restore.yield_mirrorrps(mirrorrp)
		rid_iter = Restore.get_rids(rid, rest_time)

		for indexed_tup in RORPIter.CollateIterators(mirror_iter, rid_iter):
			index = indexed_tup.index
			new_mirrorrp, new_rid = indexed_tup
			for rcd in Restore.yield_collated_tuples(index, new_mirrorrp,
				     new_rid, target.new_index(index), rest_time):
				yield rcd

	def check_dir_exists(mirrorrp, inc_tuple):
		"""Return true if target should be a directory"""
		if inc_tuple and inc_tuple[1]:
			# Incs say dir if last (earliest) one is a dir increment
			return inc_tuple[1][-1].getinctype() == "dir"
		elif mirrorrp: return mirrorrp.isdir() # if no incs, copy mirror
		else: return None

	def yield_mirrorrps(mirrorrp):
		"""Yield mirrorrps underneath given mirrorrp"""
		if mirrorrp and mirrorrp.isdir():
			dirlist = mirrorrp.listdir()
			dirlist.sort()
			for filename in dirlist: yield mirrorrp.append(filename)

	def yield_rids(rid, rest_time):
		"""Yield RestoreIncrementData objects within given rid dir

		If the rid doesn't correspond to a directory, don't yield any
		elements.  If there are increments whose corresponding base
		doesn't exist, the first element will be None.  All the rpaths
		involved correspond to files in the increment directory.

		"""
		if not rid or not rid.inc_rpath or not rid.inc_rpath.isdir(): return
		rid_dict = {} # dictionary of basenames:rids
		dirlist = rid.inc_rpath.listdir()		

		def affirm_dict_indexed(basename):
			"""Make sure the rid dictionary has given basename as key"""
			if not inc_list_dict.has_key(basename):
				rid_dict[basename] = RestoreIncrementData(
					rid.index + (basename,), None, []) # init with empty rid

		def add_to_dict(filename):
			"""Add filename to the inc tuple dictionary"""
			rp = rid.inc_rpath.append(filename)
			if rp.isincfile():
				basename = rp.getincbase_str()
				affirm_dict_indexed(basename)
				rid_dict[basename].inc_list.append(rp)
			elif rp.isdir():
				affirm_dict_indexed(filename)
				rid_dict[filename].inc_rpath = rp

		for filename in dirlist: add_to_dict(filename)
		keys = inc_list_dict.keys()
		keys.sort()

		# sortincseq now to avoid descending .missing directories later
		for key in keys:
			rid = rid_dict[key]
			if rid.inc_rpath or rid.inc_list:
				rid.sortincseq(rest_time)
				yield rid

MakeStatic(Restore)


class RestoreIncrementData:
	"""Contains information about a specific index from the increments dir

	This is just a container class, used because it would be easier to
	work with than an IndexedTuple.

	"""
	def __init__(self, index, inc_rpath, inc_list):
		self.index = index
		self.inc_rpath = inc_rpath
		self.inc_list = inc_list

	def sortincseq(self, rest_time):
		"""Sort self.inc_list sequence, throwing away irrelevant increments"""
		incpairs = map(lambda rp: (Time.stringtotime(rp.getinctime()), rp),
					   self.inc_list)
		# Only consider increments at or after the time being restored
		incpairs = filter(lambda pair: pair[0] >= rest_time, incpairs)

		# Now throw away older unnecessary increments
		incpairs.sort()
		i = 0
		while(i < len(incpairs)):
			# Only diff type increments require later versions
			if incpairs[i][1].getinctype() != "diff": break
			i = i+1
		incpairs = incpairs[:i+1]

		# Return increments in reversed order (latest first)
		incpairs.reverse()
		self.inc_list = map(lambda pair: pair[1], incpairs)


class RestoreCombinedData:
	"""Combine index information from increment and mirror directories

	This is similar to RestoreIncrementData but has mirror information
	also.

	"""
	def __init__(self, rid, mirror, target):
		"""Init - set values from one or both if they exist

		mirror and target are DSRPaths of the corresponding files in
		the mirror and target directory respectively.  rid is a
		RestoreIncrementData as defined above

		"""
		if rid:
			self.index = rid.index
			self.inc_rpath = rid.inc_rpath
			self.inc_list = rid.inc_list
			if mirror:
				self.mirror = mirror
				assert mirror.index == self.index
		elif mirror:
			self.index = mirror.index
			self.mirror = mirror
		else: assert None, "neither rid nor mirror given"
		self.target = target

	def RestoreFile(self):
		"""Non-recursive restore function """
		if not self.inc_list and not (self.mirror and self.mirror.lstat()):
			return # no increments were applicable
		self.log()

		if self.restore_hardlink(): return

		if not inclist or inclist[0].getinctype() == "diff":
			assert self.mirror and self.mirror.lstat(), \
				   "No base to go with incs for %s" % self.target.path
			RPath.copy_with_attribs(self.mirror, self.target)
		for inc in self.inc_list: self.applyinc(inc, self.target)

	def log(self)
		"""Log current restore action"""
		inc_string = ','.join(map(lambda x: x.path, self.inc_list))
		Log("Restoring %s with increments %s to %s" %
			(self.mirror and self.mirror.path,
			 inc_string, self.target.path), 5)

	def restore_hardlink(self):
		"""Hard link target and return true if hard linking appropriate"""
		if (Globals.preserve_hardlinks and
			Hardlink.restore_link(self.index, self.target)):
			RPath.copy_attribs(self.inc_list and inc_list[-1] or
							   self.mirror, self.target)
			return 1
		return None

	def applyinc(self, inc, target):
		"""Apply increment rp inc to targetrp target"""
		Log("Applying increment %s to %s" % (inc.path, target.path), 6)
		inctype = inc.getinctype()
		if inctype == "diff":
			if not target.lstat():
				raise RestoreError("Bad increment sequence at " + inc.path)
			Rdiff.patch_action(target, inc,
							   delta_compressed = inc.isinccompressed()
							   ).execute()
		elif inctype == "dir":
			if not target.isdir():
				if target.lstat():
					raise RestoreError("File %s already exists" % target.path)
				target.mkdir()
		elif inctype == "missing": return
		elif inctype == "snapshot":
			if inc.isinccompressed():
				target.write_from_fileobj(inc.open("rb", compress = 1))
			else: RPath.copy(inc, target)
		else: raise RestoreError("Unknown inctype %s" % inctype)
		RPath.copy_attribs(inc, target)
