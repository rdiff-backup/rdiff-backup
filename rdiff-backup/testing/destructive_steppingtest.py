from __future__ import generators
import unittest
from commontest import *
from rdiff_backup.rpath import *
from rdiff_backup.selection import *
from rdiff_backup import Globals

Log.setverbosity(4)

class DSTest(unittest.TestCase):
	def setUp(self):
		self.lc = Globals.local_connection
		self.noperms = RPath(self.lc, "testfiles/noperms")
		Globals.change_source_perms = 1
		self.iteration_dir = RPath(self.lc, "testfiles/iteration-test")

	def testDSIter(self):
		"""Testing destructive stepping iterator from baserp"""
		for i in range(2):
			sel = Select(DSRPath(1, self.noperms)).set_iter()
			ds_iter = sel.iterate_with_finalizer()
			noperms = ds_iter.next()
			assert noperms.isdir() and noperms.getperms() == 0, \
				   (noperms.isdir(), noperms.getperms())

			bar = ds_iter.next()
			assert bar.isreg() and bar.getperms() == 0, \
				   "%s %s" % (bar.isreg(), bar.getperms())
			barbuf = bar.open("rb").read()
			assert len(barbuf) > 0
			
			foo = ds_iter.next()
			assert foo.isreg() and foo.getperms() == 0
			assert foo.getmtime() < 1000300000

			fuz = ds_iter.next()
			assert fuz.isreg() and fuz.getperms() == 0200
			fuzbuf = fuz.open("rb").read()
			assert len(fuzbuf) > 0

			self.assertRaises(StopIteration, ds_iter.next)

if __name__ == "__main__": unittest.main()
