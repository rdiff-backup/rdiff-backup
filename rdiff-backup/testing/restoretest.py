import unittest

execfile("commontest.py")
rbexec("restore.py")


lc = Globals.local_connection

class RestoreTest(unittest.TestCase):
	"""Test Restore class"""
	prefix = "testfiles/restoretest/"
	def maketesttuples(self, basename):
		"""Make testing tuples from available files starting with prefix"""
		dirlist =  os.listdir(self.prefix)
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

		if rptarget.lstat(): rptarget.delete()
		for pair in tuples:
			print "Processing file " + pair[0].path
			rest_time = Time.stringtotime(pair[0].getinctime())
			Restore.RestoreFile(rest_time, rpbase, incs, rptarget)
			if not rptarget.lstat(): assert not pair[1].lstat()
			else:
				assert RPath.cmp(rptarget, pair[1]), \
					   "%s %s" % (rptarget.path, pair[1].path)
				assert RPath.cmp_attribs(rptarget, pair[1]), \
					   "%s %s" % (rptarget.path, pair[1].path)
				rptarget.delete()

	def testRestorefiles(self):
		"""Testing restoration of files one at a time"""
		map(self.restoreonefiletest, ["ocaml", "mf"])
		

if __name__ == "__main__": unittest.main()
