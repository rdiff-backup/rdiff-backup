# Copyright 2002 Ben Escoto
#
# This file is part of rdiff-backup.
#
# rdiff-backup is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, Inc., 675 Mass Ave, Cambridge MA
# 02139, USA; either version 2 of the License, or (at your option) any
# later version; incorporated herein by reference.

"""Define some lazy data structures and functions acting on them"""

from __future__ import generators
import os, stat, types
from static import *


class Iter:
	"""Hold static methods for the manipulation of lazy iterators"""

	def filter(predicate, iterator):
		"""Like filter in a lazy functional programming language"""
		for i in iterator:
			if predicate(i): yield i

	def map(function, iterator):
		"""Like map in a lazy functional programming language"""
		for i in iterator: yield function(i)

	def foreach(function, iterator):
		"""Run function on each element in iterator"""
		for i in iterator: function(i)

	def cat(*iters):
		"""Lazily concatenate iterators"""
		for iter in iters:
			for i in iter: yield i

	def cat2(iter_of_iters):
		"""Lazily concatenate iterators, iterated by big iterator"""
		for iter in iter_of_iters:
			for i in iter: yield i

	def empty(iter):
		"""True if iterator has length 0"""
		for i in iter: return None
		return 1

	def equal(iter1, iter2, verbose = None, operator = lambda x, y: x == y):
		"""True if iterator 1 has same elements as iterator 2

		Use equality operator, or == if it is unspecified.

		"""
		for i1 in iter1:
			try: i2 = iter2.next()
			except StopIteration:
				if verbose: print "End when i1 = %s" % i1
				return None
			if not operator(i1, i2):
				if verbose: print "%s not equal to %s" % (i1, i2)
				return None
		try: i2 = iter2.next()
		except StopIteration: return 1
		if verbose: print "End when i2 = %s" % (i2,)
		return None

	def Or(iter):
		"""True if any element in iterator is true.  Short circuiting"""
		i = None
		for i in iter:
			if i: return i
		return i

	def And(iter):
		"""True if all elements in iterator are true.  Short circuiting"""
		i = 1
		for i in iter:
			if not i: return i
		return i

	def len(iter):
		"""Return length of iterator"""
		i = 0
		while 1:
			try: iter.next()
			except StopIteration: return i
			i = i+1

	def foldr(f, default, iter):
		"""foldr the "fundamental list recursion operator"?"""
		try: next = iter.next()
		except StopIteration: return default
		return f(next, Iter.foldr(f, default, iter))

	def foldl(f, default, iter):
		"""the fundamental list iteration operator.."""
		while 1:
			try: next = iter.next()
			except StopIteration: return default
			default = f(default, next)

	def multiplex(iter, num_of_forks, final_func = None, closing_func = None):
		"""Split a single iterater into a number of streams

		The return val will be a list with length num_of_forks, each
		of which will be an iterator like iter.  final_func is the
		function that will be called on each element in iter just as
		it is being removed from the buffer.  closing_func is called
		when all the streams are finished.

		"""
		if num_of_forks == 2 and not final_func and not closing_func:
			im2 = IterMultiplex2(iter)
			return (im2.yielda(), im2.yieldb())
		if not final_func: final_func = lambda i: None
		if not closing_func: closing_func = lambda: None

		# buffer is a list of elements that some iterators need and others
		# don't
		buffer = []

		# buffer[forkposition[i]] is the next element yieled by iterator
		# i.  If it is -1, yield from the original iter
		starting_forkposition = [-1] * num_of_forks
		forkposition = starting_forkposition[:]
		called_closing_func = [None]

		def get_next(fork_num):
			"""Return the next element requested by fork_num"""
			if forkposition[fork_num] == -1:
				try:  buffer.insert(0, iter.next())
				except StopIteration:
					# call closing_func if necessary
					if (forkposition == starting_forkposition and
						not called_closing_func[0]):
						closing_func()
						called_closing_func[0] = None
					raise StopIteration
				for i in range(num_of_forks): forkposition[i] += 1

			return_val = buffer[forkposition[fork_num]]
			forkposition[fork_num] -= 1

			blen = len(buffer)
			if not (blen-1) in forkposition:
				# Last position in buffer no longer needed
				assert forkposition[fork_num] == blen-2
				final_func(buffer[blen-1])
				del buffer[blen-1]
			return return_val

		def make_iterator(fork_num):
			while(1): yield get_next(fork_num)

		return tuple(map(make_iterator, range(num_of_forks)))

MakeStatic(Iter)


class IterMultiplex2:
	"""Multiplex an iterator into 2 parts

	This is a special optimized case of the Iter.multiplex function,
	used when there is no closing_func or final_func, and we only want
	to split it into 2.  By profiling, this is a time sensitive class.

	"""
	def __init__(self, iter):
		self.a_leading_by = 0 # How many places a is ahead of b
		self.buffer = []
		self.iter = iter

	def yielda(self):
		"""Return first iterator"""
		buf, iter = self.buffer, self.iter
		while(1):
			if self.a_leading_by >= 0: # a is in front, add new element
				elem = iter.next() # exception will be passed
				buf.append(elem)
			else: elem = buf.pop(0) # b is in front, subtract an element
			self.a_leading_by += 1
			yield elem

	def yieldb(self):
		"""Return second iterator"""
		buf, iter = self.buffer, self.iter
		while(1):
			if self.a_leading_by <= 0: # b is in front, add new element
				elem = iter.next() # exception will be passed
				buf.append(elem)
			else: elem = buf.pop(0) # a is in front, subtract an element
			self.a_leading_by -= 1
			yield elem


class IterTreeReducer:
	"""Tree style reducer object for iterator

	The indicies of a RORPIter form a tree type structure.  This class
	can be used on each element of an iter in sequence and the result
	will be as if the corresponding tree was reduced.  This tries to
	bridge the gap between the tree nature of directories, and the
	iterator nature of the connection between hosts and the temporal
	order in which the files are processed.

	There are three stub functions below: start_process, end_process,
	and branch_process.  A class that subclasses this one will
	probably fill in these functions to do more.

	It is important that this class be pickable, so keep that in mind
	when subclassing (this is used to resume failed sessions).

	"""
	def __init__(self, *args):
		"""ITR initializer"""
		self.init_args = args
		self.base_index = self.index = None
		self.subinstances = [self]
		self.finished = None
		self.caught_exception = self.start_successful = None

	def finish_subinstances(self, index):
		"""Run Finish() on all subinstances index has passed

		When we pass out of a subinstance's tree, delete it and
		process it with the parent.  The innermost subinstances will
		be the last in the list.  Return None if we are out of the
		entire tree, and 1 otherwise.

		"""
		subinstances = self.subinstances
		while 1:
			to_be_finished = subinstances[-1]
			base_index = to_be_finished.base_index
			if base_index != index[:len(base_index)]:
				# out of the tree, finish with to_be_finished
				to_be_finished.call_end_proc()
				del subinstances[-1]
				if not subinstances: return None
				subinstances[-1].branch_process(to_be_finished)
			else: return 1

	def call_end_proc(self):
		"""Runs the end_process on self, checking for errors"""
		if self.finished or not self.start_successful:
			self.caught_exception = 1
		if self.caught_exception: self.log_prev_error(self.base_index)
		else: Robust.check_common_error(self.on_error, self.end_process)
		self.finished = 1

	def add_subinstance(self):
		"""Return subinstance of same type as self, add to subinstances"""
		subinst = self.__class__(*self.init_args)
		self.subinstances.append(subinst)
		return subinst

	def process_w_subinstance(self, index, subinst, args):
		"""Run start_process on latest subinstance"""
		Robust.check_common_error(subinst.on_error,
								  subinst.start_process, args)
		if not subinst.caught_exception: subinst.start_successful = 1
		subinst.base_index = index

	def start_process(self, *args):
		"""Do some initial processing (stub)"""
		pass

	def end_process(self):
		"""Do any final processing before leaving branch (stub)"""
		pass

	def branch_process(self, subinstance):
		"""Process a branch right after it is finished (stub)"""
		assert subinstance.finished
		pass

	def on_error(self, exc, *args):
		"""This will be run on any exception in start/end-process"""
		pass

	def Finish(self):
		"""Call at end of sequence to tie everything up"""
		while 1:
			to_be_finished = self.subinstances.pop()
			to_be_finished.call_end_proc()
			if not self.subinstances: break
			self.subinstances[-1].branch_process(to_be_finished)

	def log_prev_error(self, index):
		"""Call function if no pending exception"""
		Log("Skipping %s because of previous error" %
			(os.path.join(*index),), 2)

	def __call__(self, *args):
		"""Process args, where args[0] is current position in iterator

		Returns true if args successfully processed, false if index is
		not in the current tree and thus the final result is
		available.

		Also note below we set self.index after doing the necessary
		start processing, in case there is a crash in the middle.

		"""
		index = args[0]
		if self.base_index is None:
			self.process_w_subinstance(index, self, args)
			self.index = index
			return 1

		if index <= self.index:
			Log("Warning: oldindex %s >= newindex %s" % (self.index, index), 2)
			return 1

		if self.finish_subinstances(index) is None:
			return None # We are no longer in the main tree
		if self.subinstances[-1].start_successful:
			subinst = self.add_subinstance()
			self.process_w_subinstance(index, subinst, args)
		else: self.log_prev_error(index)

		self.index = index
		return 1


class ErrorITR(IterTreeReducer):
	"""Adds some error handling to above ITR, if ITR processes files"""
	def on_error(self, exc, *args):
		"""This is run on any exception in start/end-process"""
		self.caught_exception = 1
		if args and isinstance(args[0], tuple):
			filename = os.path.join(*args[0])
		elif self.index: filename = os.path.join(*self.index)
		else: filename = "."
		Log("Error '%s' processing %s" % (exc, filename), 2)


# Put at bottom to prevent (viciously) circular module dependencies
from robust import *
from log import *

