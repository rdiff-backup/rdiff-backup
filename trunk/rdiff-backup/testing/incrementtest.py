import unittest, os

execfile("commontest.py")
rbexec("increment.py")


lc = Globals.local_connection
Globals.change_source_perms = 1
Log.setverbosity(7)

def getrp(ending):
	return RPath(lc, "testfiles/various_file_types/" + ending)

rf = getrp("regular_file")
rf2 = getrp("two_hardlinked_files1")
exec1 = getrp("executable")
exec2 = getrp("executable2")
sig = getrp("regular_file.sig")
hl1, hl2 = map(getrp, ["two_hardlinked_files1", "two_hardlinked_files2"])
test = getrp("test")
dir = getrp(".")
sym = getrp("symbolic_link")
nothing = getrp("nothing")

target = RPath(lc, "testfiles/out")
out2 = RPath(lc, "testfiles/out2")
out_gz = RPath(lc, "testfiles/out.gz")

Time.setprevtime(999424113.24931)
prevtimestr = "2001-09-02T02:48:33-07:00"
t_pref = "testfiles/out.2001-09-02T02:48:33-07:00"
t_diff = "testfiles/out.2001-09-02T02:48:33-07:00.diff"

Globals.no_compression_regexp = \
			 re.compile(Globals.no_compression_regexp_string, re.I)

class inctest(unittest.TestCase):
	"""Test the incrementRP function"""
	def setUp(self):
		Globals.set('isbackup_writer',1)

	def testreg(self):
		"""Test increment of regular files"""
		Globals.compression = None
		target.setdata()
		if target.lstat(): target.delete()
		rpd = RPath(lc, t_diff)
		if rpd.lstat(): rpd.delete()

		Inc.Increment(rf, exec1, target)
		rpd.setdata()
		assert rpd.isreg(), rpd
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
		Globals.compression = None
		rp = RPath(lc, t_pref + ".snapshot")
		if rp.lstat(): rp.delete()
		Inc.Increment(rf, sym, target)
		rp.setdata()
		assert rp.lstat()
		assert RPath.cmp_attribs(rp, sym)
		assert RPath.cmp(rp, sym)
		rp.delete()

		rp = RPath(lc, t_pref + ".snapshot")
		if rp.lstat(): rp.delete()
		Inc.Increment(sym, rf, target)
		rp.setdata()
		assert rp.lstat()
		assert RPath.cmp_attribs(rp, rf)
		assert RPath.cmp(rp, rf)
		rp.delete()

	def testGzipsnapshot(self):
		"""Test making a compressed snapshot"""
		Globals.compression = 1
		rp = RPath(lc, t_pref + ".snapshot")
		if rp.lstat(): rp.delete()
		Inc.Increment(rf, sym, target)
		rp.setdata()
		assert rp.lstat()
		assert RPath.cmp_attribs(rp, sym)
		assert RPath.cmp(rp, sym)
		rp.delete()
		
		rp = RPath(lc, t_pref + ".snapshot.gz")
		if rp.lstat(): rp.delete()
		Inc.Increment(sym, rf, target)
		rp.setdata()

		assert rp.lstat()
		assert RPath.cmp_attribs(rp, rf)
		assert RPath.cmpfileobj(rp.open("rb", 1), rf.open("rb"))
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

	def testDiff(self):
		"""Test making diffs"""
		Globals.compression = None
		rp = RPath(lc, t_pref + '.diff')
		if rp.lstat(): rp.delete()
		Inc.Increment(rf, rf2, target)
		rp.setdata()
		assert rp.lstat()
		assert RPath.cmp_attribs(rp, rf2)
		Rdiff.patch_action(rf, rp, out2).execute()
		assert RPath.cmp(rf2, out2)
		rp.delete()
		out2.delete()

	def testGzipDiff(self):
		"""Test making gzipped diffs"""
		Globals.compression = 1
		rp = RPath(lc, t_pref + '.diff.gz')
		if rp.lstat(): rp.delete()
		Inc.Increment(rf, rf2, target)
		rp.setdata()
		assert rp.lstat()
		assert RPath.cmp_attribs(rp, rf2)
		Rdiff.patch_action(rf, rp, out2, delta_compressed = 1).execute()
		assert RPath.cmp(rf2, out2)
		rp.delete()
		out2.delete()

	def testGzipRegexp(self):
		"""Here a .gz file shouldn't be compressed"""
		Globals.compression = 1
		RPath.copy(rf, out_gz)
		assert out_gz.lstat()

		rp = RPath(lc, t_pref + '.diff')
		if rp.lstat(): rp.delete()

		Inc.Increment(rf, out_gz, target)
		rp.setdata()
		assert rp.lstat()
		assert RPath.cmp_attribs(rp, out_gz)
		Rdiff.patch_action(rf, rp, out2).execute()
		assert RPath.cmp(out_gz, out2)
		rp.delete()
		out2.delete()
		out_gz.delete()

if __name__ == '__main__': unittest.main()
