import unittest, os
execfile("commontest.py")
rbexec("main.py")

"""Root tests

This is mainly a copy of regressiontest.py, but contains the two tests
that are meant to be run as root.
"""

Globals.set('change_source_perms', 1)
Globals.counter = 0
Log.setverbosity(4)

class RootTest(unittest.TestCase):
	dirlist1 = ["testfiles/root", "testfiles/noperms", "testfiles/increment4"]
	dirlist2 = ["testfiles/increment4", "testfiles/root",
				"testfiles/increment1"]
	def testLocal1(self): BackupRestoreSeries(1, 1, self.dirlist1)
	def testLocal2(self): BackupRestoreSeries(1, 1, self.dirlist2)
	def testRemote(self): BackupRestoreSeries(None, None, self.dirlist1)

	def tearDown(self):
		os.system(MiscDir + "/myrm testfiles/output testfiles/rest_out")


if __name__ == "__main__": unittest.main()
