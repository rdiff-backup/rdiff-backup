import unittest, errno
from commontest import *
from rdiff_backup import rpath, longname, Globals, regress

max_len = 255

class LongNameTest(unittest.TestCase):
	"""Test the longname module"""
	root_rp = rpath.RPath(Globals.local_connection, "testfiles")
	out_rp = root_rp.append_path('output')

	def test_length_limit(self):
		"""Confirm that length limit is max_len

		Some of these tests depend on the length being at most
		max_len, so check to make sure it's accurate.

		"""
		Myrm(self.out_rp.path)
		self.out_rp.mkdir()

		really_long = self.out_rp.append('a'*max_len)
		really_long.touch()

		try: too_long = self.out_rp.append("a"*(max_len+1))
		except EnvironmentError, e:
			assert errno.errorcode[e[0]] == 'ENAMETOOLONG', e
		else: assert 0, "File made successfully with length " + str(max_len+1)

	def make_input_dirs(self):
		"""Create two input directories with long filename(s) in them"""
		dir1 = self.root_rp.append('longname1')
		dir2 = self.root_rp.append('longname2')
		Myrm(dir1.path)
		Myrm(dir2.path)

		dir1.mkdir()
		rp11 = dir1.append('A'*max_len)
		rp11.write_string('foobar')
		rp12 = dir1.append('B'*max_len)
		rp12.mkdir()
		rp121 = rp12.append('C'*max_len)
		rp121.touch()

		dir2.mkdir()
		rp21 = dir2.append('A'*max_len)
		rp21.write_string('Hello, world')
		rp22 = dir2.append('D'*max_len)
		rp22.mkdir()
		rp221 = rp22.append('C'*max_len)
		rp221.touch()

		return dir1, dir2

	def check_dir1(self, dirrp):
		"""Make sure dirrp looks like dir1"""
		rp1 = dirrp.append('A'*max_len)
		assert rp1.get_data() == 'foobar', "data doesn't match"
		rp2 = dirrp.append('B'*max_len)
		assert rp2.isdir(), rp2
		rp21 = rp2.append('C'*max_len)
		assert rp21.isreg(), rp21

	def check_dir2(self, dirrp):
		"""Make sure dirrp looks like dir2"""
		rp1 = dirrp.append('A'*max_len)
		assert rp1.get_data() == 'Hello, world', "data doesn't match"
		rp2 = dirrp.append('D'*max_len)
		assert rp2.isdir(), rp2
		rp21 = rp2.append('C'*max_len)
		assert rp21.isreg(), rp21

	def generic_test(self, inlocal, outlocal, extra_args, compare_back):
		"""Used for some of the tests below"""
		in1, in2 = self.make_input_dirs()
		Myrm(self.out_rp.path)
		restore_dir = self.root_rp.append('longname_out')

		# Test backing up
		rdiff_backup(inlocal, outlocal, in1.path, self.out_rp.path, 10000,
					 extra_options = extra_args)
		if compare_back: self.check_dir1(self.out_rp)
		rdiff_backup(inlocal, outlocal, in2.path, self.out_rp.path, 20000,
					 extra_options = extra_args)
		if compare_back: self.check_dir2(self.out_rp)

		# Now try restoring
		Myrm(restore_dir.path)
		rdiff_backup(inlocal, outlocal, self.out_rp.path, restore_dir.path,
					 30000, extra_options = "-r now " + extra_args)
		self.check_dir2(restore_dir)
		Myrm(restore_dir.path)
		rdiff_backup(1, 1, self.out_rp.path, restore_dir.path, 30000,
					 extra_options = "-r 10000 " + extra_args)
		self.check_dir1(restore_dir)

	def test_basic_local(self):
		"""Test backup session when increment would be too long"""
		self.generic_test(1, 1, "", 1)

	def test_quoting_local(self):
		"""Test backup session with quoting, so reg files also too long"""
		self.generic_test(1, 1, "--override-chars-to-quote A-Z", 0)

	def generic_regress_test(self, extra_args):
		"""Used for regress tests below"""
		in1, in2 = self.make_input_dirs()
		Myrm(self.out_rp.path)
		restore_dir = self.root_rp.append('longname_out')
		Myrm(restore_dir.path)

		rdiff_backup(1, 1, in1.path, self.out_rp.path, 10000,
					 extra_options = extra_args)
		rdiff_backup(1, 1, in2.path, self.out_rp.path, 20000,
					 extra_options = extra_args)

		# Regress repository back to in1 condition
		Globals.rbdir = self.out_rp.append_path('rdiff-backup-data')
		self.add_current_mirror(10000)
		self.out_rp.setdata()
		regress.Regress(self.out_rp)
		
		# Restore in1 and compare
		rdiff_backup(1, 1, self.out_rp.path, restore_dir.path, 30000,
					 extra_options = '-r now ' + extra_args)
		self.check_dir1(restore_dir)

	def add_current_mirror(self, time):
		"""Add current_mirror marker at given time"""
		cur_mirror_rp = Globals.rbdir.append(
			"current_mirror.%s.data" % (Time.timetostring(time),))
		cur_mirror_rp.touch()

	def test_regress_basic(self):
		"""Test regressing when increments would be too long"""
		self.generic_regress_test('')


if __name__ == "__main__": unittest.main()


