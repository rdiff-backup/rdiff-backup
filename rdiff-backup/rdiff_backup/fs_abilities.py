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

"""Determine the capabilities of given file system

rdiff-backup needs to read and write to file systems with varying
abilities.  For instance, some file systems and not others have ACLs,
are case-sensitive, or can store ownership information.  The code in
this module tests the file system for various features, and returns an
FSAbilities object describing it.

"""

import errno
import Globals, log, TempFile

class FSAbilities:
	"""Store capabilities of given file system"""
	chars_to_quote = None # Hold characters not allowable in file names
	ownership = None # True if chown works on this filesystem
	acls = None # True if access control lists supported
	eas = None # True if extended attributes supported
	hardlinks = None # True if hard linking supported
	fsync_dirs = None # True if directories can be fsync'd
	read_only = None # True if capabilities were determined non-destructively

	def init_readonly(self, rp):
		"""Set variables using fs tested at RPath rp

		This method does not write to the file system at all, and
		should be run on the file system when the file system will
		only need to be read.

		Only self.acls and self.eas are set.

		"""
		self.read_only = 1
		self.set_eas(rp, 0)
		self.set_acls(rp)
		return self

	def init_readwrite(self, rbdir, use_ctq_file = 1):
		"""Set variables using fs tested at rp_base

		This method creates a temp directory in rp_base and writes to
		it in order to test various features.  Use on a file system
		that will be written to.

		This sets self.chars_to_quote, self.ownership, self.acls,
		self.eas, self.hardlinks, and self.fsync_dirs.

		If user_ctq_file is true, try reading the "chars_to_quote"
		file in directory.

		"""
		assert rbdir.isdir()
		self.read_only = 0

		subdir = TempFile.new_in_dir(rbdir)
		subdir.mkdir()
		self.set_ownership(subdir)
		self.set_hardlinks(subdir)
		self.set_fsync_dirs(subdir)
		self.set_eas(subdir, 1)
		self.set_acls(subdir)
		self.set_chars_to_quote(subdir)
		if use_ctq_file: self.compare_chars_to_quote(rbdir)
		subdir.delete()
		return self

	def compare_chars_to_quote(self, rbdir):
		"""Read chars_to_quote file, compare with current settings"""
		assert self.chars_to_quote is not None
		ctq_rp = rbdir.append("chars_to_quote")
		def write_new_chars():
			"""Replace old chars_to_quote file with new value"""
			if ctq_rp.lstat(): ctq_rp.delete()
			fp = ctq_rp.open("wb")
			fp.write(self.chars_to_quote)
			assert not fp.close()

		def get_old_chars():
			fp = ctq_rp.open("rb")
			old_chars = fp.read()
			assert not fp.close()
			return old_chars

		if not ctq_rp.lstat(): write_new_chars()
		else:
			old_chars = get_old_chars()
			if old_chars != self.chars_to_quote:
				if self.chars_to_quote == "":
					log.Log("Warning: File system no longer needs quoting, "
							"but will retain for backwards compatibility.", 2)
				else: log.FatalError("""New quoting requirements

This may be caused when you copy an rdiff-backup directory from a
normal file system on to a windows one that cannot support the same
characters.  If you want to risk it, remove the file
rdiff-backup-data/chars_to_quote.
""")

	def set_ownership(self, testdir):
		"""Set self.ownership to true iff testdir's ownership can be changed"""
		tmp_rp = testdir.append("foo")
		tmp_rp.touch()
		uid, gid = tmp_rp.getuidgid()
		try:
			tmp_rp.chown(uid+1, gid+1) # just choose random uid/gid
			tmp_rp.chown(0, 0)
		except (IOError, OSError), exc:
			if exc[0] == errno.EPERM:
				log.Log("Warning: ownership cannot be changed on filesystem "
						"at device %s" % (testdir.getdevloc(),), 2)
				self.ownership = 0
			else: raise
		else: self.ownership = 1
		tmp_rp.delete()

	def set_hardlinks(self, testdir):
		"""Set self.hardlinks to true iff hard linked files can be made"""
		hl_source = testdir.append("hardlinked_file1")
		hl_dest = testdir.append("hardlinked_file2")
		hl_source.touch()
		try:
			hl_dest.hardlink(hl_source.path)
			assert hl_source.getinode() == hl_dest.getinode()
		except (IOError, OSError), exc:
			if exc[0] in (errno.EOPNOTSUPP, errno.EPERM):
				log.Log("Warning: hard linking not supported by filesystem %s"
						% (testdir.getdevloc(),), 2)
				self.hardlinks = 0
			else: raise
		else: self.hardlinks = 1

	def set_fsync_dirs(self, testdir):
		"""Set self.fsync_dirs if directories can be fsync'd"""
		try: testdir.fsync()
		except (IOError, OSError), exc:
			log.Log("Warning: Directories on file system at %s are not "
					"fsyncable.\nAssuming it's unnecessary." %
					(testdir.getdevloc(),), 2)
			self.fsync_dirs = 0
		else: self.fsync_dirs = 1

	def set_chars_to_quote(self, subdir):
		"""Set self.chars_to_quote by trying to write various paths"""
		def is_case_sensitive():
			"""Return true if file system is case sensitive"""
			upper_a = subdir.append("A")
			upper_a.touch()
			lower_a = subdir.append("a")
			if lower_a.lstat():
				lower_a.delete()
				upper_a.setdata()
				assert not upper_a.lstat()
				return 0
			else:
				upper_a.delete()
				return 1

		def supports_unusual_chars():
			"""Test handling of several chars sometimes not supported"""
			for filename in [':', '\\', chr(175)]:
				rp = subdir.append(filename)
				try: rp.touch()
				except IOError:
					assert not rp.lstat()
					return 0
				assert rp.lstat()
				rp.delete()
			return 1

		def sanity_check():
			"""Make sure basic filenames writable"""
			for filename in ['5-_ a']:
				rp = subdir.append(filename)
				rp.touch()
				assert rp.lstat()
				rp.delete()

		sanity_check()
		if is_case_sensitive():
			if supports_unusual_chars(): self.chars_to_quote = ""
			else: self.chars_to_quote = "^A-Za-z0-9_ -"
		else:
			if supports_unusual_chars(): self.chars_to_quote = "A-Z;"
			else: self.chars_to_quote = "^a-z0-9_ -"

	def set_acls(self, rp):
		"""Set self.acls based on rp.  Does not write.  Needs to be local"""
		assert Globals.local_connection is rp.conn
		assert rp.lstat()
		try: import posix1e
		except ImportError:
			log.Log("Warning: Unable to import module posix1e from pylibacl "
					"package.\nACLs not supported on device %s" %
					(rp.getdevloc(),), 2)
			self.acls = 0
			return

		try: posix1e.ACL(file=rp.path)
		except IOError, exc:
			if exc[0] == errno.EOPNOTSUPP:
				log.Log("Warning: ACLs appear not to be supported by "
						"filesystem on device %s" % (rp.getdevloc(),), 2)
				self.acls = 0
			else: raise
		else: self.acls = 1
		
	def set_eas(self, rp, write):
		"""Set extended attributes from rp.  Run locally.

		Tests writing if write is true.

		"""
		assert Globals.local_connection is rp.conn
		assert rp.lstat()
		try: import xattr
		except ImportError:
			log.Log("Warning: Unable to import module xattr.  ACLs not "
					"supported on device %s" % (rp.getdevloc(),), 2)
			self.eas = 0
			return

		try:
			xattr.listxattr(rp.path)
			if write:
				xattr.setxattr(rp.path, "user.test", "test val")
				assert xattr.getxattr(rp.path, "user.test") == "test val"
		except IOError, exc:
			if exc[0] == errno.EOPNOTSUPP:
				log.Log("Warning: Extended attributes not supported by "
						"filesystem on device %s" % (rp.getdevloc(),), 2)
				self.eas = 0
			else: raise
		else: self.eas = 1

