import unittest
from commontest import *
from rdiff_backup import FilenameMapping

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

if __name__ == "__main__": unittest.main()
