from __future__ import generators
execfile("static.py")
import os, stat, types

#######################################################################
#
# lazy - Define some lazy data structures and functions acting on them
#

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
		if verbose: print "End when i2 = %s" % i2
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

	There are four stub functions below: start_process, end_process,
	branch_process, and check_for_errors.  A class that subclasses
	this one will probably fill in these functions to do more.

	It is important that this class be pickable, so keep that in mind
	when subclassing (this is used to resume failed sessions).

	"""
	def __init__(self, *args):
		"""ITR initializer"""
		self.init_args = args
		self.index = None
		self.subinstance = None
		self.finished = None
		self.caught_exception, self.start_successful = None, None

	def intree(self, index):
		"""Return true if index is still in current tree"""
		return self.base_index == index[:len(self.base_index)]

	def set_subinstance(self):
		"""Return subinstance of same type as self"""
		self.subinstance = self.__class__(*self.init_args)

	def process_w_subinstance(self, args):
		"""Give object to subinstance, if necessary update branch_val"""
		if not self.subinstance: self.set_subinstance()
		if not self.subinstance(*args):
			self.branch_process(self.subinstance)
			self.set_subinstance()
			assert self.subinstance(*args)

	def start_process(self, *args):
		"""Do some initial processing (stub)"""
		pass

	def end_process(self):
		"""Do any final processing before leaving branch (stub)"""
		pass

	def branch_process(self, subinstance):
		"""Process a branch right after it is finished (stub)"""
		pass

	def check_for_errors(self, function, *args):
		"""start/end_process is called by this function

		Usually it will distinguish between two types of errors.  Some
		are serious and will be reraised, others are caught and simply
		invalidate the current instance by setting
		self.caught_exception.

		"""
		try: return apply(function, args)
		except: raise

	def Finish(self):
		"""Call at end of sequence to tie everything up"""
		if not self.start_successful or self.finished:
			self.caught_exception = 1
		if self.caught_exception: self.log_prev_error(self.index)
		else:
			if self.subinstance:
				self.subinstance.Finish()
				self.branch_process(self.subinstance)
			self.check_for_errors(self.end_process)
			self.finished = 1

	def log_prev_error(self, index):
		"""Call function if no pending exception"""
		Log("Skipping %s because of previous error" % os.path.join(*index), 2)

	def __call__(self, *args):
		"""Process args, where args[0] is current position in iterator

		Returns true if args successfully processed, false if index is
		not in the current tree and thus the final result is
		available.

		Also note below we set self.index after doing the necessary
		start processing, in case there is a crash in the middle.

		"""
		index = args[0]
		assert type(index) is types.TupleType, type(index)

		if self.index is None:
			self.check_for_errors(self.start_process, *args)
			self.start_successful = 1
			self.index = self.base_index = index
			return 1

		if index <= self.index:
			Log("Warning: oldindex %s >= newindex %s" % (self.index, index), 2)
			return 1

		if not self.intree(index):
			self.Finish()
			return None

		if self.caught_exception: self.log_prev_error(index)
		else: self.process_w_subinstance(args)
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

	def check_for_errors(self, function, *args):
		"""Catch some non-fatal errors"""
		return Robust.check_common_error(self.on_error, function, *args)

