import unittest, os
from rdiff_backup.metadata import *
from rdiff_backup import rpath, Globals

class MetadataTest(unittest.TestCase):
	def testQuote(self):
		"""Test quoting and unquoting"""
		filenames = ["foo", ".", "hello\nthere", "\\", "\\\\\\",
					 "h\no\t\x87\n", " "]
		for filename in filenames:
			quoted = quote_path(filename)
			assert not "\n" in quoted
			result = unquote_path(quoted)
			assert result == filename, (quoted, result, filename)

	def testRORP2Record(self):
		"""Test turning RORPs into records and back again"""
		vft = rpath.RPath(Globals.local_connection,
						  "testfiles/various_file_types")
		rpaths = map(lambda x: vft.append(x), vft.listdir())
		extra_rpaths = map(lambda x: rpath.RPath(Globals.local_connection, x),
						   ['/bin/ls', '/dev/ttyS0', '/dev/hda', 'aoeuaou'])

		for rp in [vft] + rpaths + extra_rpaths:
			record = RORP2Record(rp)
			#print record
			new_rorp = Record2RORP(record)
			assert new_rorp == rp, (new_rorp, rp, record)


if __name__ == "__main__": unittest.main()
