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

	The elements of the iterator are required to have a tuple-style
	.index, called "indexed elem" below.

	"""
	def __init__(self, base_init, branch_reducer,
				 branch_base, base_final, initial_state = None):
		"""ITR initializer

		base_init is a function of one argument, an indexed elem.  It
		is called immediately on any elem in the iterator.  It should
		return some value type A.

		branch_reducer and branch_base are used to form a value on a
		bunch of reduced branches, in the way that a linked list of
		type C can be folded to form a value type B.

		base_final is called when leaving a tree.  It takes three
		arguments, the indexed elem, the output (type A) of base_init,
		the output of branch_reducer on all the branches (type B) and
		returns a value type C.

		"""
		self.base_init = base_init
		self.branch_reducer = branch_reducer
		self.base_final = base_final
		self.branch_base = branch_base

		if initial_state: self.setstate(initial_state)
		else:
			self.state = IterTreeReducerState(branch_base)
			self.subreducer = None

	def setstate(self, state):
		"""Update with new state, recursive if necessary"""
		self.state = state
		if state.substate: self.subreducer = self.newinstance(state.substate)
		else:  self.subreducer = None

	def getstate(self): return self.state

	def getresult(self):
		"""Return results of calculation"""
		if not self.state.calculated: self.calculate_final_val()
		return self.state.final_val

	def intree(self, index):
		"""Return true if index is still in current tree"""
		return self.state.base_index == index[:len(self.state.base_index)]

	def newinstance(self, state = None):
		"""Return reducer of same type as self

		If state is None, sets substate of self.state, otherwise
		assume this is already set.

		"""
		new =  self.__class__(self.base_init, self.branch_reducer,
							  self.branch_base, self.base_final, state)		
		if state is None: self.state.substate = new.state
		return new

	def process_w_subreducer(self, indexed_elem):
		"""Give object to subreducer, if necessary update branch_val"""
		if not self.subreducer:
			self.subreducer = self.newinstance()
		if not self.subreducer(indexed_elem):
			self.state.branch_val = self.branch_reducer(self.state.branch_val,
												 self.subreducer.getresult())
			self.subreducer = self.newinstance()
			assert self.subreducer(indexed_elem)

	def calculate_final_val(self):
		"""Set final value"""
		if self.subreducer:
			self.state.branch_val = self.branch_reducer(self.state.branch_val,
												  self.subreducer.getresult())
		if self.state.current_index is None:
			# No input, set None as default value
			self.state.final_val = None
		else:
			self.state.final_val = self.base_final(self.state.base_elem,
											 self.state.base_init_val,
											 self.state.branch_val)
		self.state.calculated = 1

	def __call__(self, indexed_elem):
		"""Process elem, current position in iterator

		Returns true if elem successfully processed, false if elem is
		not in the current tree and thus the final result is
		available.

		"""
		index = indexed_elem.index
		assert type(index) is types.TupleType

		if self.state.current_index is None: # must be at base
			self.state.base_init_val = self.base_init(indexed_elem)
			# Do most crash-prone op first, so we don't leave inconsistent
			self.state.current_index = index
			self.state.base_index = index
			self.state.base_elem = indexed_elem
			return 1
		elif not index > self.state.current_index:
			Log("Warning: oldindex %s >= newindex %s" %
				(self.state.current_index, index), 2)

		if not self.intree(index):
			self.calculate_final_val()
			return None
		else:
			self.process_w_subreducer(indexed_elem)
			self.state.current_index = index
			return 1


class IterTreeReducerState:
	"""Holds the state for IterTreeReducers

	An IterTreeReducer cannot be pickled directly because it holds
	some anonymous functions.  This class contains the relevant data
	that is likely to be picklable, so the ITR can be saved and loaded
	if the associated functions are known.

	"""
	def __init__(self, branch_base):
		"""ITRS initializer

		Class variables:
		self.current_index - last index processing started on, or None
		self.base_index - index of first element processed
		self.base_elem - first element processed
		self.branch_val - default branch reducing value

		self.calculated - true iff the final value has been calculated
		self.base_init_val - return value of base_init function
		self.final_val - Final value once it's calculated
		self.substate - IterTreeReducerState when subreducer active

		"""
		self.current_index = None
		self.calculated = None
		self.branch_val = branch_base
		self.substate = None
		
