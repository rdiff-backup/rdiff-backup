import unittest, os, re, time
from commontest import *
from rdiff_backup import log, rpath, increment, Time, Rdiff, statistics

lc = Globals.local_connection
Globals.change_source_perms = 1
Log.setverbosity(3)

def getrp(ending):
	return rpath.RPath(lc, "testfiles/various_file_types/" + ending)

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

target = rpath.RPath(lc, "testfiles/output/out")
out2 = rpath.RPath(lc, "testfiles/output/out2")
out_gz = rpath.RPath(lc, "testfiles/output/out.gz")

Time.setcurtime(1000000000)
Time.setprevtime(999424113)
prevtimestr = "2001-09-02T02:48:33-07:00"
t_pref = "testfiles/output/out.2001-09-02T02:48:33-07:00"
t_diff = "testfiles/output/out.2001-09-02T02:48:33-07:00.diff"

Globals.no_compression_regexp = \
			 re.compile(Globals.no_compression_regexp_string, re.I)

class inctest(unittest.TestCase):
	"""Test the incrementRP function"""
	def setUp(self):
		Globals.set('isbackup_writer',1)
		MakeOutputDir()

	def check_time(self, rp):
		"""Make sure that rp is an inc file, and time is Time.prevtime"""
		assert rp.isincfile(), rp
		t = rp.getinctime()
		assert t == Time.prevtime, (t, Time.prevtime)

	def testreg(self):
		"""Test increment of regular files"""
		Globals.compression = None
		target.setdata()
		if target.lstat(): target.delete()
		rpd = rpath.RPath(lc, t_diff)
		if rpd.lstat(): rpd.delete()

		diffrp = increment.Increment(rf, exec1, target)
		assert diffrp.isreg(), diffrp
		assert diffrp.equal_verbose(exec1, check_index = 0, compare_size = 0)
		self.check_time(diffrp)
		assert diffrp.getinctype() == 'diff', diffrp.getinctype()
		diffrp.delete()

	def testmissing(self):
		"""Test creation of missing files"""
		missing_rp = increment.Increment(rf, nothing, target)
		self.check_time(missing_rp)
		assert missing_rp.getinctype() == 'missing'
		missing_rp.delete()

	def testsnapshot(self):
		"""Test making of a snapshot"""
		Globals.compression = None
		snap_rp = increment.Increment(rf, sym, target)
		self.check_time(snap_rp)
		assert rpath.cmp_attribs(snap_rp, sym)
		assert rpath.cmp(snap_rp, sym)
		snap_rp.delete()

		snap_rp2 = increment.Increment(sym, rf, target)
		self.check_time(snap_rp2)
		assert snap_rp2.equal_verbose(rf, check_index = 0)
		assert rpath.cmp(snap_rp2, rf)
		snap_rp2.delete()

	def testGzipsnapshot(self):
		"""Test making a compressed snapshot"""
		Globals.compression = 1
		rp = increment.Increment(rf, sym, target)
		self.check_time(rp)
		assert rp.equal_verbose(sym, check_index = 0, compare_size = 0)
		assert rpath.cmp(rp, sym)
		rp.delete()
		
		rp = increment.Increment(sym, rf, target)
		self.check_time(rp)
		assert rp.equal_verbose(rf, check_index = 0, compare_size = 0)
		assert rpath.cmpfileobj(rp.open("rb", 1), rf.open("rb"))
		assert rp.isinccompressed()
		rp.delete()

	def testdir(self):
		"""Test increment on dir"""
		rp = increment.Increment(sym, dir, target)
		self.check_time(rp)
		assert rp.lstat()
		assert target.isdir()
		assert dir.equal_verbose(rp, check_index = 0,
								 compare_size = 0, compare_type = 0)
		assert rp.isreg()
		rp.delete()
		target.delete()

	def testDiff(self):
		"""Test making diffs"""
		Globals.compression = None
		rp = increment.Increment(rf, rf2, target)
		self.check_time(rp)
		assert rp.equal_verbose(rf2, check_index = 0, compare_size = 0)
		Rdiff.patch_local(rf, rp, out2)
		assert rpath.cmp(rf2, out2)
		rp.delete()
		out2.delete()

	def testGzipDiff(self):
		"""Test making gzipped diffs"""
		Globals.compression = 1
		rp = increment.Increment(rf, rf2, target)
		self.check_time(rp)
		assert rp.equal_verbose(rf2, check_index = 0, compare_size = 0)
		Rdiff.patch_local(rf, rp, out2, delta_compressed = 1)
		assert rpath.cmp(rf2, out2)
		rp.delete()
		out2.delete()

	def testGzipRegexp(self):
		"""Here a .gz file shouldn't be compressed"""
		Globals.compression = 1
		rpath.copy(rf, out_gz)
		assert out_gz.lstat()

		rp = increment.Increment(rf, out_gz, target)
		self.check_time(rp)
		assert rp.equal_verbose(out_gz, check_index = 0, compare_size = 0)
		Rdiff.patch_local(rf, rp, out2)
		assert rpath.cmp(out_gz, out2)
		rp.delete()
		out2.delete()
		out_gz.delete()

if __name__ == '__main__': unittest.main()
