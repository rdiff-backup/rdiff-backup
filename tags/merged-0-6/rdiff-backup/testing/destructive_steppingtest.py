from __future__ import generators
import unittest
execfile("commontest.py")
rbexec("destructive_stepping.py")



class DSTest(unittest.TestCase):
	def setUp(self):
		self.lc = Globals.local_connection
		self.noperms = RPath(self.lc, "testfiles/noperms")
		Globals.change_source_perms = 1
		self.iteration_dir = RPath(self.lc, "testfiles/iteration-test")

	def testDSIter(self):
		"""Testing destructive stepping iterator from baserp"""
		for i in range(2):
			ds_iter = DestructiveStepping.Iterate_with_Finalizer(
				self.noperms, 1)
			noperms = ds_iter.next()
			assert noperms.isdir() and noperms.getperms() == 0

			bar = ds_iter.next()
			assert bar.isreg() and bar.getperms() == 0
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

	def testIterate_from(self):
		"""Tests basic iteration by Iterate_from"""
		iter = DestructiveStepping.Iterate_from(self.iteration_dir, 1)
		l = []
		for rp in iter: l.append(rp.index)
		assert l == [(),
					 ('1',),
					 ('2',),
					 ('3',), ('3','2'), ('3','3'),
					 ('4',),
					 ('5',), ('5','1'), ('5','2'), ('5','2','1'),
					 ('6',), ('6','3'),
                             ('6','3','1'), ('6','3','2'), ('6','4'),
					 ('7',)], l

	def testIterate_from_index(self):
		"""Test iteration from a given index"""
		iter = DestructiveStepping.Iterate_from(self.iteration_dir, 1, ('3',))
		l = []
		for rp in iter: l.append(rp.index)
		assert l == [('3','2'), ('3','3'),
					 ('4',),
					 ('5',), ('5','1'), ('5','2'), ('5','2','1'),
					 ('6',), ('6','3'),
					         ('6','3','1'), ('6','3','2'), ('6','4'),
					 ('7',)], l
		iter = DestructiveStepping.Iterate_from(self.iteration_dir, 1,
												('6','3'))
		l = []
		for rp in iter: l.append(rp.index)
		assert l == [('6','3','1'), ('6','3','2'), ('6', '4'),
					 ('7',)], l

if __name__ == "__main__": unittest.main()
