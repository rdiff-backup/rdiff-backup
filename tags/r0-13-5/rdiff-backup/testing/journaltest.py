from commontest import *
import unittest
from rdiff_backup import journal, Globals, rpath

class JournalTest(unittest.TestCase):
	def testBasic(self):
		"""Test opening a journal, then reading, writing, and deleting"""
		MakeOutputDir()
		Globals.dest_root = rpath.RPath(Globals.local_connection,
										"testfiles/output")
		Globals.rbdir = Globals.dest_root.append("rdiff-backup-data")

		Globals.rbdir.mkdir()
		journal.open_journal()
		assert len(journal.get_entries_from_journal()) == 0

		# It's important that none of these files really exist
		e1 = journal.write_entry(("Hello48",), ("temp_index", "foo"),
								 2, "reg")
		e2 = journal.write_entry(("2nd", "Entry", "now"),
								 ("temp_index",), 1, None)
		assert e1.entry_rp and e2.entry_rp

		l = journal.get_entries_from_journal()
		assert len(l) == 2
		first_index = l[0].index
		assert (first_index == ("Hello48",) or
				first_index == ("2nd", "Entry", "now"))

		# Now test recovering journal, and make sure everything deleted
		journal.recover_journal()
		assert len(journal.get_entries_from_journal()) == 0
		

if __name__ == "__main__": unittest.main()
