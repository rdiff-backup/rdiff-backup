execfile("robust.py")
from __future__ import generators
import tempfile, UserList

#######################################################################
#
# rorpiter - Operations on Iterators of Read Only Remote Paths
#

class RORPIterException(Exception): pass

class RORPIter:
	"""Functions relating to iterators of Read Only RPaths

	The main structure will be an iterator that yields RORPaths.
	Every RORPath has a "raw" form that makes it more amenable to
	being turned into a file.  The raw form of the iterator yields
	each RORPath in the form of the tuple (index, data_dictionary,
	files), where files is the number of files attached (usually 1 or
	0).  After that, if a file is attached, it yields that file.

	"""
	def ToRaw(rorp_iter):
		"""Convert a rorp iterator to raw form"""
		for rorp in rorp_iter:
			if rorp.file:
				yield (rorp.index, rorp.data, 1)
				yield rorp.file
			else: yield (rorp.index, rorp.data, 0)

	def FromRaw(raw_iter):
		"""Convert raw rorp iter back to standard form"""
		for index, data, num_files in raw_iter:
			rorp = RORPath(index, data)
			if num_files:
				assert num_files == 1, "Only one file accepted right now"
				rorp.setfile(RORPIter.getnext(raw_iter))
			yield rorp

	def ToFile(rorp_iter):
		"""Return file version of iterator"""
		return FileWrappingIter(RORPIter.ToRaw(rorp_iter))

	def FromFile(fileobj):
		"""Recover rorp iterator from file interface"""
		return RORPIter.FromRaw(IterWrappingFile(fileobj))

	def IterateRPaths(base_rp):
		"""Return an iterator yielding RPaths with given base rp"""
		yield base_rp
		if base_rp.isdir():
			dirlisting = base_rp.listdir()
			dirlisting.sort()
			for filename in dirlisting:
				for rp in RORPIter.IterateRPaths(base_rp.append(filename)):
					yield rp

	def Signatures(rp_iter):
		"""Yield signatures of rpaths in given rp_iter"""
		def error_handler(exc, rp):
			Log("Error generating signature for %s" % rp.path)
			return None

		for rp in rp_iter:
			if rp.isplaceholder(): yield rp
			else:
				rorp = rp.getRORPath()
				if rp.isreg():
					if rp.isflaglinked(): rorp.flaglinked()
					else:
						fp = Robust.check_common_error(
							error_handler, Rdiff.get_signature, (rp,))
						if fp: rorp.setfile(fp)
						else: continue
				yield rorp

	def GetSignatureIter(base_rp):
		"""Return a signature iterator recurring over the base_rp"""
		return RORPIter.Signatures(RORPIter.IterateRPaths(base_rp))

	def CollateIterators(*rorp_iters):
		"""Collate RORPath iterators by index

		So it takes two or more iterators of rorps and returns an
		iterator yielding tuples like (rorp1, rorp2) with the same
		index.  If one or the other lacks that index, it will be None

		"""
		# overflow[i] means that iter[i] has been exhausted
		# rorps[i] is None means that it is time to replenish it.
		iter_num = len(rorp_iters)
		if iter_num == 2:
			return RORPIter.Collate2Iters(rorp_iters[0], rorp_iters[1])
		overflow = [None] * iter_num
		rorps = overflow[:]

		def setrorps(overflow, rorps):
			"""Set the overflow and rorps list"""
			for i in range(iter_num):
				if not overflow[i] and rorps[i] is None:
					try: rorps[i] = rorp_iters[i].next()
					except StopIteration:
						overflow[i] = 1
						rorps[i] = None

		def getleastindex(rorps):
			"""Return the first index in rorps, assuming rorps isn't empty"""
			return min(map(lambda rorp: rorp.index,
						   filter(lambda x: x, rorps)))

		def yield_tuples(iter_num, overflow, rorps):
			while 1:
				setrorps(overflow, rorps)
				if not None in overflow: break

				index = getleastindex(rorps)
				yieldval = []
				for i in range(iter_num):
					if rorps[i] and rorps[i].index == index:
						yieldval.append(rorps[i])
						rorps[i] = None
					else: yieldval.append(None)
				yield IndexedTuple(index, yieldval)
		return yield_tuples(iter_num, overflow, rorps)

	def Collate2Iters(riter1, riter2):
		"""Special case of CollateIterators with 2 arguments

		This does the same thing but is faster because it doesn't have
		to consider the >2 iterator case.  Profiler says speed is
		important here.
		
		"""
		relem1, relem2 = None, None
		while 1:
			if not relem1:
				try: relem1 = riter1.next()
				except StopIteration:
					if relem2: yield IndexedTuple(index2, (None, relem2))
					for relem2 in riter2:
						yield IndexedTuple(relem2.index, (None, relem2))
					break
				index1 = relem1.index
			if not relem2:
				try: relem2 = riter2.next()
				except StopIteration:
					if relem1: yield IndexedTuple(index1, (relem1, None))
					for relem1 in riter1:
						yield IndexedTuple(relem1.index, (relem1, None))
					break
				index2 = relem2.index

			if index1 < index2:
				yield IndexedTuple(index1, (relem1, None))
				relem1 = None
			elif index1 == index2:
				yield IndexedTuple(index1, (relem1, relem2))
				relem1, relem2 = None, None
			else: # index2 is less
				yield IndexedTuple(index2, (None, relem2))
				relem2 = None

	def getnext(iter):
		"""Return the next element of an iterator, raising error if none"""
		try: next = iter.next()
		except StopIteration: raise RORPIterException("Unexpected end to iter")
		return next

	def GetDiffIter(sig_iter, new_iter):
		"""Return delta iterator from sig_iter to new_iter

		The accompanying file for each will be a delta as produced by
		rdiff, unless the destination file does not exist, in which
		case it will be the file in its entirety.

		sig_iter may be composed of rorps, but new_iter should have
		full RPaths.

		"""
		collated_iter = RORPIter.CollateIterators(sig_iter, new_iter)
		for rorp, rp in collated_iter: yield RORPIter.diffonce(rorp, rp)

	def diffonce(sig_rorp, new_rp):
		"""Return one diff rorp, based from signature rorp and orig rp"""
		if sig_rorp and Globals.preserve_hardlinks and sig_rorp.isflaglinked():
			if new_rp: diff_rorp = new_rp.getRORPath()
			else: diff_rorp = RORPath(sig_rorp.index)
			diff_rorp.flaglinked()
			return diff_rorp
		elif sig_rorp and sig_rorp.isreg() and new_rp and new_rp.isreg():
			diff_rorp = new_rp.getRORPath()
			diff_rorp.setfile(Rdiff.get_delta_sigfileobj(sig_rorp.open("rb"),
														 new_rp))
			diff_rorp.set_attached_filetype('diff')
			return diff_rorp
		else:
			# Just send over originial if diff isn't appropriate
			if sig_rorp: sig_rorp.close_if_necessary()
			if not new_rp: return RORPath(sig_rorp.index)
			elif new_rp.isreg():
				diff_rorp = new_rp.getRORPath(1)
				diff_rorp.set_attached_filetype('snapshot')
				return diff_rorp
			else: return new_rp.getRORPath()

	def PatchIter(base_rp, diff_iter):
		"""Patch the appropriate rps in basis_iter using diff_iter"""
		basis_iter = RORPIter.IterateRPaths(base_rp)
		collated_iter = RORPIter.CollateIterators(basis_iter, diff_iter)
		for basisrp, diff_rorp in collated_iter:
			RORPIter.patchonce_action(base_rp, basisrp, diff_rorp).execute()

	def patchonce_action(base_rp, basisrp, diff_rorp):
		"""Return action patching basisrp using diff_rorp"""
		assert diff_rorp, "Missing diff index %s" % basisrp.index
		if not diff_rorp.lstat():
			return RobustAction(None, lambda init_val: basisrp.delete(), None)

		if Globals.preserve_hardlinks and diff_rorp.isflaglinked():
			if not basisrp: basisrp = base_rp.new_index(diff_rorp.index)
			tf = TempFileManager.new(basisrp)
			def init(): Hardlink.link_rp(diff_rorp, tf, basisrp)
			return Robust.make_tf_robustaction(init, tf, basisrp)
		elif basisrp and basisrp.isreg() and diff_rorp.isreg():
			assert diff_rorp.get_attached_filetype() == 'diff'
			return Rdiff.patch_with_attribs_action(basisrp, diff_rorp)
		else: # Diff contains whole file, just copy it over
			if not basisrp: basisrp = base_rp.new_index(diff_rorp.index)
			return Robust.copy_with_attribs_action(diff_rorp, basisrp)

MakeStatic(RORPIter)



class IndexedTuple(UserList.UserList):
	"""Like a tuple, but has .index

	This is used by CollateIterator above, and can be passed to the
	IterTreeReducer.

	"""
	def __init__(self, index, sequence):
		self.index = index
		self.data = tuple(sequence)

	def __len__(self): return len(self.data)

	def __getitem__(self, key):
		"""This only works for numerical keys (easier this way)"""
		return self.data[key]

	def __lt__(self, other): return self.__cmp__(other) == -1
	def __le__(self, other): return self.__cmp__(other) != 1
	def __ne__(self, other): return not self.__eq__(other)
	def __gt__(self, other): return self.__cmp__(other) == 1
	def __ge__(self, other): return self.__cmp__(other) != -1
	
	def __cmp__(self, other):
		assert isinstance(other, IndexedTuple)
		if self.index < other.index: return -1
		elif self.index == other.index: return 0
		else: return 1

	def __eq__(self, other):
		if isinstance(other, IndexedTuple):
			return self.index == other.index and self.data == other.data
		elif type(other) is types.TupleType:
			return self.data == other
		else: return None

	def __str__(self):
		return  "(%s).%s" % (", ".join(map(str, self.data)), self.index)
