from __future__ import generators
execfile("increment.py")
import tempfile

#######################################################################
#
# restore - Read increment files and restore to original
#

class RestoreError(Exception): pass

class Restore:
	def RestoreFile(rest_time, rpbase, mirror_rel_index, inclist, rptarget):
		"""Non-recursive restore function

		rest_time is the time in seconds to restore to,
		rpbase is the base name of the file being restored,
		mirror_rel_index is the same as in RestoreRecursive,
		inclist is a list of rpaths containing all the relevant increments,
		and rptarget is the rpath that will be written with the restored file.

		"""
		if not inclist and not (rpbase and rpbase.lstat()):
			return # no increments were applicable
		Log("Restoring %s with increments %s to %s" %
			(rpbase and rpbase.path,
			 Restore.inclist2str(inclist), rptarget.path), 5)

		if (Globals.preserve_hardlinks and
			Hardlink.restore_link(mirror_rel_index, rptarget)):
			RPath.copy_attribs(inclist and inclist[-1] or rpbase, rptarget)
			return

		if not inclist or inclist[0].getinctype() == "diff":
			assert rpbase and rpbase.lstat(), \
				   "No base to go with incs %s" % Restore.inclist2str(inclist)
			RPath.copy_with_attribs(rpbase, rptarget)
		for inc in inclist: Restore.applyinc(inc, rptarget)

	def inclist2str(inclist):
		"""Return string version of inclist for logging"""
		return ",".join(map(lambda x: x.path, inclist))

	def sortincseq(rest_time, inclist):
		"""Sort the inc sequence, and throw away irrelevant increments"""
		incpairs = map(lambda rp: (Time.stringtotime(rp.getinctime()), rp),
					   inclist)
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
		return map(lambda pair: pair[1], incpairs)

	def applyinc(inc, target):
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

	def RestoreRecursive(rest_time, mirror_base, mirror_rel_index,
						 baseinc_tup, target_base):
		"""Recursive restore function.

		rest_time is the time in seconds to restore to;

		mirror_base is an rpath of the mirror directory corresponding
		to the one to be restored;

		mirror_rel_index is the index of the mirror_base relative to
		the root of the mirror directory.  (The mirror_base itself
		always has index (), as its index must match that of
		target_base.)

		baseinc_tup is the inc tuple (incdir, list of incs) to be
		restored;

		and target_base in the dsrp of the target directory.

		"""
		assert isinstance(target_base, DSRPath)
		baseinc_tup = IndexedTuple(baseinc_tup.index, (baseinc_tup[0],
						  Restore.sortincseq(rest_time, baseinc_tup[1])))

		collated = Restore.yield_collated_tuples((), mirror_base,
										   baseinc_tup, target_base, rest_time)
		mirror_finalizer = DestructiveStepping.Finalizer()
		target_finalizer = DestructiveStepping.Finalizer()

		for mirror, inc_tup, target in collated:
			inclist = inc_tup and inc_tup[1] or []
			DestructiveStepping.initialize(target, None)
			Restore.RestoreFile(rest_time, mirror, mirror_rel_index,
								inclist, target)
			target_finalizer(target)
			if mirror: mirror_finalizer(mirror)
		target_finalizer.getresult()
		mirror_finalizer.getresult()			

	def yield_collated_tuples(index, mirrorrp, inc_tup, target, rest_time):
		"""Iterate collated tuples starting with given args

		A collated tuple is an IndexedTuple (mirrorrp, inc_tuple, target).
		inc_tuple is itself an IndexedTuple.  target is an rpath where
		the created file should go.

		In this case the "mirror" directory is treated as the source,
		and we are actually copying stuff onto what Select considers
		the source directory.

		"""
		select_result = Globals.select_mirror.Select(target)
		if select_result == 0: return

		inc_base = inc_tup and inc_tup[0]
		if mirrorrp and (not Globals.select_source.Select(mirrorrp) or
						 DestructiveStepping.initialize(mirrorrp, None)):
			mirrorrp = None
		collated_tuple = IndexedTuple(index, (mirrorrp, inc_tup, target))
		if mirrorrp and mirrorrp.isdir() or inc_base and inc_base.isdir():
			depth_tuples = Restore.yield_collated_tuples_dir(index, mirrorrp,
									   			  inc_tup, target, rest_time)
		else: depth_tuples = None

		if select_result == 1:
			yield collated_tuple
			if depth_tuples:
				for tup in depth_tuples: yield tup
		elif select_result == 2:
			if depth_tuples:
				try: first = depth_tuples.next()
				except StopIteration: return # no tuples found inside, skip
				yield collated_tuple
				yield first
				for tup in depth_tuples: yield tup

	def yield_collated_tuples_dir(index, mirrorrp, inc_tup, target, rest_time):
		"""Yield collated tuples from inside given args"""
		if not Restore.check_dir_exists(mirrorrp, inc_tup): return
		if mirrorrp and mirrorrp.isdir():
			dirlist = mirrorrp.listdir()
			dirlist.sort()
			mirror_list = map(lambda x: IndexedTuple(x, (mirrorrp.append(x),)),
							  dirlist)
		else: mirror_list = []
		inc_list = Restore.get_inc_tuples(inc_tup, rest_time)

		for indexed_tup in RORPIter.CollateIterators(iter(mirror_list),
													 iter(inc_list)):
			filename = indexed_tup.index
			new_inc_tup = indexed_tup[1]
			new_mirrorrp = indexed_tup[0] and indexed_tup[0][0]
			for new_col_tup in Restore.yield_collated_tuples(
				index + (filename,), new_mirrorrp, new_inc_tup,
				target.append(filename), rest_time): yield new_col_tup

	def check_dir_exists(mirrorrp, inc_tuple):
		"""Return true if target should be a directory"""
		if inc_tuple and inc_tuple[1]:
			# Incs say dir if last (earliest) one is a dir increment
			return inc_tuple[1][-1].getinctype() == "dir"
		elif mirrorrp: return mirrorrp.isdir() # if no incs, copy mirror
		else: return None

	def get_inc_tuples(inc_tuple, rest_time):
		"""Return list of inc tuples in given rpath of increment directory

		An increment tuple is an IndexedTuple (pair).  The second
		element in the pair is a list of increments with the same
		base.  The first element is the rpath of the corresponding
		base.  Usually this base is a directory, otherwise it is
		ignored.  If there are increments whose corresponding base
		doesn't exist, the first element will be None.  All the rpaths
		involved correspond to files in the increment directory.

		"""
		if not inc_tuple: return []
		oldindex, incdir = inc_tuple.index, inc_tuple[0]
		if not incdir.isdir(): return []
		inc_list_dict = {} # Index tuple lists by index
		dirlist = incdir.listdir()		

		def affirm_dict_indexed(index):
			"""Make sure the inc_list_dict has given index"""
			if not inc_list_dict.has_key(index):
				inc_list_dict[index] = [None, []]

		def add_to_dict(filename):
			"""Add filename to the inc tuple dictionary"""
			rp = incdir.append(filename)
			if rp.isincfile():
				basename = rp.getincbase_str()
				affirm_dict_indexed(basename)
				inc_list_dict[basename][1].append(rp)
			elif rp.isdir():
				affirm_dict_indexed(filename)
				inc_list_dict[filename][0] = rp

		def index2tuple(index):
			"""Return inc_tuple version of dictionary entry by index

			Also runs sortincseq to sort the increments and remove
			irrelevant ones.  This is done here so we can avoid
			descending into .missing directories.

			"""
			incbase, inclist = inc_list_dict[index]
			inclist = Restore.sortincseq(rest_time, inclist)
			if not inclist: return None # no relevant increments, so ignore
			return IndexedTuple(index, (incbase, inclist))

		for filename in dirlist: add_to_dict(filename)
		keys = inc_list_dict.keys()
		keys.sort()
		return filter(lambda x: x, map(index2tuple, keys))

MakeStatic(Restore)
