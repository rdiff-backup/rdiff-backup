import unittest, os, re, time
from commontest import *
from rdiff_backup import log, rpath, restore, increment, Time, \
	 Rdiff, statistics

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

target = rpath.RPath(lc, "testfiles/out")
out2 = rpath.RPath(lc, "testfiles/out2")
out_gz = rpath.RPath(lc, "testfiles/out.gz")

Time.setprevtime(999424113)
prevtimestr = "2001-09-02T02:48:33-07:00"
t_pref = "testfiles/out.2001-09-02T02:48:33-07:00"
t_diff = "testfiles/out.2001-09-02T02:48:33-07:00.diff"

Globals.no_compression_regexp = \
			 re.compile(Globals.no_compression_regexp_string, re.I)

class inctest(unittest.TestCase):
	"""Test the incrementRP function"""
	def setUp(self):
		Globals.set('isbackup_writer',1)

	def check_time(self, rp):
		"""Make sure that rp is an inc file, and time is Time.prevtime"""
		assert rp.isincfile(), rp
		t = Time.stringtotime(rp.getinctime())
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
		assert rpath.cmp_attribs(diffrp, exec1)
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
		assert rpath.cmp_attribs(snap_rp2, rf)
		assert rpath.cmp(snap_rp2, rf)
		snap_rp2.delete()

	def testGzipsnapshot(self):
		"""Test making a compressed snapshot"""
		Globals.compression = 1
		rp = increment.Increment(rf, sym, target)
		self.check_time(rp)
		assert rpath.cmp_attribs(rp, sym)
		assert rpath.cmp(rp, sym)
		rp.delete()
		
		rp = increment.Increment(sym, rf, target)
		self.check_time(rp)
		assert rpath.cmp_attribs(rp, rf)
		assert rpath.cmpfileobj(rp.open("rb", 1), rf.open("rb"))
		assert rp.isinccompressed()
		rp.delete()

	def testdir(self):
		"""Test increment on dir"""
		rp = increment.Increment(sym, dir, target)
		self.check_time(rp)
		assert rp.lstat()
		assert target.isdir()
		assert rpath.cmp_attribs(dir, rp)
		assert rp.isreg()
		rp.delete()
		target.delete()

	def testDiff(self):
		"""Test making diffs"""
		Globals.compression = None
		rp = increment.Increment(rf, rf2, target)
		self.check_time(rp)
		assert rpath.cmp_attribs(rp, rf2)
		Rdiff.patch_action(rf, rp, out2).execute()
		assert rpath.cmp(rf2, out2)
		rp.delete()
		out2.delete()

	def testGzipDiff(self):
		"""Test making gzipped diffs"""
		Globals.compression = 1
		rp = increment.Increment(rf, rf2, target)
		self.check_time(rp)
		assert rpath.cmp_attribs(rp, rf2)
		Rdiff.patch_action(rf, rp, out2, delta_compressed = 1).execute()
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
		assert rpath.cmp_attribs(rp, out_gz)
		Rdiff.patch_action(rf, rp, out2).execute()
		assert rpath.cmp(out_gz, out2)
		rp.delete()
		out2.delete()
		out_gz.delete()

class inctest2(unittest.TestCase):
	"""Like inctest but contains more elaborate tests"""
	def stats_check_initial(self, s):
		"""Make sure stats object s compatible with initial mirroring

		A lot of the off by one stuff is because the root directory
		exists in the below examples.

		"""
		assert s.MirrorFiles == 1 or s.MirrorFiles == 0
		assert s.MirrorFileSize < 20000
		assert s.NewFiles <= s.SourceFiles <= s.NewFiles + 1
		assert s.NewFileSize <= s.SourceFileSize <= s.NewFileSize + 20000
		assert s.ChangedFiles == 1 or s.ChangedFiles == 0
		assert s.ChangedSourceSize < 20000
		assert s.ChangedMirrorSize < 20000
		assert s.DeletedFiles == s.DeletedFileSize == 0
		assert s.IncrementFileSize == 0

	def testStatistics(self):
		"""Test the writing of statistics

		The file sizes are approximate because the size of directories
		could change with different file systems...

		"""
		Globals.compression = 1
		Myrm("testfiles/output")
		InternalBackup(1, 1, "testfiles/stattest1", "testfiles/output")
		InternalBackup(1, 1, "testfiles/stattest2", "testfiles/output",
					   time.time()+1)

		rbdir = rpath.RPath(Globals.local_connection,
							"testfiles/output/rdiff-backup-data")

		#incs = Restore.get_inclist(rbdir.append("subdir").
		#						   append("directory_statistics"))
		#assert len(incs) == 2
		#s1 = StatsObj().read_stats_from_rp(incs[0]) # initial mirror stats
		#assert s1.SourceFiles == 2
		#assert 400000 < s1.SourceFileSize < 420000
		#self.stats_check_initial(s1)

		#subdir_stats = StatsObj().read_stats_from_rp(incs[1]) # increment stats
		#assert subdir_stats.SourceFiles == 2
		#assert 400000 < subdir_stats.SourceFileSize < 420000
		#assert subdir_stats.MirrorFiles == 2
		#assert 400000 < subdir_stats.MirrorFileSize < 420000
		#assert subdir_stats.NewFiles == subdir_stats.NewFileSize == 0
		#assert subdir_stats.DeletedFiles == subdir_stats.DeletedFileSize == 0
		#assert subdir_stats.ChangedFiles == 2
		#assert 400000 < subdir_stats.ChangedSourceSize < 420000
		#assert 400000 < subdir_stats.ChangedMirrorSize < 420000
		#assert 10 < subdir_stats.IncrementFileSize < 20000

		incs = restore.get_inclist(rbdir.append("session_statistics"))
		assert len(incs) == 2
		s2 = statistics.StatsObj().read_stats_from_rp(incs[0])
		assert s2.SourceFiles == 7
		assert 700000 < s2.SourceFileSize < 750000
		self.stats_check_initial(s2)

		root_stats = statistics.StatsObj().read_stats_from_rp(incs[1])
		assert root_stats.SourceFiles == 7, root_stats.SourceFiles
		assert 550000 < root_stats.SourceFileSize < 570000
		assert root_stats.MirrorFiles == 7
		assert 700000 < root_stats.MirrorFileSize < 750000
		assert root_stats.NewFiles == 1
		assert root_stats.NewFileSize == 0
		assert root_stats.DeletedFiles == 1
		assert root_stats.DeletedFileSize == 200000
		assert 3 <= root_stats.ChangedFiles <= 4, root_stats.ChangedFiles
		assert 450000 < root_stats.ChangedSourceSize < 470000
		assert 400000 < root_stats.ChangedMirrorSize < 420000
		assert 10 < root_stats.IncrementFileSize < 30000

if __name__ == '__main__': unittest.main()
