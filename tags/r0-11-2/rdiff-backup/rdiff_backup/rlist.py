from __future__ import generators
import marshal, sha, types
from rdiff_backup.iterfile import *

#######################################################################
#
# rlist - Define the CachingIter, and sig/diff/patch ops on iterators
#

class CachingIter:
	"""Cache parts of an iter using a list

	Turn an iter into something that you can prepend elements into,
	and also read from without apparently changing the state.

	"""
	def __init__(self, iter_or_list):
		if type(iter_or_list) is types.ListType:
			self.iter = iter(iter_or_list)
		else: self.iter = iter_or_list
		self.next = self.iter.next
		self.head = []

	def __iter__(self): return self

	def _next(self):
		"""Take elements from the head list

		When there are elements waiting before the main iterator, this
		is the next function.  If not, iter.next returns to being next.

		"""
		head = self.head
		a = head[0]
		del head[0]
		if not head: self.next = self.iter.next
		return a

	def nextrange(self, m):
		"""Return next m elements in list"""
		l = head[:m]
		del head[:m]
		for i in xrange(m - len(l)): l.append(self.iter.next())
		return l

	def peek(self):
		"""Return next element without removing it from iterator"""
		n = self.next()
		self.push(n)
		return n

	def push(self, elem):
		"""Insert an element into the iterator at the beginning"""
		if not self.head: self.next = self._next
		self.head.insert(0, elem)

	def pushrange(self, elem_list):
		"""Insert list of multiple elements at the beginning"""
		if not self.head: self.next = self._next
		self.head[:0] = elem_list

	def cache(self, m):
		"""Move next m elements from iter to internal list

		If m is None, append the entire rest of the iterator.

		"""
		h, it = self.head, self.iter
		if m is None:
			for i in it: h.append(i)
		else:
			for i in xrange(m): h.append(it.next())

	def __getitem__(self, key):
		"""Support a[i:j] style notation.  Non destructive"""
		if type(key) is types.SliceType:
			if key.stop > len(self.head): self.cache(key.stop - len(self.head))
			return self.head[key.start, key.stop]
		else:
			if key >= len(self.head): self.cache(key + 1 - len(self.head))
			return self.head[key]



class RListDelta:
	"""Note a difference from one iterator (A) to another (B)

	The min, max pairs are indicies which stand for the half-open
	interval (min, max], and elemlist is a list of all the elements in
	A which fall within this interval.

	These are produced by the function RList.Deltas(...)

	"""
	def __init__(self, (min, max), elemlist):
		self.min, self.max = min, max
		self.elemlist = elemlist



class RList:
	"""Tools for signatures, diffing, and patching an iterator

	This class requires that the iterators involved are yielding
	objects that have .index and .data attributes.  Two objects with
	the same .data attribute are supposed to be equivalent.  The
	iterator must also yield the objects in increasing order with
	respect to the .index attribute.

	"""
	blocksize = 100

	def Signatures(iter):
		"""Return iterator of signatures from stream of pairs

		Each signature is an ordered pair (last index sig applies to,
		SHA digest of data)

		"""
		i, s = 0, sha.new()
		for iter_elem in iter:
			s.update(marshal.dumps(iter_elem.data))
			i = i+1
			if i == RList.blocksize:
				yield (iter_elem.index, s.digest())
				i, s = 0, sha.new()
		if i != 0: yield (iter_elem.index, s.digest())

	def sig_one_block(iter_or_list):
		"""Return the digest portion of a signature on given list"""
		s = sha.new()
		for iter_elem in iter_or_list: s.update(marshal.dumps(iter_elem.data))
		return s.digest()

	def Deltas(remote_sigs, iter):
		"""Return iterator of Delta objects that bring iter to remote"""
		def get_before(index, iter):
			"""Return elements in iter whose index is before or equal index
			iter needs to be pushable
			"""
			l = []
			while 1:
				try: iter_elem = iter.next()
				except StopIteration: return l
				if iter_elem.index > index: break
				l.append(iter_elem)
			iter.push(iter_elem)
			return l

		if not isinstance(iter, CachingIter): iter = CachingIter(iter)
		oldindex = None
		for (rs_index, rs_digest) in remote_sigs:
			l = get_before(rs_index, iter)
			if rs_digest != RList.sig_one_block(l):
				yield RListDelta((oldindex, rs_index), l)
			oldindex = rs_index

	def patch_once(basis, delta):
		"""Apply one delta to basis to return original iterator

		This returns original iterator up to and including the max range
		of delta, then stop.  basis should be pushable.

		"""
		# Return elements of basis until start of delta range
		for basis_elem in basis:
			if basis_elem.index > delta.min:
				basis.push(basis_elem)
				break
			yield basis_elem

		# Yield elements of delta...
		for elem in delta.elemlist: yield elem

		# Finally, discard basis until end of delta range
		for basis_elem in basis:
			if basis_elem.index > delta.max:
				basis.push(basis_elem)
				break

	def Patch(basis, deltas):
		"""Apply a delta stream to basis iterator, yielding original"""
		if not isinstance(basis, CachingIter): basis = CachingIter(basis)
		for d in deltas:
			for elem in RList.patch_once(basis, d): yield elem
		for elem in basis: yield elem

	def get_difference_once(basis, delta):
		"""From one delta, find differences from basis

		Will return pairs (basis_elem, new_elem) where basis_elem is
		the element from the basis iterator and new_elem is the
		element from the other iterator.  If either is missing None
		will take its place.  If both are present iff two have the
		same index.

		"""
		# Discard any elements of basis before delta starts
		for basis_elem in basis:
			if basis_elem.index > delta.min:
				basis.push(basis_elem)
				break

		# In range compare each one by one
		di, boverflow, doverflow = 0, None, None
		while 1:
			# Set indicies and data, or mark if at end of range already
			try:
				basis_elem = basis.next()
				if basis_elem.index > delta.max:
					basis.push(basis_elem)
					boverflow = 1
			except StopIteration: boverflow = 1
			if di >= len(delta.elemlist): doverflow = 1
			else: delta_elem = delta.elemlist[di]

			if boverflow and doverflow: break
			elif boverflow:
				yield (None, delta_elem)
				di = di+1
			elif doverflow: yield (basis_elem, None)

			# Now can assume that everything is in range
			elif basis_elem.index > delta_elem.index:
				yield (None, delta_elem)
				basis.push(basis_elem)
				di = di+1
			elif basis_elem.index == delta_elem.index:
				if basis_elem.data != delta_elem.data:
					yield (basis_elem, delta_elem)
				di = di+1
			else: yield (basis_elem, None)

	def Dissimilar(basis, deltas):
		"""Return iter of differences from delta iter and basis iter"""
		if not isinstance(basis, CachingIter): basis = CachingIter(basis)
		for d in deltas:
			for triple in RList.get_difference_once(basis, d): yield triple

MakeStatic(RList)
