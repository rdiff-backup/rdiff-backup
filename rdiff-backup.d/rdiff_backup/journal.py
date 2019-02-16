# Copyright 2002 Ben Escoto
#
# This file is part of rdiff-backup.
#
# rdiff-backup is free software; you can redistribute it and/or modify
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.
#
# rdiff-backup is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with rdiff-backup; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
# USA

# UPDATE: I have decided not to use journaling and use the regress
# stuff exclusively.  This code is left here for posterity.

"""Application level journaling for better error recovery

This module has routines for maintaining a "journal" to keep track of
writes to an rdiff-backup destination directory.  This is necessary
because otherwise data could be lost if the program is abruptly
stopped (say to a computer crash).  For instance, various temp files
could be left on the mirror drive.  Or it may not be clear whether an
increment file has been fully written.

To keep this from happening, various writes may be journaled (a write
corresponds to the updating of a single file).  To do this, a separate
file in the journal directory is created, and the necessary
information is written to it.  When the transaction is finished, that
journal entry file will be deleted.  If there is a crash, the next
time rdiff-backup is run, it will see the journal file, and process
it, bringing the rdiff-backup destination directory back into a
consistent state.

Two caveats:

1) The journal is only meant to be used in conjunction with a
   regression to the state before the backup was attempted.  If the
   failed session is not "cleaned" out right after the journal is
   recovered, something bad could happen.

2) This journal will only be effective if the actual hardware and OS
   are working.  If disk failures are causing data loss, or if a crash
   causes your filesystem to be corrupted, rdiff-backup could lose
   data despite all this journal stuff.

"""

import Globals, log, rpath, cPickle, TempFile, os, restore

# Holds an rpath of the journal directory, a file object, and then
journal_dir_rp = None
journal_dir_fp = None

# Set to time in seconds of previous aborted backup
unsuccessful_backup_time = None

def open_journal():
	"""Make sure the journal dir exists (creating it if necessary)"""
	global journal_dir_rp, journal_dir_fp
	assert journal_dir_rp is journal_dir_fp is None
	journal_dir_rp = Globals.rbdir.append("journal")
	if not journal_dir_rp.lstat():
		log.Log("Creating journal directory %s" % (journal_dir_rp.path,), 5)
		journal_dir_rp.mkdir()
	assert journal_dir_rp.isdir()
	journal_dir_fp = journal_dir_rp.open("rb")
	
def close_journal():
	"""Close the journal at the end of a session"""
	global journal_dir_rp, journal_dir_fp
	assert not journal_dir_rp.listdir()
	assert not journal_dir_fp.close()
	journal_dir_rp = journal_dir_fp = None

def sync_journal():
	"""fsync the journal directory.

	Note that fsync'ing a particular entry file may also be required
	to guarantee writes have been committed.

	"""
	journal_dir_rp.fsync(journal_dir_fp)

def recover_journal():
	"""Read the journal and recover each of the events"""
	for entry in get_entries_from_journal():
		entry.recover()
		entry.delete()

def get_entries_from_journal():
	"""Return list of entries in the journal (deletes bad entries)"""
	entry_list = []
	for filename in journal_dir_rp.listdir():
		entry_rp = journal_dir_rp.append(filename)
		e = Entry()
		success = e.init_from_rp(entry_rp)
		if not success: entry_rp.delete()
		else: entry_list.append(e)
	return entry_list

def write_entry(index, temp_index, testfile_option, testfile_type):
	"""Write new entry given variables into journal, return entry"""
	e = Entry()
	e.index = index
	e.temp_index = index
	e.testfile_option = testfile_option
	e.testfile_type = testfile_type
	e.write()
	return e
	

class Entry:
	"""A single journal entry, describing one transaction

	Although called a journal entry, this is less a description of
	what is going happen than a short recipe of how to recover if
	something goes wrong.

	Currently the recipe needs to be very simple and is determined by
	the four variables index, temp_index, testfile_option,
	testfile_type.  See the recover() method for details.

	"""
	index = None
	temp_index = None
	testfile_option = None
	testfile_type = None # None is a valid value for this variable

	# This points to the rpath in the journal dir that holds this entry
	entry_rp = None

	def recover(self):
		"""Recover the current journal entry

		self.testfile_option has 3 possibilities:
		1 - testfile is mirror file
		2 - testfile is increment file
		3 - testfile is temp file

		Either way, see if the type of the testfile matches
		testfile_type.  If so, delete increment file.  Deleted
		tempfile regardless.

		We express things in terms of indicies because we need paths
		relative to a fixed directory (like Globals.dest_root).

		It's OK to recover the same entry multiple times.

		"""
		assert self.index is not None and self.temp_index is not None
		mirror_rp = Globals.dest_root.new_index(self.index)
		if self.temp_index:
			temp_rp = Globals.dest_root.new_index(self.temp_index)
		inc_rp = self.get_inc()

		assert 1 <= self.testfile_option <= 3
		if self.testfile_option == 1: test_rp = mirror_rp
		elif self.testfile_option == 2: test_rp = inc_rp
		else: test_rp = temp_rp

		if test_rp and test_rp.lstat() == self.testfile_type:
			if inc_rp and inc_rp.lstat(): inc_rp.sync_delete()
		if temp_rp and temp_rp.lstat(): temp_rp.sync_delete()

	def get_inc(self):
		"""Return inc_rpath, if any, corresponding to self.index"""
		incroot = Globals.rbdir.append_path("increments")
		incbase = incroot.new_index(self.index)
		inclist = restore.get_inclist(incbase)
		inclist = filter(lambda inc:
						 inc.getinctime() == unsuccessful_backup_time, inclist)
		assert len(inclist) <= 1
		if inclist: return inclist[0]
		else: return None

	def to_string(self):
		"""Return string form of entry"""
		return cPickle.dumps({'index': self.index,
							  'testfile_option': self.testfile_option,
							  'testfile_type': self.testfile_type,
							  'temp_index': self.temp_index})

	def write(self):
		"""Write the current entry into the journal"""
		entry_rp = TempFile.new_in_dir(journal_dir_rp)
		fp = entry_rp.open("wb")
		fp.write(self.to_string())
		entry_rp.fsync(fp)
		assert not fp.close()
		sync_journal()
		self.entry_rp = entry_rp

	def init_from_string(self, s):
		"""Initialize values from string.  Return 0 if problem."""
		try: val_dict = cPickle.loads(s)
		except cPickle.UnpicklingError: return 0
		try:
			self.index = val_dict['index']
			self.testfile_type = val_dict['testfile_type']
			self.testfile_option = val_dict['testfile_option']
			self.temp_index = val_dict['temp_index']
		except TypeError, KeyError: return 0
		return 1

	def init_from_rp(self, entry_rp):
		"""Initialize values from an rpath.  Return 0 if problem"""
		if not entry_rp.isreg(): return 0
		success = self.init_from_string(entry_rp.get_data())
		if not success: return 0
		self.entry_rp = entry_rp
		return 1

	def delete(self):
		"""Remove entry from the journal.  self.entry_rp must be set"""
		self.entry_rp.sync_delete()
