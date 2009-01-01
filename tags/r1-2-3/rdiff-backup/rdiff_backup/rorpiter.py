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

"""Operations on Iterators of Read Only Remote Paths

The main structure will be an iterator that yields RORPaths.
Every RORPath has a "raw" form that makes it more amenable to
being turned into a file.  The raw form of the iterator yields
each RORPath in the form of the tuple (index, data_dictionary,
files), where files is the number of files attached (usually 1 or
0).  After that, if a file is attached, it yields that file.

"""

from __future__ import generators
import os, tempfile, UserList, types
import Globals, rpath, iterfile, log


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
		return Collate2Iters(rorp_iters[0], rorp_iters[1])
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
				if relem2: yield (None, relem2)
				for relem2 in riter2:
					yield (None, relem2)
				break
			index1 = relem1.index
		if not relem2:
			try: relem2 = riter2.next()
			except StopIteration:
				if relem1: yield (relem1, None)
				for relem1 in riter1:
					yield (relem1, None)
				break
			index2 = relem2.index

		if index1 < index2:
			yield (relem1, None)
			relem1 = None
		elif index1 == index2:
			yield (relem1, relem2)
			relem1, relem2 = None, None
		else: # index2 is less
			yield (None, relem2)
			relem2 = None


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


def FillInIter(rpiter, rootrp):
	"""Given ordered rpiter and rootrp, fill in missing indicies with rpaths

	For instance, suppose rpiter contains rpaths with indicies (),
	(1,2), (2,5).  Then return iter with rpaths (), (1,), (1,2), (2,),
	(2,5).  This is used when we need to process directories before or
	after processing a file in that directory.

	"""
	# Handle first element as special case
	first_rp = rpiter.next() # StopIteration gets passed upwards
	cur_index = first_rp.index
	for i in range(len(cur_index)): yield rootrp.new_index(cur_index[:i])
	yield first_rp
	del first_rp
	old_index = cur_index

	# Now do all the other elements
	for rp in rpiter:
		cur_index = rp.index
		if not cur_index[:-1] == old_index[:-1]: # Handle special case quickly
			for i in range(1, len(cur_index)): # i==0 case already handled
				if cur_index[:i] != old_index[:i]:
					filler_rp = rootrp.new_index(cur_index[:i])
					if not filler_rp.isdir():
						log.Log("Warning: expected %s to be a directory but "
								"found %s instead.\nThis is probably caused "
								"by a bug in versions 1.0.0 and earlier." %
								(filler_rp.path, filler_rp.lstat()), 2)
						filler_rp.make_zero_dir(rootrp)
					yield filler_rp
		yield rp
		old_index = cur_index


class IterTreeReducer:
	"""Tree style reducer object for iterator

	The indicies of a RORPIter form a tree type structure.  This class
	can be used on each element of an iter in sequence and the result
	will be as if the corresponding tree was reduced.  This tries to
	bridge the gap between the tree nature of directories, and the
	iterator nature of the connection between hosts and the temporal
	order in which the files are processed.

	"""
	def __init__(self, branch_class, branch_args):
		"""ITR initializer"""
		self.branch_class = branch_class
		self.branch_args = branch_args
		self.index = None
		self.root_branch = branch_class(*branch_args)
		self.branches = [self.root_branch]
		self.root_fast_processed = None

	def finish_branches(self, index):
		"""Run Finish() on all branches index has passed

		When we pass out of a branch, delete it and process it with
		the parent.  The innermost branches will be the last in the
		list.  Return None if we are out of the entire tree, and 1
		otherwise.

		"""
		branches = self.branches
		while 1:
			to_be_finished = branches[-1]
			base_index = to_be_finished.base_index
			if base_index != index[:len(base_index)]:
				# out of the tree, finish with to_be_finished
				to_be_finished.end_process()
				del branches[-1]
				if not branches: return None
				branches[-1].branch_process(to_be_finished)
			else: return 1

	def add_branch(self, index):
		"""Return branch of type self.branch_class, add to branch list"""
		branch = self.branch_class(*self.branch_args)
		branch.base_index = index
		self.branches.append(branch)
		return branch

	def Finish(self):
		"""Call at end of sequence to tie everything up"""
		if self.index is None or self.root_fast_processed: return
		while 1:
			to_be_finished = self.branches.pop()
			to_be_finished.end_process()
			if not self.branches: break
			self.branches[-1].branch_process(to_be_finished)

	def __call__(self, *args):
		"""Process args, where args[0] is current position in iterator

		Returns true if args successfully processed, false if index is
		not in the current tree and thus the final result is
		available.

		Also note below we set self.index after doing the necessary
		start processing, in case there is a crash in the middle.

		"""
		index = args[0]
		if self.index is None:
			self.root_branch.base_index = index
			if self.root_branch.can_fast_process(*args):
				self.root_branch.fast_process(*args)
				self.root_fast_processed = 1
			else: self.root_branch.start_process(*args)
			self.index = index
			return 1
		if index == self.index:
			log.Log("Warning, repeated index %s, bad filesystem?"
					% (index,), 2)
		elif index < self.index:
			assert 0, "Bad index order: %s >= %s" % (self.index, index)
		else: # normal case
			if self.finish_branches(index) is None:
				return None # We are no longer in the main tree
			last_branch = self.branches[-1]
			if last_branch.can_fast_process(*args):
				last_branch.fast_process(*args)
			else:
				branch = self.add_branch(index)
				branch.start_process(*args)

		self.index = index
		return 1


class ITRBranch:
	"""Helper class for IterTreeReducer above

	There are five stub functions below: start_process, end_process,
	branch_process, can_fast_process, and fast_process.  A class that
	subclasses this one will probably fill in these functions to do
	more.

	"""
	base_index = index = None
	def start_process(self, *args):
		"""Do some initial processing (stub)"""
		pass

	def end_process(self):
		"""Do any final processing before leaving branch (stub)"""
		pass

	def branch_process(self, branch):
		"""Process a branch right after it is finished (stub)"""
		pass

	def can_fast_process(self, *args):
		"""True if object can be processed without new branch (stub)"""
		return None

	def fast_process(self, *args):
		"""Process args without new child branch (stub)"""
		pass


class CacheIndexable:
	"""Cache last few indexed elements in iterator

	This class should be initialized with an iterator yielding
	.index'd objects.  It looks like it is just the same iterator as
	the one that initialized it.  Luckily, it does more, caching the
	last few elements iterated, which can be retrieved using the
	.get() method.

	If the index is not in the cache, return None.

	"""
	def __init__(self, indexed_iter, cache_size = None):
		"""Make new CacheIndexable.  Cache_size is max cache length"""
		self.cache_size = cache_size
		self.iter = indexed_iter
		self.cache_dict = {}
		self.cache_indicies = []

	def next(self):
		"""Return next elem, add to cache.  StopIteration passed upwards"""
		next_elem = self.iter.next()
		next_index = next_elem.index
		self.cache_dict[next_index] = next_elem
		self.cache_indicies.append(next_index)

		if len(self.cache_indicies) > self.cache_size:
			try:
				del self.cache_dict[self.cache_indicies[0]]
			except KeyError:
				log.Log("Warning: index %s missing from iterator cache" %
					(self.cache_indicies[0],), 2)
			del self.cache_indicies[0]

		return next_elem

	def __iter__(self): return self

	def get(self, index):
		"""Return element with index index from cache"""
		try: return self.cache_dict[index]
		except KeyError:
			assert index >= self.cache_indicies[0], \
				   "Index out of order: "+repr((index, self.cache_indicies[0]))
			return None
