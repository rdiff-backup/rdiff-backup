import unittest, os

execfile("commontest.py")
rbexec("increment.py")


lc = Globals.local_connection
Globals.change_source_perms = 1
Log.setverbosity(7)

def getrp(ending):
	return RPath(lc, "testfiles/various_file_types/" + ending)

rf = getrp("regular_file")
exec1 = getrp("executable")
exec2 = getrp("executable2")
sig = getrp("regular_file.sig")
hl1, hl2 = map(getrp, ["two_hardlinked_files1", "two_hardlinked_files2"])
test = getrp("test")
dir = getrp(".")
sym = getrp("symbolic_link")
nothing = getrp("nothing")

target = RPath(lc, "testfiles/out")

Time.setprevtime(999424113.24931)
prevtimestr = "2001-09-02T02:48:33-07:00"
t_pref = "testfiles/out.2001-09-02T02:48:33-07:00"
t_diff = "testfiles/out.2001-09-02T02:48:33-07:00.diff"

class inctest(unittest.TestCase):
	"""Test the incrementRP function"""
	def setUp(self):
		pass

	def testreg(self):
		"""Test increment of regular files"""
		Inc.Increment(rf, exec1, target)
		rpd = RPath(lc, t_diff)
		assert rpd.isreg()
		assert RPath.cmp_attribs(rpd, exec1)
		rpd.delete()

	def testmissing(self):
		"""Test creation of missing files"""
		Inc.Increment(rf, nothing, target)
		rp = RPath(lc, t_pref + ".missing")
		assert rp.lstat()
		rp.delete()

	def testsnapshot(self):
		"""Test making of a snapshot"""
		Inc.Increment(rf, sym, target)
		rp = RPath(lc, t_pref + ".snapshot")
		assert rp.lstat()
		assert RPath.cmp_attribs(rp, sym)
		assert RPath.cmp(rp, sym)
		rp.delete()

		Inc.Increment(sym, rf, target)
		rp = RPath(lc, t_pref + ".snapshot")
		assert rp.lstat()
		assert RPath.cmp_attribs(rp, rf)
		assert RPath.cmp(rp, rf)
		rp.delete()

	def testdir(self):
		"""Test increment on dir"""
		Inc.Increment(sym, dir, target)
		rp = RPath(lc, t_pref + ".dir")
		rp2 = RPath(lc, t_pref)
		assert rp.lstat()
		assert target.isdir()
		assert RPath.cmp_attribs(dir, rp)
		assert rp.isreg()
		rp.delete()
		target.delete()


inc1rp = RPath(lc, "testfiles/increment1")
inc2rp = RPath(lc, "testfiles/increment2")
inc3rp = RPath(lc, "testfiles/increment3")
inc4rp = RPath(lc, "testfiles/increment4")
rpout = RPath(lc, "testfiles/output")

#class IncTreeTest(unittest.TestCase):
#	def setUp(self):
#		os.system("./myrm testfiles/output*")

#	def testinctree(self):
#		"""Test tree incrementing"""
#		rpt1 = RPTriple(inc2rp, inc1rp, rpout)
#		rpt2 = RPTriple(inc3rp, inc2rp, rpout)
#		rpt3 = RPTriple(inc4rp, inc3rp, rpout)
#		for rpt in [rpt1, rpt2, rpt3]:
#			Time.setprevtime(Time.prevtime + 10000)
#			Inc.IncrementTTree(TripleTree(rpt).destructive_stepping())
#		Time.setprevtime(999424113.24931)

if __name__ == "__main__": unittest.main()
