from __future__ import generators
execfile("increment.py")
import tempfile

#######################################################################
#
# restore - Read increment files and restore to original
#

class RestoreError(Exception): pass

class Restore:
	def RestoreFile(rest_time, rpbase, inclist, rptarget):
		"""Non-recursive restore function

		rest_time is the time in seconds to restore to,
		rpbase is the base name of the file being restored,
		inclist is a list of rpaths containing all the relevant increments,
		and rptarget is the rpath that will be written with the restored file.

		"""
		inclist = Restore.sortincseq(rest_time, inclist)
		if not inclist and not (rpbase and rpbase.lstat()):
			return # no increments were applicable
		Log("Restoring %s with increments %s to %s" %
			(rpbase and rpbase.path,
			 Restore.inclist2str(inclist), rptarget.path), 5)
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

		# Return increments in reversed order
		incpairs.reverse()
		return map(lambda pair: pair[1], incpairs)

	def applyinc(inc, target):
		"""Apply increment rp inc to targetrp target"""
		Log("Applying increment %s to %s" % (inc.path, target.path), 6)
		inctype = inc.getinctype()
		if inctype == "diff":
			if not target.lstat():
				raise RestoreError("Bad increment sequence at " + inc.path)
			Rdiff.patch_action(target, inc).execute()
		elif inctype == "dir":
			if not target.isdir():
				if target.lstat():
					raise RestoreError("File %s already exists" % target.path)
				target.mkdir()
		elif inctype == "missing": return
		elif inctype == "snapshot": RPath.copy(inc, target)
		else: raise RestoreError("Unknown inctype %s" % inctype)
		RPath.copy_attribs(inc, target)

	def RestoreRecursive(rest_time, mirror_base, baseinc_tup, target_base):
		"""Recursive restore function.

		rest_time is the time in seconds to restore to;
		mirror_base is an rpath of the mirror directory corresponding
		to the one to be restored;
		baseinc_tup is the inc tuple (incdir, list of incs) to be
		restored;
		and target_base in the dsrp of the target directory.

		"""
		assert isinstance(target_base, DSRPath)
		collated = RORPIter.CollateIterators(
			DestructiveStepping.Iterate_from(mirror_base, None),
			Restore.yield_inc_tuples(baseinc_tup))
		mirror_finalizer = DestructiveStepping.Finalizer()
		target_finalizer = DestructiveStepping.Finalizer()

		for mirror, inc_tup in collated:
			if not inc_tup:
				inclist = []
				target = target_base.new_index(mirror.index)
			else:
				inclist = inc_tup[1]
				target = target_base.new_index(inc_tup.index)
			DestructiveStepping.initialize(target, None)
			Restore.RestoreFile(rest_time, mirror, inclist, target)
			target_finalizer(target)
			if mirror: mirror_finalizer(mirror)
		target_finalizer.getresult()
		mirror_finalizer.getresult()

	def yield_inc_tuples(inc_tuple):
		"""Iterate increment tuples starting with inc_tuple

		An increment tuple is an IndexedTuple (pair).  The first will
		be the rpath of a directory, and the second is a list of all
		the increments associated with that directory.  If there are
		increments that do not correspond to a directory, the first
		element will be None.  All the rpaths involved correspond to
		files in the increment directory.

		"""
		oldindex, rpath = inc_tuple.index, inc_tuple[0]
		yield inc_tuple
		if not rpath or not rpath.isdir(): return

		inc_list_dict = {} # Index tuple lists by index
		dirlist = rpath.listdir()

		def affirm_dict_indexed(index):
			"""Make sure the inc_list_dict has given index"""
			if not inc_list_dict.has_key(index):
				inc_list_dict[index] = [None, []]

		def add_to_dict(filename):
			"""Add filename to the inc tuple dictionary"""
			rp = rpath.append(filename)
			if rp.isincfile():
				basename = rp.getincbase_str()
				affirm_dict_indexed(basename)
				inc_list_dict[basename][1].append(rp)
			elif rp.isdir():
				affirm_dict_indexed(filename)
				inc_list_dict[filename][0] = rp

		def list2tuple(index):
			"""Return inc_tuple version of dictionary entry by index"""
			inclist = inc_list_dict[index]
			if not inclist[1]: return None # no increments, so ignore
			return IndexedTuple(oldindex + (index,), inclist)

		for filename in dirlist: add_to_dict(filename)
		keys = inc_list_dict.keys()
		keys.sort()
		for index in keys:
			new_inc_tuple = list2tuple(index)
			if not new_inc_tuple: continue
			elif new_inc_tuple[0]: # corresponds to directory
				for i in Restore.yield_inc_tuples(new_inc_tuple): yield i
			else: yield new_inc_tuple

MakeStatic(Restore)
