from commontest import *
import unittest
from rdiff_backup import journal, Globals, rpath

class JournalTest(unittest.TestCase):
	def testBasic(self):
		"""Test opening a journal, then reading, writing, and deleting"""
		MakeOutputDir()
		Globals.rbdir = rpath.RPath(Globals.local_connection,
									"testfiles/output")
		journal.open_journal()
		assert len(journal.get_entries_from_journal()) == 0

		# It's important that none of these files really exist
		e1 = journal.write_entry("Hello48", "reg", "inc_file3917", "t39p")
		e2 = journal.write_entry("2nd_euoeuo", None, "inc_file4832", "l389")
		assert e1.entry_rp and e2.entry_rp

		l = journal.get_entries_from_journal()
		assert len(l) == 2
		first_filename = l[0].test_filename
		assert first_filename == "Hello48" or first_filename == "2nd_euoeuo"

		# Now test recovering journal, and make sure everything deleted
		journal.recover_journal()
		assert len(journal.get_entries_from_journal()) == 0
		

if __name__ == "__main__": unittest.main()
