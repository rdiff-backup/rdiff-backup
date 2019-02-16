import unittest
from commontest import *
from rdiff_backup.rlist import *

class BasicObject:
	"""The simplest object that can be used with RList"""
	def __init__(self, i):
		self.index = i
		self.data = "This is object # %d" % i

	def __eq__(self, other):
		return self.index == other.index and self.data == other.data

l1_pre = [x for x in range(1, 1001) if x != 342 and not x in [650, 651, 652] and
				x != 911 and x != 987]
l2_pre = [x for x in range(1, 1001) if not x in [222, 223, 224, 225] and x != 950
				and x != 999 and x != 444]

l1 = list(map(BasicObject, l1_pre))
l2 = list(map(BasicObject, l2_pre))
combined = list(map(BasicObject, list(range(1, 1001))))

def lmaphelper2(xxx_todo_changeme):
	"""Return difference triple to say that index x only in list # i"""
	(x, i) = xxx_todo_changeme
	if i == 1: return (BasicObject(x), None)
	elif i == 2: return (None, BasicObject(x))
	else: assert 0, "Invalid parameter %s for i" % i

difference1 = list(map(lmaphelper2, [(222, 1), (223, 1), (224, 1), (225, 1),
								(342, 2), (444, 1), (650, 2), (651, 2),
								(652, 2), (911, 2), (950, 1), (987, 2),
								(999, 1)]))
difference2 = [(a_b[1], a_b[0]) for a_b in difference1]

def comparelists(l1, l2):
	print(len(l1), len(l2))
	for i in range(len(l1)):
		if l1[i] != l2[i]: print(l1[i], l2[i])
	print(l1)
	print(l2)



class RListTest(unittest.TestCase):
	def setUp(self):
		"""Make signatures, deltas"""
		self.l1_sig = RList.Signatures(l1)
		self.l2_sig = RList.Signatures(l2)
		self.l1_to_l2_diff = RList.Deltas(self.l1_sig, l2)
		self.l2_to_l1_diff = RList.Deltas(self.l2_sig, l1)

#		for d in makedeltas(makesigs(l2ci(l1)), l2ci(l2)):
#			print d.min, d.max
#			print d.elemlist

	def testPatching(self):
		"""Test to make sure each list can be reconstructed from other"""
		newlist = list(RList.Patch(l1, RList.Deltas(RList.Signatures(l1),
													 l2)))
		assert l2 == newlist
		newlist = list(RList.Patch(l2, RList.Deltas(RList.Signatures(l2),
													 l1)))
		assert l1 == newlist

	def testDifference(self):
		"""Difference between lists correctly identified"""
		diff = list(RList.Dissimilar(l1, RList.Deltas(RList.Signatures(l1),
													  l2)))
		assert diff == difference1
		diff = list(RList.Dissimilar(l2, RList.Deltas(RList.Signatures(l2),
													  l1)))
		assert diff == difference2



class CachingIterTest(unittest.TestCase):
	"""Test the Caching Iter object"""
	def testNormalIter(self):
		"""Make sure it can act like a normal iterator"""
		ci = CachingIter(iter(list(range(10))))
		for i in range(10): assert i == next(ci)
		self.assertRaises(StopIteration, ci.__next__)

	def testPushing(self):
		"""Pushing extra objects onto the iterator"""
		ci = CachingIter(iter(list(range(10))))
		ci.push(12)
		ci.push(11)
		assert next(ci) == 11
		assert next(ci) == 12
		assert next(ci) == 0
		ci.push(10)
		assert next(ci) == 10
		
		
if __name__ == "__main__": unittest.main()
