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

import Globals, log, rpath, cPickle, TempFile

# Holds an rpath of the journal directory, a file object, and then
journal_dir_rp = None
journal_dir_fp = None

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
	"""fsync the journal directory"""
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

def write_entry(test_filename, test_filename_type,
				increment_filename, temp_filename):
	"""Write new entry given variables into journal, return entry"""
	e = Entry()
	e.test_filename = test_filename
	e.test_filename_type = test_filename_type
	e.increment_filename = increment_filename
	e.temp_filename = temp_filename
	e.write()
	return e
	
def remove_entry(entry_rp):
	"""Remove the entry in entry_rp from the journal"""
	entry_rp.delete()
	sync_journal()


class Entry:
	"""A single journal entry, describing one transaction

	Although called a journal entry, this is less a description of
	what is going happen than a short recipe of what to do if
	something goes wrong.

	Currently the recipe needs to be very simple and is determined by
	the four variables test_filename, test_filename_type,
	increment_filename, and temp_filename.  See the recover() method
	for details.

	"""
	test_filename = None
	test_filename_type = None # None is a valid value for this variable
	increment_filename = None
	temp_filename = None

	# This holds the rpath in the journal dir that holds self
	entry_rp = None

	def recover(self):
		"""Recover the current journal entry

		See if test_filename matches test_filename_type.  If so,
		delete increment_filename.  Delete temp_filename regardless.
		It's OK to recover the same entry multiple times.

		"""
		assert self.test_filename and self.temp_filename
		test_rp = rpath.RPath(Globals.local_connection, self.test_filename)
		temp_rp = rpath.RPath(Globals.local_connection, self.temp_filename)
		inc_rp = rpath.RPath(Globals.local_connection, self.increment_filename)
		if test_rp.lstat() == self.test_filename_type:
			if inc_rp.lstat():
				inc_rp.delete()
				inc_rp.get_parent_rp().fsync()
		if temp_rp.lstat():
			temp_rp.delete()
			temp_rp.get_parent_rp().fsync()

	def to_string(self):
		"""Return string form of entry"""
		return cPickle.dumps({'test_filename': self.test_filename,
							  'test_filename_type': self.test_filename_type,
							  'increment_filename': self.increment_filename,
							  'temp_filename': self.temp_filename})

	def write(self):
		"""Write the current entry into the journal"""
		entry_rp = TempFile.new(journal_dir_rp.append("foo"))
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
			self.test_filename = val_dict['test_filename']
			self.test_filename_type = val_dict['test_filename_type']
			self.increment_filename = val_dict['increment_filename']
			self.temp_filename = val_dict['temp_filename']
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
		self.entry_rp.delete()
		sync_journal()
