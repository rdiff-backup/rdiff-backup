from __future__ import generators
import unittest, time, pickle
from commontest import *
from rdiff_backup import log, rpath, rorpiter, Globals, lazy

#Log.setverbosity(8)

class index:
	"""This is just used below to test the iter tree reducer"""
	def __init__(self, index):
		self.index = index


class RORPIterTest(unittest.TestCase):
	def setUp(self):
		self.lc = Globals.local_connection
		self.inc0rp = rpath.RPath(self.lc, "testfiles/empty", ())
		self.inc1rp = rpath.RPath(self.lc, "testfiles/inc-reg-perms1", ())
		self.inc2rp = rpath.RPath(self.lc, "testfiles/inc-reg-perms2", ())
		self.output = rpath.RPath(self.lc, "testfiles/output", ())

	def testCollateIterators(self):
		"""Test basic collating"""
		indicies = map(index, [0,1,2,3])
		helper = lambda i: indicies[i]

		makeiter1 = lambda: iter(indicies)
		makeiter2 = lambda: iter(map(helper, [0,1,3]))
		makeiter3 = lambda: iter(map(helper, [1,2]))

		outiter = rorpiter.CollateIterators(makeiter1(), makeiter2())
		assert lazy.Iter.equal(outiter,
							   iter([(indicies[0], indicies[0]),
									 (indicies[1], indicies[1]),
									 (indicies[2], None),
									 (indicies[3], indicies[3])]))

		assert lazy.Iter.equal(rorpiter.CollateIterators(makeiter1(),
														 makeiter2(),
														 makeiter3()),
							   iter([(indicies[0], indicies[0], None),
									 (indicies[1], indicies[1], indicies[1]),
									 (indicies[2], None, indicies[2]),
									 (indicies[3], indicies[3], None)]))

		assert lazy.Iter.equal(rorpiter.CollateIterators(makeiter1(),
														 iter([])),
							   iter(map(lambda i: (i, None),
										indicies)))
		assert lazy.Iter.equal(iter(map(lambda i: (i, None), indicies)),
							   rorpiter.CollateIterators(makeiter1(),
														 iter([])))
		

	def compare_no_times(self, src_rp, dest_rp):
		"""Compare but disregard directories attributes"""
		def equal(src_rorp, dest_rorp):
			return ((src_rorp.isdir() and dest_rorp.isdir()) or
					src_rorp == dest_rorp)

		return CompareRecursive(src_rp, dest_rp, None, equal)


class IndexedTupleTest(unittest.TestCase):
	def testTuple(self):
		"""Test indexed tuple"""
		i = rorpiter.IndexedTuple((1,2,3), ("a", "b"))
		i2 = rorpiter.IndexedTuple((), ("hello", "there", "how are you"))

		assert i[0] == "a"
		assert i[1] == "b"
		assert i2[1] == "there"
		assert len(i) == 2 and len(i2) == 3
		assert i2 < i, i2 < i

	def testTupleAssignment(self):
		a, b, c = rorpiter.IndexedTuple((), (1, 2, 3))
		assert a == 1
		assert b == 2
		assert c == 3


class DirHandlerTest(unittest.TestCase):
	made_test_dir = 0 # Set to 1 once we have made the test dir
	def make_test_dir(self):
		"""Make the test directory"""
		self.rootrp = RPath(Globals.local_connection, "testfiles/output")
		self.rootrp.delete()
		self.rootrp.mkdir()
		
		self.a = self.rootrp.append("a")
		self.b = self.rootrp.append("b")
		self.c = self.rootrp.append("c")
		self.a.mkdir()
		self.b.mkdir()
		self.b.chmod(0700)
		self.c.mkdir()
		self.c.chmod(0500) # No write permissions to c

		self.rootmtime = self.rootrp.getmtime()
		self.amtime = self.a.getmtime()
		self.bmtime = self.b.getmtime()
		self.cmtime = self.c.getmtime()

		self.made_test_dir = 1
		
	def test_times_and_writes(self):
		"""Test writing without disrupting times, and to unwriteable dir"""
		return
		self.make_test_dir()
		time.sleep(1) # make sure the mtimes would get updated otherwise
		DH = DirHandler(self.rootrp)

		new_a_rp = self.a.append("foo")
		DH(new_a_rp)
		new_a_rp.touch()

		DH(self.b)
		self.b.chmod(0751)
		new_b_rp = self.b.append("aoenuth")
		DH(new_b_rp)
		new_b_rp.touch()

		new_root_rp = self.rootrp.append("bb")
		DH(new_root_rp)
		new_root_rp.touch()

		new_c_rp = self.c.append("bar")
		DH(new_c_rp)
		new_c_rp.touch()
		DH.Finish()

		assert new_a_rp.lstat() and new_b_rp.lstat() and new_c_rp.lstat()
		self.a.setdata()
		self.b.setdata()
		self.c.setdata()
		assert self.a.getmtime() == self.amtime
		assert self.c.getmtime() == self.cmtime
		assert self.rootrp.getmtime() == self.rootmtime
		assert self.b.getperms() == 0751
		assert self.c.getperms() == 0500


class FillTest(unittest.TestCase):
	def test_fill_in(self):
		"""Test fill_in_iter"""
		rootrp = RPath(Globals.local_connection, "testfiles/output")
		def get_rpiter():
			for int_index in [(1,2), (1,3), (1,4),
							  (2,), (2,1),
							  (3,4,5), (3,6)]:
				index = tuple(map(lambda i: str(i), int_index))
				yield rootrp.new_index(index)

		filled_in = rorpiter.FillInIter(get_rpiter(), rootrp)
		rp_list = list(filled_in)
		index_list = map(lambda rp: tuple(map(int, rp.index)), rp_list)
		assert index_list == [(), (1,), (1,2), (1,3), (1,4),
							  (2,), (2,1),
							  (3,), (3,4), (3,4,5), (3,6)], index_list


class ITRBadder(rorpiter.ITRBranch):
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

class ITRBadder2(rorpiter.ITRBranch):
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
		itm = rorpiter.IterTreeReducer(ITRBadder, [])
		for index in self.i1:
			val = itm(index)
			assert val, (val, index)
		itm.Finish()
		assert itm.root_branch.total == 6, itm.root_branch.total

		itm2 = rorpiter.IterTreeReducer(ITRBadder2, [])
		for index in self.i2:
			val = itm2(index)
			if index == (): assert not val
			else: assert val
		itm2.Finish()
		assert itm2.root_branch.total == 12, itm2.root_branch.total

	def testTreeReducerState(self):
		"""Test saving and recreation of an IterTreeReducer"""
		itm1a = rorpiter.IterTreeReducer(ITRBadder, [])
		for index in self.i1a:
			val = itm1a(index)
			assert val, index
		itm1b = pickle.loads(pickle.dumps(itm1a))
		for index in self.i1b:
			val = itm1b(index)
			assert val, index
		itm1b.Finish()
		assert itm1b.root_branch.total == 6, itm1b.root_branch.total

		itm2a = rorpiter.IterTreeReducer(ITRBadder2, [])
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


class CacheIndexableTest(unittest.TestCase):
	def get_iter(self):
		"""Return iterator yielding indexed objects, add to dict d"""
		for i in range(100):
			it = rorpiter.IndexedTuple((i,), range(i))
			self.d[(i,)] = it
			yield it

	def testCaching(self):
		"""Test basic properties of CacheIndexable object"""
		self.d = {}
		
		ci = rorpiter.CacheIndexable(self.get_iter(), 3)
		val0 = ci.next()
		val1 = ci.next()
		val2 = ci.next()
		
		assert ci.get((1,)) == self.d[(1,)]
		assert ci.get((3,)) is None

		val3 = ci.next()
		val4 = ci.next()
		val5 = ci.next()

		assert ci.get((3,)) == self.d[(3,)]
		assert ci.get((4,)) == self.d[(4,)]
		assert ci.get((1,)) is None

	def testEqual(self):
		"""Make sure CI doesn't alter properties of underlying iter"""
		self.d = {}
		l1 = list(self.get_iter())
		l2 = list(rorpiter.CacheIndexable(iter(l1), 10))
		assert l1 == l2, (l1, l2)
							   

if __name__ == "__main__": unittest.main()

