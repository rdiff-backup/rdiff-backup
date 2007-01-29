# Copyright 2003 Ben Escoto
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

import errno, os
import Globals, log, TempFile, selection, robust, SetConnections, \
	   static, FilenameMapping

class FSAbilities:
	"""Store capabilities of given file system"""
	extended_filenames = None # True if filenames can handle ":" etc.
	case_sensitive = None # True if "foobar" and "FoObAr" are different files
	ownership = None # True if chown works on this filesystem
	acls = None # True if access control lists supported
	eas = None # True if extended attributes supported
	hardlinks = None # True if hard linking supported
	fsync_dirs = None # True if directories can be fsync'd
	dir_inc_perms = None # True if regular files can have full permissions
	resource_forks = None # True if system supports resource forks
	carbonfile = None # True if Mac Carbon file data is supported. 
	name = None # Short string, not used for any technical purpose
	read_only = None # True if capabilities were determined non-destructively
	high_perms = None # True if suid etc perms are (read/write) supported
	escape_dos_devices = None # True if dos device files can't be created (e.g.,
							  # aux, con, com1, etc)
	symlink_perms = None # True if symlink perms are affected by umask

	def __init__(self, name = None):
		"""FSAbilities initializer.  name is only used in logging"""
		self.name = name

	def __str__(self):
		"""Return pretty printable version of self"""
		assert self.read_only == 0 or self.read_only == 1, self.read_only
		s = ['-' * 65]

		def addline(desc, val_text):
			"""Add description line to s"""
			s.append('  %s%s%s' % (desc, ' ' * (45-len(desc)), val_text))

		def add_boolean_list(pair_list):
			"""Add lines from list of (desc, boolean) pairs"""
			for desc, boolean in pair_list:
				if boolean: val_text = 'On'
				elif boolean is None: val_text = 'N/A'
				else:
					assert boolean == 0
					val_text = 'Off'
				addline(desc, val_text)			

		def get_title_line():
			"""Add the first line, mostly for decoration"""
			read_string = self.read_only and "read only" or "read/write"
			if self.name:
				return ('Detected abilities for %s (%s) file system:' %
						(self.name, read_string))
			else: return ('Detected abilities for %s file system' %
						  (read_string,))

		s.append(get_title_line())
		if not self.read_only:
			add_boolean_list([('Ownership changing', self.ownership),
							  ('Hard linking', self.hardlinks),
							  ('fsync() directories', self.fsync_dirs),
							  ('Directory inc permissions',
							   self.dir_inc_perms),
							  ('High-bit permissions', self.high_perms),
							  ('Symlink permissions', self.symlink_perms),
							  ('Extended filenames', self.extended_filenames)])
		add_boolean_list([('Access control lists', self.acls),
						  ('Extended attributes', self.eas),
						  ('Case sensitivity', self.case_sensitive),
						  ('Escape DOS devices', self.escape_dos_devices),
						  ('Mac OS X style resource forks',
						   self.resource_forks),
						  ('Mac OS X Finder information', self.carbonfile)])
		s.append(s[0])
		return '\n'.join(s)

	def init_readonly(self, rp):
		"""Set variables using fs tested at RPath rp.  Run locally.

		This method does not write to the file system at all, and
		should be run on the file system when the file system will
		only need to be read.

		Only self.acls and self.eas are set.

		"""
		assert rp.conn is Globals.local_connection
		self.root_rp = rp
		self.read_only = 1
		self.set_eas(rp, 0)
		self.set_acls(rp)
		self.set_resource_fork_readonly(rp)
		self.set_carbonfile()
		self.set_case_sensitive_readonly(rp)
		self.set_escape_dos_devices(rp)
		return self

	def init_readwrite(self, rbdir):
		"""Set variables using fs tested at rp_base.  Run locally.

		This method creates a temp directory in rp_base and writes to
		it in order to test various features.  Use on a file system
		that will be written to.

		"""
		assert rbdir.conn is Globals.local_connection
		if not rbdir.isdir():
			assert not rbdir.lstat(), (rbdir.path, rbdir.lstat())
			rbdir.mkdir()
		self.root_rp = rbdir
		self.read_only = 0
		subdir = TempFile.new_in_dir(rbdir)
		subdir.mkdir()

		self.set_extended_filenames(subdir)
		self.set_case_sensitive_readwrite(subdir)
		self.set_ownership(subdir)
		self.set_hardlinks(subdir)
		self.set_fsync_dirs(subdir)
		self.set_eas(subdir, 1)
		self.set_acls(subdir)
		self.set_dir_inc_perms(subdir)
		self.set_resource_fork_readwrite(subdir)
		self.set_carbonfile()
		self.set_high_perms_readwrite(subdir)
		self.set_symlink_perms(subdir)
		self.set_escape_dos_devices(subdir)

		subdir.delete()
		return self

	def set_ownership(self, testdir):
		"""Set self.ownership to true iff testdir's ownership can be changed"""
		tmp_rp = testdir.append("foo")
		tmp_rp.touch()
		uid, gid = tmp_rp.getuidgid()
		try:
			tmp_rp.chown(uid+1, gid+1) # just choose random uid/gid
			tmp_rp.chown(0, 0)
		except (IOError, OSError): self.ownership = 0
		else: self.ownership = 1
		tmp_rp.delete()

	def set_hardlinks(self, testdir):
		"""Set self.hardlinks to true iff hard linked files can be made"""
		hl_source = testdir.append("hardlinked_file1")
		hl_dir = testdir.append("hl")
		hl_dir.mkdir()
		hl_dest = hl_dir.append("hardlinked_file2")
		hl_source.touch()
		try:
			hl_dest.hardlink(hl_source.path)
			if hl_source.getinode() != hl_dest.getinode():
				raise IOError(errno.EOPNOTSUPP, "Hard links don't compare")
		except (IOError, OSError):
			log.Log("Warning: hard linking not supported by filesystem "
					"at %s" % (self.root_rp.path,), 3)
			self.hardlinks = 0
		else: self.hardlinks = 1

	def set_fsync_dirs(self, testdir):
		"""Set self.fsync_dirs if directories can be fsync'd"""
		assert testdir.conn is Globals.local_connection
		try: testdir.fsync()
		except (IOError, OSError):
			log.Log("Directories on file system at %s are not fsyncable.\n"
					"Assuming it's unnecessary." % (testdir.path,), 4)
			self.fsync_dirs = 0
		else: self.fsync_dirs = 1

	def set_extended_filenames(self, subdir):
		"""Set self.extended_filenames by trying to write a path"""
		assert not self.read_only

		# Make sure ordinary filenames ok
		ordinary_filename = '5-_ a.snapshot.gz'
		ord_rp = subdir.append(ordinary_filename)
		ord_rp.touch()
		assert ord_rp.lstat()
		ord_rp.delete()

		# Try a UTF-8 encoded character
		extended_filename = ':\\ ' + chr(225) + chr(132) + chr(137)
		ext_rp = None
		try:
			ext_rp = subdir.append(extended_filename)
			ext_rp.touch()
		except (IOError, OSError):
			if ext_rp: assert not ext_rp.lstat()
			self.extended_filenames = 0
		else:
			assert ext_rp.lstat()
			ext_rp.delete()
			self.extended_filenames = 1

	def set_acls(self, rp):
		"""Set self.acls based on rp.  Does not write.  Needs to be local"""
		assert Globals.local_connection is rp.conn
		assert rp.lstat()
		try: import posix1e
		except ImportError:
			log.Log("Unable to import module posix1e from pylibacl "
					"package.\nACLs not supported on filesystem at %s" %
					(rp.path,), 4)
			self.acls = 0
			return

		try: posix1e.ACL(file=rp.path)
		except IOError:
			log.Log("ACLs not supported by filesystem at %s" % (rp.path,), 4)
			self.acls = 0
		else: self.acls = 1

	def set_case_sensitive_readwrite(self, subdir):
		"""Determine if directory at rp is case sensitive by writing"""
		assert not self.read_only
		upper_a = subdir.append("A")
		upper_a.touch()
		lower_a = subdir.append("a")
		if lower_a.lstat():
			lower_a.delete()
			upper_a.setdata()
			assert not upper_a.lstat()
			self.case_sensitive = 0
		else:
			upper_a.delete()
			self.case_sensitive = 1

	def set_case_sensitive_readonly(self, rp):
		"""Determine if directory at rp is case sensitive without writing"""
		def find_letter(subdir):
			"""Find a (subdir_rp, dirlist) with a letter in it, or None

			Recurse down the directory, looking for any file that has
			a letter in it.  Return the pair (rp, [list of filenames])
			where the list is of the directory containing rp.

			"""
			l = robust.listrp(subdir)
			for filename in l:
				if filename != filename.swapcase():
					return (subdir, l, filename)
			for filename in l:
				dir_rp = subdir.append(filename)
				if dir_rp.isdir():
					subsearch = find_letter(dir_rp)
					if subsearch: return subsearch
			return None

		def test_triple(dir_rp, dirlist, filename):
			"""Return 1 if filename shows system case sensitive"""
			letter_rp = dir_rp.append(filename)
			assert letter_rp.lstat(), letter_rp
			swapped = filename.swapcase()
			if swapped in dirlist: return 1

			swapped_rp = dir_rp.append(swapped)
			if swapped_rp.lstat(): return 0
			return 1

		triple = find_letter(rp)
		if not triple:
			log.Log("Warning: could not determine case sensitivity of "
					"source directory at\n  " + rp.path + "\n"
					"because we can't find any files with letters in them.\n"
					"It will be treated as case sensitive.", 2)
			self.case_sensitive = 1
			return

		self.case_sensitive = test_triple(*triple)

	def set_eas(self, rp, write):
		"""Set extended attributes from rp. Tests writing if write is true."""
		assert Globals.local_connection is rp.conn
		assert rp.lstat()
		try: import xattr
		except ImportError:
			log.Log("Unable to import module xattr.\nExtended attributes not "
					"supported on filesystem at %s" % (rp.path,), 4)
			self.eas = 0
			return

		try:
			xattr.listxattr(rp.path)
			if write:
				xattr.setxattr(rp.path, "user.test", "test val")
				assert xattr.getxattr(rp.path, "user.test") == "test val"
		except IOError:
			log.Log("Extended attributes not supported by "
					"filesystem at %s" % (rp.path,), 4)
			self.eas = 0
		else: self.eas = 1

	def set_dir_inc_perms(self, rp):
		"""See if increments can have full permissions like a directory"""
		test_rp = rp.append('dir_inc_check')
		test_rp.touch()
		try: test_rp.chmod(07777)
		except OSError:
			test_rp.delete()
			self.dir_inc_perms = 0
			return
		test_rp.setdata()
		assert test_rp.isreg()
		if test_rp.getperms() == 07777: self.dir_inc_perms = 1
		else: self.dir_inc_perms = 0
		test_rp.delete()

	def set_carbonfile(self):
		"""Test for support of the Mac Carbon library.  This library
		can be used to obtain Finder info (creator/type)."""
		try:
			import Carbon.File
			import MacOS
		except:
			self.carbonfile = 0
			return

		try: x = Carbon.File.FSSpec('.')
		except:
			self.carbonfile = 0
			return

		self.carbonfile = 1

	def set_resource_fork_readwrite(self, dir_rp):
		"""Test for resource forks by writing to regular_file/..namedfork/rsrc"""
		assert dir_rp.conn is Globals.local_connection
		reg_rp = dir_rp.append('regfile')
		reg_rp.touch()

		s = 'test string---this should end up in resource fork'
		try:
			fp_write = open(os.path.join(reg_rp.path, '..namedfork', 'rsrc'), 'wb')
			fp_write.write(s)
			assert not fp_write.close()

			fp_read = open(os.path.join(reg_rp.path, '..namedfork', 'rsrc'), 'rb')
			s_back = fp_read.read()
			assert not fp_read.close()
		except (OSError, IOError): self.resource_forks = 0
		else: self.resource_forks = (s_back == s)
		reg_rp.delete()

	def set_resource_fork_readonly(self, dir_rp):
		"""Test for resource fork support by testing an regular file

		Launches search for regular file in given directory.  If no
		regular file is found, resource_fork support will be turned
		off by default.

		"""
		for rp in selection.Select(dir_rp).set_iter():
			if rp.isreg():
				try:
					rfork = rp.append(os.path.join('..namedfork', 'rsrc'))
					fp = rfork.open('rb')
					fp.read()
					assert not fp.close()
				except (OSError, IOError):
					self.resource_forks = 0
					return
				self.resource_forks = 1
				return
		self.resource_forks = 0

	def set_high_perms_readwrite(self, dir_rp):
		"""Test for writing high-bit permissions like suid"""
		tmp_rp = dir_rp.append("high_perms")
		tmp_rp.touch()
		try:
			tmp_rp.chmod(07000)
			tmp_rp.chmod(07777)
		except (OSError, IOError): self.high_perms = 0
		else: self.high_perms = 1
		tmp_rp.delete()

	def set_symlink_perms(self, dir_rp):
		"""Test if symlink permissions are affected by umask"""
		sym_source = dir_rp.append("symlinked_file1")
		sym_source.touch()
		sym_dest = dir_rp.append("symlinked_file2")
		sym_dest.symlink(sym_source.path)
		sym_dest.setdata()
		assert sym_dest.issym()
		orig_umask = os.umask(077)
		if sym_dest.getperms() == 0700: self.symlink_perms = 1
		else: self.symlink_perms = 0
		os.umask(orig_umask)
		sym_dest.delete()
		sym_source.delete()

	def set_escape_dos_devices(self, subdir):
		"""If special file aux can be stat'd, escape special files"""
		device_rp = subdir.append("aux")
		if device_rp.lstat():
			assert device_rp.lstat()
			log.Log("escape_dos_devices required by filesystem at %s" \
					% (subdir.path), 4)
			self.escape_dos_devices = 1
		else:
			assert not device_rp.lstat()
			log.Log("escape_dos_devices not required by filesystem at %s" \
					% (subdir.path), 4)
			self.escape_dos_devices = 0

def get_readonly_fsa(desc_string, rp):
	"""Return an fsa with given description_string

	Will be initialized read_only with given RPath rp.  We separate
	this out into a separate function so the request can be vetted by
	the security module.

	"""
	return FSAbilities(desc_string).init_readonly(rp)

	def set_escape_dos_devices(self):
		SetConnections.UpdateGlobal('escape_dos_devices', \
									self.dest_fsa.escape_dos_devices)

class SetGlobals:
	"""Various functions for setting Globals vars given FSAbilities above

	Container for BackupSetGlobals and RestoreSetGlobals (don't use directly)

	"""
	def __init__(self, in_conn, out_conn, src_fsa, dest_fsa):
		"""Just store some variables for use below"""
		self.in_conn, self.out_conn = in_conn, out_conn
		self.src_fsa, self.dest_fsa = src_fsa, dest_fsa

	def set_eas(self):
		self.update_triple(self.src_fsa.eas, self.dest_fsa.eas,
						   ('eas_active', 'eas_write', 'eas_conn'))

	def set_acls(self):
		self.update_triple(self.src_fsa.acls, self.dest_fsa.acls,
						   ('acls_active', 'acls_write', 'acls_conn'))
		if Globals.never_drop_acls and not Globals.acls_active:
			log.Log.FatalError("--never-drop-acls specified, but ACL support\n"
							   "missing from destination filesystem")

	def set_resource_forks(self):
		self.update_triple(self.src_fsa.resource_forks,
						   self.dest_fsa.resource_forks,
						   ('resource_forks_active', 'resource_forks_write',
							'resource_forks_conn'))

	def set_carbonfile(self):
		self.update_triple(self.src_fsa.carbonfile, self.dest_fsa.carbonfile,
			  ('carbonfile_active', 'carbonfile_write', 'carbonfile_conn'))

	def set_hardlinks(self):
		if Globals.preserve_hardlinks != 0:
			SetConnections.UpdateGlobal('preserve_hardlinks',
										self.dest_fsa.hardlinks)

	def set_fsync_directories(self):
		SetConnections.UpdateGlobal('fsync_directories',
									self.dest_fsa.fsync_dirs)

	def set_change_ownership(self):
		SetConnections.UpdateGlobal('change_ownership',
									self.dest_fsa.ownership)

	def set_high_perms(self):
		if not self.dest_fsa.high_perms:
			SetConnections.UpdateGlobal('permission_mask', 0777)

	def set_symlink_perms(self):
		SetConnections.UpdateGlobal('symlink_perms',
									self.dest_fsa.symlink_perms)

class BackupSetGlobals(SetGlobals):
	"""Functions for setting fsa related globals for backup session"""
	def update_triple(self, src_support, dest_support, attr_triple):
		"""Many of the settings have a common form we can handle here"""
		active_attr, write_attr, conn_attr = attr_triple
		if Globals.get(active_attr) == 0: return # don't override 0
		for attr in attr_triple: SetConnections.UpdateGlobal(attr, None)
		if not src_support: return # if source doesn't support, nothing
		SetConnections.UpdateGlobal(active_attr, 1)
		self.in_conn.Globals.set_local(conn_attr, 1)
		if dest_support:
			SetConnections.UpdateGlobal(write_attr, 1)
			self.out_conn.Globals.set_local(conn_attr, 1)

	def set_must_escape_dos_devices(self, rbdir):
		"""If local edd or src edd, then must escape """
		device_rp = rbdir.append("aux")
		if device_rp.lstat(): local_edd = 1
		else: local_edd = 0
		SetConnections.UpdateGlobal('must_escape_dos_devices', \
			self.src_fsa.escape_dos_devices or local_edd)
		log.Log("Backup: must_escape_dos_devices = %d" % \
				(self.src_fsa.escape_dos_devices or local_edd), 4)

	def set_chars_to_quote(self, rbdir):
		"""Set chars_to_quote setting for backup session

		Unlike the other options, the chars_to_quote setting also
		depends on the current settings in the rdiff-backup-data
		directory, not just the current fs features.

		"""
		ctq = self.compare_ctq_file(rbdir, self.get_ctq_from_fsas())

		SetConnections.UpdateGlobal('chars_to_quote', ctq)
		if Globals.chars_to_quote: FilenameMapping.set_init_quote_vals()

	def get_ctq_from_fsas(self):
		"""Determine chars_to_quote just from filesystems, no ctq file"""
		if self.src_fsa.case_sensitive and not self.dest_fsa.case_sensitive:
			if self.dest_fsa.extended_filenames:
				return "A-Z;" # Quote upper case and quoting char
			# Quote the following 0 - 31, ", *, /, :, <, >, ?, \, |, ;
			# Also quote uppercase A-Z
			else: return 'A-Z\000-\037\"*/:<>?\\\\|\177;'

		if self.dest_fsa.extended_filenames:
			return "" # Don't quote anything
		else: return '\000-\037\"*/:<>?\\\\|\177;'

	def compare_ctq_file(self, rbdir, suggested_ctq):
		"""Compare ctq file with suggested result, return actual ctq"""
		ctq_rp = rbdir.append("chars_to_quote")
		if not ctq_rp.lstat():
			if Globals.chars_to_quote is None: actual_ctq = suggested_ctq
			else: actual_ctq = Globals.chars_to_quote
			ctq_rp.write_string(actual_ctq)
			return actual_ctq

		if Globals.chars_to_quote is None: actual_ctq = ctq_rp.get_data()
		else: actual_ctq = Globals.chars_to_quote # Globals override

		if actual_ctq == suggested_ctq: return actual_ctq
		if suggested_ctq == "":
			log.Log("Warning: File system no longer needs quoting, "
					"but we will retain for backwards compatibility.", 2)
			return actual_ctq
		if Globals.chars_to_quote is None:
			log.Log.FatalError("""New quoting requirements!

The quoting chars this session needs (%s) do not match
the repository settings (%s) listed in

%s

This may be caused when you copy an rdiff-backup repository from a
normal file system onto a windows one that cannot support the same
characters, or if you backup a case-sensitive file system onto a
case-insensitive one that previously only had case-insensitive ones
backed up onto it.""" % (suggested_ctq, actual_ctq, ctq_rp.path))


class RestoreSetGlobals(SetGlobals):
	"""Functions for setting fsa-related globals for restore session"""
	def update_triple(self, src_support, dest_support, attr_triple):
		"""Update global settings for feature based on fsa results

		This is slightly different from BackupSetGlobals.update_triple
		because (using the mirror_metadata file) rpaths from the
		source may have more information than the file system
		supports.

		"""
		active_attr, write_attr, conn_attr = attr_triple
		if Globals.get(active_attr) == 0: return # don't override 0
		for attr in attr_triple: SetConnections.UpdateGlobal(attr, None)
		if not dest_support: return # if dest doesn't support, do nothing
		SetConnections.UpdateGlobal(active_attr, 1)
		self.out_conn.Globals.set_local(conn_attr, 1)
		self.out_conn.Globals.set_local(write_attr, 1)
		if src_support: self.in_conn.Globals.set_local(conn_attr, 1)

	def set_must_escape_dos_devices(self, rbdir):
		"""If local edd or src edd, then must escape """
		device_rp = rbdir.append("aux")
		if device_rp.lstat(): local_edd = 1
		else: local_edd = 0
		SetConnections.UpdateGlobal('must_escape_dos_devices', \
			self.src_fsa.escape_dos_devices or local_edd)
		log.Log("Restore: must_escape_dos_devices = %d" % \
				(self.src_fsa.escape_dos_devices or local_edd), 4)

	def set_chars_to_quote(self, rbdir):
		"""Set chars_to_quote from rdiff-backup-data dir"""
		if Globals.chars_to_quote is not None: return # already overridden
		
		ctq_rp = rbdir.append("chars_to_quote")
		if ctq_rp.lstat():
			SetConnections.UpdateGlobal("chars_to_quote", ctq_rp.get_data())
		else:
			log.Log("Warning: chars_to_quote file not found,\n"
					"assuming no quoting in backup repository.", 2)
			SetConnections.UpdateGlobal("chars_to_quote", "")


class SingleSetGlobals(RestoreSetGlobals):
	"""For setting globals when dealing only with one filesystem"""
	def __init__(self, conn, fsa):
		self.conn = conn
		self.dest_fsa = fsa

	def update_triple(self, fsa_support, attr_triple):
		"""Update global vars from single fsa test"""
		active_attr, write_attr, conn_attr = attr_triple
		if Globals.get(active_attr) == 0: return # don't override 0
		for attr in attr_triple: SetConnections.UpdateGlobal(attr, None)
		if not fsa_support: return
		SetConnections.UpdateGlobal(active_attr, 1)
		SetConnections.UpdateGlobal(write_attr, 1)
		self.conn.Globals.set_local(conn_attr, 1)

	def set_eas(self):
		self.update_triple(self.dest_fsa.eas,
						   ('eas_active', 'eas_write', 'eas_conn'))
	def set_acls(self):
		self.update_triple(self.dest_fsa.acls,
						  ('acls_active', 'acls_write', 'acls_conn'))
	def set_resource_forks(self):
		self.update_triple(self.dest_fsa.resource_forks,
						   ('resource_forks_active',
							'resource_forks_write', 'resource_forks_conn'))
	def set_carbonfile(self):
		self.update_triple(self.dest_fsa.carbonfile,
			 ('carbonfile_active', 'carbonfile_write', 'carbonfile_conn'))


def backup_set_globals(rpin):
	"""Given rps for source filesystem and repository, set fsa globals

	This should be run on the destination connection, because we may
	need to write a new chars_to_quote file.

	"""
	assert Globals.rbdir.conn is Globals.local_connection
	src_fsa = rpin.conn.fs_abilities.get_readonly_fsa('source', rpin)
	log.Log(str(src_fsa), 4)
	dest_fsa = FSAbilities('destination').init_readwrite(Globals.rbdir)
	log.Log(str(dest_fsa), 4)

	bsg = BackupSetGlobals(rpin.conn, Globals.rbdir.conn, src_fsa, dest_fsa)
	bsg.set_eas()
	bsg.set_acls()
	bsg.set_resource_forks()
	bsg.set_carbonfile()
	bsg.set_hardlinks()
	bsg.set_fsync_directories()
	bsg.set_change_ownership()
	bsg.set_high_perms()
	bsg.set_symlink_perms()
	bsg.set_chars_to_quote(Globals.rbdir)
	bsg.set_escape_dos_devices()
	bsg.set_must_escape_dos_devices(Globals.rbdir)

def restore_set_globals(rpout):
	"""Set fsa related globals for restore session, given in/out rps"""
	assert rpout.conn is Globals.local_connection
	src_fsa = Globals.rbdir.conn.fs_abilities.get_readonly_fsa(
		                  'rdiff-backup repository', Globals.rbdir)
	log.Log(str(src_fsa), 4)
	dest_fsa = FSAbilities('restore target').init_readwrite(rpout)
	log.Log(str(dest_fsa), 4)

	rsg = RestoreSetGlobals(Globals.rbdir.conn, rpout.conn, src_fsa, dest_fsa)
	rsg.set_eas()
	rsg.set_acls()
	rsg.set_resource_forks()
	rsg.set_carbonfile()
	rsg.set_hardlinks()
	# No need to fsync anything when restoring
	rsg.set_change_ownership()
	rsg.set_high_perms()
	rsg.set_symlink_perms()
	rsg.set_chars_to_quote(Globals.rbdir)
	rsg.set_escape_dos_devices()
	rsg.set_must_escape_dos_devices(Globals.rbdir)

def single_set_globals(rp, read_only = None):
	"""Set fsa related globals for operation on single filesystem"""
	if read_only:
		fsa = rp.conn.fs_abilities.get_readonly_fsa(rp.path, rp)
	else: fsa = FSAbilities(rp.path).init_readwrite(rp)
	log.Log(str(fsa), 4)

	ssg = SingleSetGlobals(rp.conn, fsa)
	ssg.set_eas()
	ssg.set_acls()
	ssg.set_resource_forks()
	ssg.set_carbonfile()
	if not read_only:
		ssg.set_hardlinks()
		ssg.set_change_ownership()
		ssg.set_high_perms()
		ssg.set_symlink_perms()
	ssg.set_chars_to_quote(Globals.rbdir)
	ssg.set_escape_dos_devices()
	ssg.set_must_escape_dos_devices(Globals.rbdir)

