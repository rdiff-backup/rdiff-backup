from __future__ import generators
import unittest, pickle
from commontest import *
from lazy import *

class Iterators(unittest.TestCase):
	one_to_100 = lambda s: iter(range(1, 101))
	evens = lambda s: iter(range(2, 101, 2))
	odds = lambda s: iter(range(1, 100, 2))
	empty = lambda s: iter([])

	def __init__(self, *args):
		apply (unittest.TestCase.__init__, (self,) + args)
		self.falseerror = self.falseerror_maker()
		self.trueerror = self.trueerror_maker()
		self.emptygen = self.emptygen_maker()
		self.typeerror = self.typeerror_maker()
		self.nameerror = self.nameerror_maker()

	def falseerror_maker(self):
		yield None
		yield 0
		yield []
		raise Exception

	def trueerror_maker(self):
		yield 1
		yield "hello"
		yield (2, 3)
		raise Exception

	def nameerror_maker(self):
		if 0: yield 1
		raise NameError

	def typeerror_maker(self):
		yield 1
		yield 2
		raise TypeError

	def alwayserror(self, x):
		raise Exception

	def emptygen_maker(self):
		if 0: yield 1


class IterEqualTestCase(Iterators):
	"""Tests for iter_equal function"""
	def testEmpty(self):
		"""Empty iterators should be equal"""
		assert Iter.equal(self.empty(), iter([]))

	def testNormal(self):
		"""See if normal iterators are equal"""
		assert Iter.equal(iter((1,2,3)), iter((1,2,3)))
		assert Iter.equal(self.odds(), iter(range(1, 100, 2)))
		assert Iter.equal(iter((1,2,3)), iter(range(1, 4)))

	def testNormalInequality(self):
		"""See if normal unequals work"""
		assert not Iter.equal(iter((1,2,3)), iter((1,2,4)))
		assert not Iter.equal(self.odds(), iter(["hello", "there"]))

	def testGenerators(self):
		"""equals works for generators"""
		def f():
			yield 1
			yield "hello"
		def g():
			yield 1
			yield "hello"
		assert Iter.equal(f(), g())

	def testLength(self):
		"""Differently sized iterators"""
		assert not Iter.equal(iter((1,2,3)), iter((1,2)))
		assert not Iter.equal(iter((1,2)), iter((1,2,3)))


class FilterTestCase(Iterators):
	"""Tests for lazy_filter function"""
	def testEmpty(self):
		"""empty iterators -> empty iterators"""
		assert Iter.empty(Iter.filter(self.alwayserror,
									  self.empty())), \
			   "Filtering an empty iterator should result in empty iterator"

	def testNum1(self):
		"""Test numbers 1 - 100 #1"""
		assert Iter.equal(Iter.filter(lambda x: x % 2 == 0,
									  self.one_to_100()),
						  self.evens())
		assert Iter.equal(Iter.filter(lambda x: x % 2,
									  self.one_to_100()),
						  self.odds())

	def testError(self):
		"""Should raise appropriate error"""
		i = Iter.filter(lambda x: x, self.falseerror_maker())
		self.assertRaises(Exception, i.next)


class MapTestCase(Iterators):
	"""Test mapping of iterators"""
	def testNumbers(self):
		"""1 to 100 * 2 = 2 to 200"""
		assert Iter.equal(Iter.map(lambda x: 2*x, self.one_to_100()),
						  iter(range(2, 201, 2)))

	def testShortcut(self):
		"""Map should go in order"""
		def f(x):
			if x == "hello":
				raise NameError
		i = Iter.map(f, self.trueerror_maker())
		i.next()
		self.assertRaises(NameError, i.next)

	def testEmpty(self):
		"""Map of an empty iterator is empty"""
		assert Iter.empty(Iter.map(lambda x: x, iter([])))


class CatTestCase(Iterators):
	"""Test concatenation of iterators"""
	def testEmpty(self):
		"""Empty + empty = empty"""
		assert Iter.empty(Iter.cat(iter([]), iter([])))

	def testNumbers(self):
		"""1 to 50 + 51 to 100 = 1 to 100"""
		assert Iter.equal(Iter.cat(iter(range(1, 51)), iter(range(51, 101))),
						  self.one_to_100())

	def testShortcut(self):
		"""Process iterators in order"""
		i = Iter.cat(self.typeerror_maker(), self.nameerror_maker())
		i.next()
		i.next()
		self.assertRaises(TypeError, i.next)


class AndOrTestCase(Iterators):
	"""Test And and Or"""
	def testEmpty(self):
		"""And() -> true, Or() -> false"""
		assert Iter.And(self.empty())
		assert not Iter.Or(self.empty())

	def testAndShortcut(self):
		"""And should return if any false"""
		assert Iter.And(self.falseerror_maker()) is None

	def testOrShortcut(self):
		"""Or should return if any true"""
		assert Iter.Or(self.trueerror_maker()) == 1

	def testNormalAnd(self):
		"""And should go through true iterators, picking last"""
		assert Iter.And(iter([1,2,3,4])) == 4
		self.assertRaises(Exception, Iter.And, self.trueerror_maker())

	def testNormalOr(self):
		"""Or goes through false iterators, picking last"""
		assert Iter.Or(iter([0, None, []])) == []
		self.assertRaises(Exception, Iter.Or, self.falseerror_maker())


class FoldingTest(Iterators):
	"""Test folding operations"""
	def f(self, x, y): return x + y

	def testEmpty(self):
		"""Folds of empty iterators should produce defaults"""
		assert Iter.foldl(self.f, 23, self.empty()) == 23
		assert Iter.foldr(self.f, 32, self.empty()) == 32

	def testAddition(self):
		"""Use folds to sum lists"""
		assert Iter.foldl(self.f, 0, self.one_to_100()) == 5050
		assert Iter.foldr(self.f, 0, self.one_to_100()) == 5050

	def testLargeAddition(self):
		"""Folds on 10000 element iterators"""
		assert Iter.foldl(self.f, 0, iter(range(1, 10001))) == 50005000
		self.assertRaises(RuntimeError,
						  Iter.foldr, self.f, 0, iter(range(1, 10001)))

	def testLen(self):
		"""Use folds to calculate length of lists"""
		assert Iter.foldl(lambda x, y: x+1, 0, self.evens()) == 50
		assert Iter.foldr(lambda x, y: y+1, 0, self.odds()) == 50

class MultiplexTest(Iterators):
	def testSingle(self):
		"""Test multiplex single stream"""
		i_orig = self.one_to_100()
		i2_orig = self.one_to_100()
		i = Iter.multiplex(i_orig, 1)[0]
		assert Iter.equal(i, i2_orig)

	def testTrible(self):
		"""Test splitting iterator into three"""
		counter = [0]
		def ff(x): counter[0] += 1
		i_orig = self.one_to_100()
		i2_orig = self.one_to_100()
		i1, i2, i3 = Iter.multiplex(i_orig, 3, ff)
		assert Iter.equal(i1, i2)
		assert Iter.equal(i3, i2_orig)
		assert counter[0] == 100, counter

	def testDouble(self):
		"""Test splitting into two..."""
		i1, i2 = Iter.multiplex(self.one_to_100(), 2)
		assert Iter.equal(i1, self.one_to_100())
		assert Iter.equal(i2, self.one_to_100())


class ITRBadder(ITRBranch):
	def start_process(self, index):
		self.total = 0

	def end_process(self):
		if self.base_index:
			summand = self.base_index[-1]
			#print "Adding ", summand
			self.total += summand

	def branch_process(self, subinstance):
		#print "Adding subinstance ", subinstance.total
		self.total += subinstance.total

class ITRBadder2(ITRBranch):
	def start_process(self, index):
		self.total = 0

	def end_process(self):
		#print "Adding ", self.base_index
		self.total += reduce(lambda x,y: x+y, self.base_index, 0)

	def can_fast_process(self, index):
		if len(index) == 3: return 1
		else: return None

	def fast_process(self, index):
		self.total += index[0] + index[1] + index[2]

	def branch_process(self, subinstance):
		#print "Adding branch ", subinstance.total
		self.total += subinstance.total

class TreeReducerTest(unittest.TestCase):
	def setUp(self):
		self.i1 = [(), (1,), (2,), (3,)]
		self.i2 = [(0,), (0,1), (0,1,0), (0,1,1), (0,2), (0,2,1), (0,3)]

		self.i1a = [(), (1,)]
		self.i1b = [(2,), (3,)]
		self.i2a = [(0,), (0,1), (0,1,0)]
		self.i2b = [(0,1,1), (0,2)]
		self.i2c = [(0,2,1), (0,3)]

	def testTreeReducer(self):
		"""testing IterTreeReducer"""
		itm = IterTreeReducer(ITRBadder, [])
		for index in self.i1:
			val = itm(index)
			assert val, (val, index)
		itm.Finish()
		assert itm.root_branch.total == 6, itm.root_branch.total

		itm2 = IterTreeReducer(ITRBadder2, [])
		for index in self.i2:
			val = itm2(index)
			if index == (): assert not val
			else: assert val
		itm2.Finish()
		assert itm2.root_branch.total == 12, itm2.root_branch.total

	def testTreeReducerState(self):
		"""Test saving and recreation of an IterTreeReducer"""
		itm1a = IterTreeReducer(ITRBadder, [])
		for index in self.i1a:
			val = itm1a(index)
			assert val, index
		itm1b = pickle.loads(pickle.dumps(itm1a))
		for index in self.i1b:
			val = itm1b(index)
			assert val, index
		itm1b.Finish()
		assert itm1b.root_branch.total == 6, itm1b.root_branch.total

		itm2a = IterTreeReducer(ITRBadder2, [])
		for index in self.i2a:
			val = itm2a(index)
			if index == (): assert not val
			else: assert val
		itm2b = pickle.loads(pickle.dumps(itm2a))
		for index in self.i2b:
			val = itm2b(index)
			if index == (): assert not val
			else: assert val
		itm2c = pickle.loads(pickle.dumps(itm2b))
		for index in self.i2c:
			val = itm2c(index)
			if index == (): assert not val
			else: assert val
		itm2c.Finish()
		assert itm2c.root_branch.total == 12, itm2c.root_branch.total


if __name__ == "__main__": unittest.main()
