from __future__ import generators
import unittest

execfile("commontest.py")
rbexec("lazy.py")

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


class index:
	"""This is just used below to test the iter tree reducer"""
	def __init__(self, index):
		self.index = index


class TreeReducerTest(unittest.TestCase):
	def setUp(self):
		self.i1 = iter(map(index, [(), (1,), (2,), (3,)]))
		self.i2 = iter(map(index, [(0,), (0,1), (0,1,0), (0,1,1),
								   (0,2), (0,2,1), (0,3)]))

		self.i1a = iter(map(index, [(), (1,)]))
		self.i1b = iter(map(index, [(2,), (3,)]))
		self.i2a = iter(map(index, [(0,), (0,1), (0,1,0)]))
		self.i2b = iter(map(index, [(0,1,1), (0,2)]))
		self.i2c = iter(map(index, [(0,2,1), (0,3)]))

	# The four following are used to make an ITR later
	def number_of_index(self, index_obj):
		if not index_obj.index: return 0
		else: return index_obj.index[-1]

	def sum_index(self, index_obj):
		return reduce(lambda x,y: x+y, index_obj.index, 0)

	def add2(self, x, y):
		#print "adding %d and %d" % (x,y)
		return x+y

	def add3(self, x,y,z):
		#print "ignoring %s, adding %d and %d" % (x,y,z)
		return y+z

	def testTreeReducer(self):
		"""testing IterTreeReducer"""
		itm = IterTreeReducer(self.number_of_index, self.add2, 0, self.add3)
		for elem in self.i1:
			val = itm(elem)
			assert val, elem.index
		itm.calculate_final_val()
		assert itm.getresult() == 6, itm.getresult()

		itm2 = IterTreeReducer(self.sum_index, self.add2, 0, self.add3)
		for elem in self.i2:
			val = itm2(elem)
			if elem.index == (): assert not val
			else: assert val
		assert itm2.getresult() == 12, itm2.getresult()

	def testTreeReducerState(self):
		"""Test saving and recreation of an IterTreeReducer"""
		itm1a = IterTreeReducer(self.number_of_index, self.add2, 0, self.add3)
		for elem in self.i1a:
			val = itm1a(elem)
			assert val, elem.index
		itm1b = IterTreeReducer(self.number_of_index, self.add2, 0, self.add3,
								itm1a.getstate())
		for elem in self.i1b:
			val = itm1b(elem)
			assert val, elem.index
		itm1b.calculate_final_val()
		assert itm1b.getresult() == 6, itm1b.getresult()

		itm2a = IterTreeReducer(self.sum_index, self.add2, 0, self.add3)
		for elem in self.i2a:
			val = itm2a(elem)
			if elem.index == (): assert not val
			else: assert val
		itm2b = IterTreeReducer(self.sum_index, self.add2, 0, self.add3,
								itm2a.getstate())
		for elem in self.i2b:
			val = itm2b(elem)
			if elem.index == (): assert not val
			else: assert val
		itm2c = IterTreeReducer(self.sum_index, self.add2, 0, self.add3,
								itm2b.getstate())
		for elem in self.i2c:
			val = itm2c(elem)
			if elem.index == (): assert not val
			else: assert val
		assert itm2c.getresult() == 12, itm2c.getresult()

	def testTreeReducer2(self):
		"""Another test of the tree reducer"""
		assert Iter.len(self.i1) == 4

		hit_021_02 = [None, None]
		def helper(indexobj, elem_init, branch_result):
			if indexobj.index == (0,2):
				assert hit_021_02[0]
				hit_021_02[1] = 1
			elif indexobj.index == (0,2,1):
				assert not hit_021_02[1]
				hit_021_02[0] = 1
			return None
		itm = IterTreeReducer(lambda x: None, lambda x,y: None, None, helper)

		for elem in self.i2: itm(elem)
		itm.getresult()
		assert hit_021_02 == [1,1]
		


if __name__ == "__main__": unittest.main()
