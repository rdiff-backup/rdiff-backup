import unittest
execfile("commontest.py")
rbexec("highlevel.py")


#Log.setverbosity(8)

class index:
	"""This is just used below to test the iter tree reducer"""
	def __init__(self, index):
		self.index = index


class RORPIterTest(unittest.TestCase):
	def setUp(self):
		self.lc = Globals.local_connection
		self.inc0rp = RPath(self.lc, "testfiles/empty", ())
		self.inc1rp = RPath(self.lc, "testfiles/inc-reg-perms1", ())
		self.inc2rp = RPath(self.lc, "testfiles/inc-reg-perms2", ())
		self.output = RPath(self.lc, "testfiles/output", ())

	def testCollateIterators(self):
		"""Test basic collating"""
		indicies = map(index, [0,1,2,3])
		helper = lambda i: indicies[i]

		makeiter1 = lambda: iter(indicies)
		makeiter2 = lambda: iter(map(helper, [0,1,3]))
		makeiter3 = lambda: iter(map(helper, [1,2]))

		outiter = RORPIter.CollateIterators(makeiter1(), makeiter2())
		assert Iter.equal(outiter,
						  iter([(indicies[0], indicies[0]),
								(indicies[1], indicies[1]),
								(indicies[2], None),
								(indicies[3], indicies[3])]))

		assert Iter.equal(RORPIter.CollateIterators(makeiter1(),
													makeiter2(),
													makeiter3()),
						  iter([(indicies[0], indicies[0], None),
								(indicies[1], indicies[1], indicies[1]),
								(indicies[2], None, indicies[2]),
								(indicies[3], indicies[3], None)]))

		assert Iter.equal(RORPIter.CollateIterators(makeiter1(), iter([])),
						  iter(map(lambda i: (i, None),
								   indicies)))
		assert Iter.equal(iter(map(lambda i: (i, None), indicies)),
						  RORPIter.CollateIterators(makeiter1(), iter([])))
		

	def testCombinedPatching(self):
		"""Combined signature, patch, and diff operations"""
		if self.output.lstat(): self.output.delete()

		def turninto(final_rp):
			sigfile = RORPIter.ToFile(RORPIter.GetSignatureIter(self.output))
			diff_file = RORPIter.ToFile(
				RORPIter.GetDiffIter(RORPIter.FromFile(sigfile),
									 RORPIter.IterateRPaths(final_rp)))
			RORPIter.PatchIter(self.output, RORPIter.FromFile(diff_file))

		turninto(self.inc1rp)
		assert self.compare_rps(self.output, self.inc1rp)
		turninto(self.inc2rp)
		assert self.compare_rps(self.output, self.inc2rp)

	def compare_rps(self, rp1, rp2):
		"""True if rp1 and rp2 are equal in some sense"""
		def RawIter(rp):
			"""Get raw iterator of file stats based an rp1"""
			return RORPIter.ToRaw(Iter.map(lambda rp2: rp2.getRORPath(),
										   RORPIter.IterateRPaths(rp)))
		ri1 = RawIter(rp1)
		ri2 = RawIter(rp2)
		try:
			rorp1 = ri1.next()
			rorp2 = ri2.next()
			assert rorp1 == rorp2, "%s %s" % (rorp1, rorp2)
		except StopIteration: pass
		return 1
	#	return Iter.equal(RawIter(rp1), RawIter(rp2))


class IndexedTupleTest(unittest.TestCase):
	def testTuple(self):
		"""Test indexed tuple"""
		i = IndexedTuple((1,2,3), ("a", "b"))
		i2 = IndexedTuple((), ("hello", "there", "how are you"))

		assert i[0] == "a"
		assert i[1] == "b"
		assert i2[1] == "there"
		assert len(i) == 2 and len(i2) == 3
		assert i2 < i, i2 < i

	def testTupleAssignment(self):
		a, b, c = IndexedTuple((), (1, 2, 3))
		assert a == 1
		assert b == 2
		assert c == 3

if __name__ == "__main__": unittest.main()

