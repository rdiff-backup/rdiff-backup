import unittest, os

execfile("commontest.py")
rbexec("main.py")


lc = Globals.local_connection
Globals.change_source_perms = 1
Log.setverbosity(4)

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

class inctest2(unittest.TestCase):
	"""Like inctest but contains more elaborate tests"""
	def testStatistics(self):
		"""Test the writing of statistics

		The file sizes are approximate because the size of directories
		could change with different file systems...

		"""
		Globals.compression = 1
		Myrm("testfiles/output")
		InternalBackup(1, 1, "testfiles/stattest1", "testfiles/output")
		InternalBackup(1, 1, "testfiles/stattest2", "testfiles/output")

		inc_base = RPath(Globals.local_connection,
						 "testfiles/output/rdiff-backup-data/increments")

		incs = Restore.get_inclist(inc_base.append("subdir").
								   append("directory_statistics"))
		assert len(incs) == 1
		subdir_stats = self.parse_statistics(incs[0])
		assert subdir_stats.total_files == 2, subdir_stats.total_files
		assert 350000 < subdir_stats.total_file_size < 450000, \
			   subdir_stats.total_file_size
		assert subdir_stats.changed_files == 2, subdir_stats.changed_files
		assert 350000 < subdir_stats.changed_file_size < 450000, \
			   subdir_stats.changed_file_size
		assert 10 < subdir_stats.increment_file_size < 20000, \
			   subdir_stats.increment_file_size

		incs = Restore.get_inclist(inc_base.append("directory_statistics"))
		assert len(incs) == 1
		root_stats = self.parse_statistics(incs[0])
		assert root_stats.total_files == 6, root_stats.total_files
		assert 650000 < root_stats.total_file_size < 750000, \
			   root_stats.total_file_size
		assert root_stats.changed_files == 4, root_stats.changed_files
		assert 550000 < root_stats.changed_file_size < 650000, \
			   root_stats.changed_file_size
		assert 10 < root_stats.increment_file_size < 20000, \
			   root_stats.increment_file_size

	def parse_statistics(self, statrp):
		"""Return StatObj from given statrp"""
		assert statrp.isincfile() and statrp.getinctype() == "data"
		s = StatObj()
		fp = statrp.open("r")
		for line in fp:
			lsplit = line.split()
			assert len(lsplit) == 2
			field, num = lsplit[0], long(lsplit[1])
			if field == "TotalFiles": s.total_files = num
			elif field == "TotalFileSize": s.total_file_size = num
			elif field == "ChangedFiles": s.changed_files = num
			elif field == "ChangedFileSize": s.changed_file_size = num
			elif field == "IncrementFileSize": s.increment_file_size = num
			else: assert None, "Unrecognized field %s" % (field,)
		assert not fp.close()
		return s


class StatObj:
	"""Just hold various statistics"""
	total_files = 0
	total_file_size = 0
	changed_files = 0
	changed_file_size = 0
	increment_file_size = 0
	

if __name__ == '__main__': unittest.main()
