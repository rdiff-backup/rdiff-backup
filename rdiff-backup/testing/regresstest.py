"""regresstest - test the regress module.

Not to be confused with the regression tests.

"""

import unittest
from commontest import *
from rdiff_backup import regress

Log.setverbosity(7)

class RegressTest(unittest.TestCase):
	regress_rp1 = rpath.RPath(Globals.local_connection,
							  "testfiles/regress_output1")
	regress_rp2 = rpath.RPath(Globals.local_connection,
							  "testfiles/regress_output2")
	
	def make_output(self, level):
		"""Set up two rdiff-backup destination dir of level and level+1

		testfiles/regress_output1 will be a copy of
		testfiles/increment1 through testfiles/increment{level}

		testfiles/regress_output2 will have all everything backed up
		in testfiles/regress_output1 + testfiles/increment{level+1}.

		The time of each increment will be 10000*level.

		"""
		assert 1 <= level <= 3
		if self.regress_rp1.lstat(): Myrm(self.regress_rp1.path)
		if self.regress_rp2.lstat(): Myrm(self.regress_rp2.path)

		# Make regress_output1
		Log("Making %s" % (self.regress_rp1.path,), 4)
		for i in range(1, level+1):
			rdiff_backup(1, 1,
						 "testfiles/increment%s" % (i,),
						 self.regress_rp1.path,
						 current_time = 10000*i)

		# Now make regress_output2
		Log("Making %s" % (self.regress_rp2.path,), 4)
		assert not os.system("cp -a %s %s" %
							 (self.regress_rp1.path, self.regress_rp2.path))
		rdiff_backup(1, 1,
					 "testfiles/increment%s" % (level+1),
					 self.regress_rp2.path,
					 current_time = 10000*(level+1))
		self.regress_rp1.setdata()
		self.regress_rp2.setdata()

	def test_full(self):
		"""Test regressing a full directory to older state

		Make two directories, one with one more backup in it.  Then
		regress the bigger one, and then make sure they compare the
		same.

		"""
		for level in range(1, 4):
			self.make_output(level)
			regress.regress_time = 10000*level
			regress.unsuccessful_backup_time = 10000*(level+1)
			regress.time_override_mode = 1
			Globals.rbdir = self.regress_rp2.append_path("rdiff-backup-data")
			Log("######### Beginning regress ###########", 5)
			regress.Regress(self.regress_rp2)

			assert CompareRecursive(self.regress_rp1, self.regress_rp2,
									exclude_rbdir = 0)


if __name__ == "__main__": unittest.main()
