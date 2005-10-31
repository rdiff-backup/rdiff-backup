import unittest
from commontest import *
from rdiff_backup import compare

"""Test the compare.py module and overall compare functionality"""

class CompareTest(unittest.TestCase):
	def setUp(self):
		Myrm("testfiles/output")
		rdiff_backup(1, 1, 'testfiles/increment2', 'testfiles/output',
					 current_time = 10000)
		rdiff_backup(1, 1, 'testfiles/increment3', 'testfiles/output',
					 current_time = 20000)

	def generic_test(self, local, compare_option):
		"""Used for 6 tests below"""
		rdiff_backup(local, local, 'testfiles/increment3', 'testfiles/output',
					 extra_options = compare_option)
		ret_val = rdiff_backup(local, local, 'testfiles/increment2',
		             'testfiles/output', extra_options = compare_option,
					  check_return_val = 0)
		assert ret_val, ret_val
		rdiff_backup(local, local, 'testfiles/increment2', 'testfiles/output',
					 extra_options = compare_option + "-at-time 10000")
		ret_val = rdiff_backup(local, local, 'testfiles/increment3',
			'testfiles/output',
			extra_options = compare_option + "-at-time 10000",
			check_return_val = 0)
		assert ret_val, ret_val

	def testBasicLocal(self):
		"""Test basic --compare and --compare-at-time modes"""
		self.generic_test(1, "--compare")

	def testBasicRemote(self):
		"""Test basic --compare and --compare-at-time modes, both remote"""
		self.generic_test(0, "--compare")

	def testHashLocal(self):
		"""Test --compare-hash and --compare-hash-at-time modes local"""
		self.generic_test(1, "--compare-hash")

	def testHashRemote(self):
		"""Test --compare-hash and -at-time remotely"""
		self.generic_test(0, "--compare-hash")

	def testFullLocal(self):
		"""Test --compare-full and --compare-full-at-time"""
		self.generic_test(1, "--compare-full")

	def testFullRemote(self):
		"""Test full file compare remotely"""
		self.generic_test(0, "--compare-full")

	def generic_selective_test(self, local, compare_option):
		"""Used for selective tests--just compare part of a backup"""
		rdiff_backup(local, local, 'testfiles/increment3/various_file_types',
					 'testfiles/output/various_file_types',
					 extra_options = compare_option)
		ret_val = rdiff_backup(local, local,
							   'testfiles/increment2/increment1',
							   'testfiles/output/increment1',
							   extra_options = compare_option,
							   check_return_val = 0)
		assert ret_val, ret_val

		rdiff_backup(local, local, 'testfiles/increment2/newdir',
					 'testfiles/output/newdir',
					 extra_options = compare_option + "-at-time 10000")
		ret_val = rdiff_backup(local, local,
							   'testfiles/increment3/newdir',
							   'testfiles/output/newdir',
						extra_options = compare_option + "-at-time 10000",
							   check_return_val = 0)
		assert ret_val, ret_val

	def testSelLocal(self):
		"""Test basic local compare of single subdirectory"""
		self.generic_selective_test(1, "--compare")

	def testSelRemote(self):
		"""Test --compare of single directory, remote"""
		self.generic_selective_test(0, "--compare")		

	def testSelHashLocal(self):
		"""Test --compare-hash of subdirectory, local"""
		self.generic_selective_test(1, "--compare-hash")

	def testSelHashRemote(self):
		"""Test --compare-hash of subdirectory, remote"""
		self.generic_selective_test(0, "--compare-hash")

	def testSelFullLocal(self):
		"""Test --compare-full of subdirectory, local"""
		self.generic_selective_test(1, "--compare-full")		

	def testSelFullRemote(self):
		"""Test --compare-full of subdirectory, remote"""
		self.generic_selective_test(0, "--compare-full")		

if __name__ == "__main__": unittest.main()

