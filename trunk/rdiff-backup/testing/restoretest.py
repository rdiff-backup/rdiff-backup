import unittest

execfile("commontest.py")
rbexec("main.py")
Log.setverbosity(7)


lc = Globals.local_connection

class RestoreTest(unittest.TestCase):
	"""Test Restore class"""
	prefix = "testfiles/restoretest/"
	def maketesttuples(self, basename):
		"""Make testing tuples from available files starting with prefix

		tuples is a sorted (oldest to newest) list of pairs (rp1, rp2)
		where rp1 is an increment file and rp2 is the same but without
		the final extension.  incs is a list of all increment files.

		"""
		dirlist =  os.listdir(self.prefix)
		dirlist.sort()
		baselist = filter(lambda f: f.startswith(basename), dirlist)
		rps = map(lambda f: RPath(lc, self.prefix+f), baselist)
		incs = filter(lambda rp: rp.isincfile(), rps)
		tuples = map(lambda rp: (rp, RPath(lc, "%s.%s" %
										   (rp.getincbase().path,
											rp.getinctime()))),
					 incs)
		return tuples, incs

	def restoreonefiletest(self, basename):
		tuples, incs = self.maketesttuples(basename)
		rpbase = RPath(lc, self.prefix + basename)
		rptarget = RPath(lc, "testfiles/outfile")

		for pair in tuples:
			print "Processing file " + pair[0].path
			if rptarget.lstat(): rptarget.delete()
			rest_time = Time.stringtotime(pair[0].getinctime())
			rid = RestoreIncrementData((), rpbase, incs)
			rid.sortincseq(rest_time, 10000000000) # pick some really late time
			rcd = RestoreCombinedData(rid, rpbase, rptarget)
			rcd.RestoreFile()
			#sorted_incs = Restore.sortincseq(rest_time, incs)
			#Restore.RestoreFile(rest_time, rpbase, (), sorted_incs, rptarget)
			rptarget.setdata()
			if not rptarget.lstat(): assert not pair[1].lstat()
			elif not pair[1].lstat(): assert not rptarget.lstat()
			else:
				assert RPath.cmp(rptarget, pair[1]), \
					   "%s %s" % (rptarget.path, pair[1].path)
				assert RPath.cmp_attribs(rptarget, pair[1]), \
					   "%s %s" % (rptarget.path, pair[1].path)
				rptarget.delete()

	def testsortincseq(self):
		"""Test the Restore.sortincseq function

		This test just makes sure that it comes up with the right
		number of increments for each base name - given a list of
		increments, we should eventually get sorted sequences that
		end in each one (each one will be the last increment once).

		"""
		for basename in ['ocaml', 'mf']:
			tuples, unused = self.maketesttuples(basename)
			incs = [tuple[0] for tuple in tuples]

			# Now we need a time newer than any inc
			mirror_time = Time.stringtotime(incs[-1].getinctime()) + 10000

			for inc, incbase in tuples:
				assert inc.isincfile()
				inctime = Time.stringtotime(inc.getinctime())
				rid1 = RestoreIncrementData(basename, incbase, incs)
				rid2 = RestoreIncrementData(basename, incbase, incs)
				rid1.sortincseq(inctime, mirror_time)
				rid2.sortincseq(inctime + 5, mirror_time)
				assert rid1.inc_list, rid1.inc_list
				# Five seconds later shouldn't make a difference
				assert rid1.inc_list == rid2.inc_list, (rid1.inc_list,
														rid2.inc_list)
				# oldest increment should be exactly inctime
				ridtime = Time.stringtotime(rid1.inc_list[-1].getinctime())
				assert ridtime == inctime, (ridtime, inctime)
				

	def testRestorefiles(self):
		"""Testing restoration of files one at a time"""
		map(self.restoreonefiletest, ["ocaml", "mf"])

	def testRestoreDir(self):
		"""Test restoring from a real backup set"""
		Myrm("testfiles/output")
		InternalRestore(1, 1, "testfiles/restoretest3",
						"testfiles/output", 20000)

		src_rp = RPath(Globals.local_connection, "testfiles/increment2")
		restore_rp = RPath(Globals.local_connection, "testfiles/output")
		assert CompareRecursive(src_rp, restore_rp)

	def testRestoreCorrupt(self):
		"""Test restoring a partially corrupt archive

		The problem here is that a directory is missing from what is
		to be restored, but because the previous backup was aborted in
		the middle, some of the files in that directory weren't marked
		as .missing.

		"""
		Myrm("testfiles/output")
		InternalRestore(1, 1, "testfiles/restoretest4", "testfiles/output",
						10000)
		assert os.lstat("testfiles/output")
		self.assertRaises(OSError, os.lstat, "testfiles/output/tmp")
		self.assertRaises(OSError, os.lstat, "testfiles/output/rdiff-backup")

if __name__ == "__main__": unittest.main()
