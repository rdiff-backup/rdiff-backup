import unittest
from commontest import *
from rdiff_backup import FilenameMapping, rpath, Globals

class FilenameMappingTest(unittest.TestCase):
	"""Test the FilenameMapping class, for quoting filenames"""
	def setUp(self):
		"""Just initialize quoting"""
		Globals.chars_to_quote = 'A-Z'
		FilenameMapping.set_init_quote_vals()

	def testBasicQuote(self):
		"""Test basic quoting and unquoting"""
		filenames = ["hello", "HeLLo", "EUOeu/EUOeu", ":", "::::EU", "/:/:"]
		for filename in filenames:
			quoted = FilenameMapping.quote(filename)
			assert FilenameMapping.unquote(quoted) == filename, filename

	def testQuotedRPath(self):
		"""Test the QuotedRPath class"""

	def testQuotedSepBase(self):
		"""Test get_quoted_sep_base function"""
		path = ("/usr/local/mirror_metadata"
				".1969-12-31;08421;05833;05820-07;05800.data.gz")
		qrp = FilenameMapping.get_quoted_sep_base(path)
		assert qrp.base == "/usr/local", qrp.base
		assert len(qrp.index) == 1, qrp.index
		assert (qrp.index[0] ==
				"mirror_metadata.1969-12-31T21:33:20-07:00.data.gz")

	def testLongFilenames(self):
		"""See if long quoted filenames cause crash"""
		MakeOutputDir()
		outrp = rpath.RPath(Globals.local_connection, "testfiles/output")
		inrp = rpath.RPath(Globals.local_connection, "testfiles/quotetest")
		re_init_dir(inrp)
		long_filename = "A"*200 # when quoted should cause overflow
		longrp = inrp.append(long_filename)
		longrp.touch()
		shortrp = inrp.append("B")
		shortrp.touch()

		rdiff_backup(1, 1, inrp.path, outrp.path, 100000,
					 extra_options = "--override-chars-to-quote A")

		longrp_out = outrp.append(long_filename)
		assert not longrp_out.lstat()
		shortrp_out = outrp.append('B')
		assert shortrp_out.lstat()

		rdiff_backup(1, 1, "testfiles/empty", outrp.path, 200000)
		shortrp_out.setdata()
		assert not shortrp_out.lstat()
		rdiff_backup(1, 1, inrp.path, outrp.path, 300000)
		shortrp_out.setdata()
		assert shortrp_out.lstat()

if __name__ == "__main__": unittest.main()
