# Copyright 2002, 2003 Ben Escoto
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

"""Wrapper class around a real path like "/usr/bin/env"

The RPath (short for Remote Path) and associated classes make some
function calls more convenient and also make working with files on
remote systems transparent.

For instance, suppose

rp = RPath(connection_object, "/usr/bin/env")

Then rp.getperms() returns the permissions of that file, and
rp.delete() deletes that file.  Both of these will work the same even
if "usr/bin/env" is on a different computer.  So many rdiff-backup
functions use rpaths so they don't have to know whether the files they
are dealing with are local or remote.

"""

import os, stat, re, sys, shutil, gzip, socket, time
import Globals, Time, static, log, user_group


class SkipFileException(Exception):
	"""Signal that the current file should be skipped but then continue

	This exception will often be raised when there is problem reading
	an individual file, but it makes sense for the rest of the backup
	to keep going.

	"""
	pass

class RPathException(Exception): pass

def copyfileobj(inputfp, outputfp):
	"""Copies file inputfp to outputfp in blocksize intervals"""
	blocksize = Globals.blocksize
	while 1:
		inbuf = inputfp.read(blocksize)
		if not inbuf: break
		outputfp.write(inbuf)

def cmpfileobj(fp1, fp2):
	"""True if file objects fp1 and fp2 contain same data"""
	blocksize = Globals.blocksize
	while 1:
		buf1 = fp1.read(blocksize)
		buf2 = fp2.read(blocksize)
		if buf1 != buf2: return None
		elif not buf1: return 1

def check_for_files(*rps):
	"""Make sure that all the rps exist, raise error if not"""
	for rp in rps:
		if not rp.lstat():
			raise RPathException("File %s does not exist" % rp.get_indexpath())

def move(rpin, rpout):
	"""Move rpin to rpout, renaming if possible"""
	try: rename(rpin, rpout)
	except os.error:
		copy(rpin, rpout)
		rpin.delete()

def copy(rpin, rpout, compress = 0):
	"""Copy RPath rpin to rpout.  Works for symlinks, dirs, etc."""
	log.Log("Regular copying %s to %s" % (rpin.index, rpout.path), 6)
	if not rpin.lstat():
		if rpout.lstat(): rpout.delete()
		return

	if rpout.lstat():
		if rpin.isreg() or not cmp(rpin, rpout):
			rpout.delete()   # easier to write than compare
		else: return

	if rpin.isreg(): copy_reg_file(rpin, rpout, compress)
	elif rpin.isdir(): rpout.mkdir()
	elif rpin.issym(): rpout.symlink(rpin.readlink())
	elif rpin.ischardev():
		major, minor = rpin.getdevnums()
		rpout.makedev("c", major, minor)
	elif rpin.isblkdev():
		major, minor = rpin.getdevnums()
		rpout.makedev("b", major, minor)
	elif rpin.isfifo(): rpout.mkfifo()
	elif rpin.issock(): rpout.mksock()
	else: raise RPathException("File %s has unknown type" % rpin.path)

def copy_reg_file(rpin, rpout, compress = 0):
	"""Copy regular file rpin to rpout, possibly avoiding connection"""
	try:
		if (rpout.conn is rpin.conn and
			rpout.conn is not Globals.local_connection):
			rpout.conn.rpath.copy_reg_file(rpin.path, rpout.path, compress)
			rpout.setdata()
			return
	except AttributeError: pass
	rpout.write_from_fileobj(rpin.open("rb"), compress = compress)

def cmp(rpin, rpout):
	"""True if rpin has the same data as rpout

	cmp does not compare file ownership, permissions, or times, or
	examine the contents of a directory.

	"""
	check_for_files(rpin, rpout)
	if rpin.isreg():
		if not rpout.isreg(): return None
		fp1, fp2 = rpin.open("rb"), rpout.open("rb")
		result = cmpfileobj(fp1, fp2)
		if fp1.close() or fp2.close():
			raise RPathException("Error closing file")
		return result
	elif rpin.isdir(): return rpout.isdir()
	elif rpin.issym():
		return rpout.issym() and (rpin.readlink() == rpout.readlink())
	elif rpin.ischardev():
		return rpout.ischardev() and (rpin.getdevnums() == rpout.getdevnums())
	elif rpin.isblkdev():
		return rpout.isblkdev() and (rpin.getdevnums() == rpout.getdevnums())
	elif rpin.isfifo(): return rpout.isfifo()
	elif rpin.issock(): return rpout.issock()
	else: raise RPathException("File %s has unknown type" % rpin.path)

def copy_attribs(rpin, rpout):
	"""Change file attributes of rpout to match rpin

	Only changes the chmoddable bits, uid/gid ownership, and
	timestamps, so both must already exist.

	"""
	log.Log("Copying attributes from %s to %s" % (rpin.index, rpout.path), 7)
	assert rpin.lstat() == rpout.lstat() or rpin.isspecial()
	if rpin.issym(): return # symlinks have no valid attributes
	if Globals.resource_forks_write and rpin.isreg():
		rpout.write_resource_fork(rpin.get_resource_fork())
	if Globals.eas_write: rpout.write_ea(rpin.get_ea())
	if Globals.change_ownership: rpout.chown(*user_group.map_rpath(rpin))
	rpout.chmod(rpin.getperms())
	if Globals.acls_write: rpout.write_acl(rpin.get_acl())
	if not rpin.isdev(): rpout.setmtime(rpin.getmtime())

def copy_attribs_inc(rpin, rpout):
	"""Change file attributes of rpout to match rpin

	Like above, but used to give increments the same attributes as the
	originals.  Therefore, don't copy all directory acl and
	permissions.

	"""
	log.Log("Copying inc attrs from %s to %s" % (rpin.index, rpout.path), 7)
	check_for_files(rpin, rpout)
	if rpin.issym(): return # symlinks have no valid attributes
	if Globals.resource_forks_write and rpin.isreg() and rpout.isreg():
		rpout.write_resource_fork(rpin.get_resource_fork())
	if Globals.eas_write: rpout.write_ea(rpin.get_ea())
	if Globals.change_ownership: apply(rpout.chown, rpin.getuidgid())
	if rpin.isdir() and not rpout.isdir():
		rpout.chmod(rpin.getperms() & 0777)
	else: rpout.chmod(rpin.getperms())
	if Globals.acls_write: rpout.write_acl(rpin.get_acl(), map_names = 0)
	if not rpin.isdev(): rpout.setmtime(rpin.getmtime())

def cmp_attribs(rp1, rp2):
	"""True if rp1 has the same file attributes as rp2

	Does not compare file access times.  If not changing
	ownership, do not check user/group id.

	"""
	check_for_files(rp1, rp2)
	if Globals.change_ownership and rp1.getuidgid() != rp2.getuidgid():
		result = None
	elif rp1.getperms() != rp2.getperms(): result = None
	# Don't compare ctime for now, add later
	#elif rp1.getctime() != rp2.getctime(): result = None
	elif rp1.issym() and rp2.issym(): # Don't check times for some types
		result = 1
	elif rp1.isblkdev() and rp2.isblkdev(): result = 1
	elif rp1.ischardev() and rp2.ischardev(): result = 1
	else: result = (rp1.getmtime() == rp2.getmtime())
	log.Log("Compare attribs of %s and %s: %s" %
			(rp1.get_indexpath(), rp2.get_indexpath(), result), 7)
	return result

def copy_with_attribs(rpin, rpout, compress = 0):
	"""Copy file and then copy over attributes"""
	copy(rpin, rpout, compress)
	if rpin.lstat(): copy_attribs(rpin, rpout)

def rename(rp_source, rp_dest):
	"""Rename rp_source to rp_dest"""
	assert rp_source.conn is rp_dest.conn
	log.Log(lambda: "Renaming %s to %s" % (rp_source.path, rp_dest.path), 7)
	if not rp_source.lstat(): rp_dest.delete()
	else:
		if rp_dest.lstat() and rp_source.getinode() == rp_dest.getinode():
			log.Log("Warning: Attempt to rename over same inode: %s to %s"
					% (rp_source.path, rp_dest.path), 2)
			# You can't rename one hard linked file over another
			rp_source.delete()
		else: rp_source.conn.os.rename(rp_source.path, rp_dest.path)
		rp_dest.data = rp_source.data
		rp_source.data = {'type': None}

def tupled_lstat(filename):
	"""Like os.lstat, but return only a tuple, or None if os.error

	Later versions of os.lstat return a special lstat object,
	which can confuse the pickler and cause errors in remote
	operations.  This has been fixed in Python 2.2.1.

	"""
	try: return tuple(os.lstat(filename))
	except os.error: return None

def make_socket_local(rpath):
	"""Make a local socket at the given path

	This takes an rpath so that it will be checked by Security.
	(Miscellaneous strings will not be.)

	"""
	assert rpath.conn is Globals.local_connection
	s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
	try: s.bind(rpath.path)
	except socket.error, exc:
		raise SkipFileException("Socket error: " + str(exc))

def gzip_open_local_read(rpath):
	"""Return open GzipFile.  See security note directly above"""
	assert rpath.conn is Globals.local_connection
	return gzip.GzipFile(rpath.path, "rb")

def open_local_read(rpath):
	"""Return open file (provided for security reasons)"""
	assert rpath.conn is Globals.local_connection
	return open(rpath.path, "rb")


class RORPath:
	"""Read Only RPath - carry information about a path

	These contain information about a file, and possible the file's
	data, but do not have a connection and cannot be written to or
	changed.  The advantage of these objects is that they can be
	communicated by encoding their index and data dictionary.

	"""
	def __init__(self, index, data = None):
		self.index = index
		if data: self.data = data
		else: self.data = {'type':None} # signify empty file
		self.file = None

	def zero(self):
		"""Set inside of self to type None"""
		self.data = {'type': None}
		self.file = None

	def __nonzero__(self): return 1

	def __eq__(self, other):
		"""True iff the two rorpaths are equivalent"""
		if self.index != other.index: return None

		for key in self.data.keys(): # compare dicts key by key
			if self.issym() and key in ('uid', 'gid', 'uname', 'gname'):
				pass # Don't compare gid/uid for symlinks
			elif key == 'atime' and not Globals.preserve_atime: pass
			elif key == 'ctime': pass
			elif key == 'devloc' or key == 'nlink': pass
			elif key == 'size' and not self.isreg(): pass
			elif key == 'ea' and not Globals.eas_active: pass
			elif key == 'acl' and not Globals.acls_active: pass
			elif key == 'resourcefork' and not Globals.resource_forks_active:
				pass
			elif ((key == 'uname' or key == 'gname') and
				  not other.data.has_key(key)):
				pass # legacy reasons - 0.12.x didn't store u/gnames
			elif (key == 'inode' and
				  (not self.isreg() or self.getnumlinks() == 1 or
				   not Globals.compare_inode or
				   not Globals.preserve_hardlinks)):
				pass
			else:
				try: other_val = other.data[key]
				except KeyError: return None
				if self.data[key] != other.data[key]: return None
		return 1

	def equal_loose(self, other):
		"""True iff the two rorpaths are kinda equivalent

		Sometimes because permissions cannot be set, a file cannot be
		replicated exactly on the remote side.  This function tells
		you whether the two files are close enough.  self must be the
		original rpath.

		"""
		for key in self.data.keys(): # compare dicts key by key
			if key in ('uid', 'gid', 'uname', 'gname'): pass
			elif (key == 'type' and self.isspecial() and
				  other.isreg() and other.getsize() == 0):
				pass # Special files may be replaced with empty regular files
			elif key == 'atime' and not Globals.preserve_atime: pass
			elif key == 'ctime': pass
			elif key == 'devloc' or key == 'nlink': pass
			elif key == 'size' and not self.isreg(): pass
			elif key == 'inode': pass
			elif key == 'ea' and not Globals.eas_write: pass
			elif key == 'acl' and not Globals.acls_write: pass
			elif key == 'resourcefork' and not Globals.resource_forks_write:
				pass
			elif (not other.data.has_key(key) or
				  self.data[key] != other.data[key]): return 0

		if self.lstat() and not self.issym() and Globals.change_ownership:
			# Now compare ownership.  Symlinks don't have ownership
			if user_group.map_rpath(self) != other.getuidgid(): return 0

		return 1

	def equal_verbose(self, other, check_index = 1,
					  compare_inodes = 0, compare_ownership = 0,
					  compare_acls = 0, compare_eas = 0):
		"""Like __eq__, but log more information.  Useful when testing"""
		if check_index and self.index != other.index:
			log.Log("Index %s != index %s" % (self.index, other.index), 2)
			return None

		for key in self.data.keys(): # compare dicts key by key
			if (key in ('uid', 'gid', 'uname', 'gname') and
				(self.issym() or not compare_ownership)):
				# Don't compare gid/uid for symlinks, or if told not to
				pass
			elif key == 'atime' and not Globals.preserve_atime: pass
			elif key == 'ctime': pass
			elif key == 'devloc' or key == 'nlink': pass
			elif key == 'size' and not self.isreg(): pass
			elif key == 'inode' and (not self.isreg() or not compare_inodes):
				pass
			elif key == 'ea' and not compare_eas: pass
			elif key == 'acl' and not compare_acls: pass
			elif (not other.data.has_key(key) or
				  self.data[key] != other.data[key]):
				if not other.data.has_key(key):
					log.Log("Second is missing key %s" % (key,), 2)
				else: log.Log("Value of %s differs: %s vs %s" %
							  (key, self.data[key], other.data[key]), 2)
				return None
		return 1

	def __ne__(self, other): return not self.__eq__(other)

	def __str__(self):
		"""Pretty print file statistics"""
		return "Index: %s\nData: %s" % (self.index, self.data)

	def summary_string(self):
		"""Return summary string"""
		return "%s %s" % (self.get_indexpath(), self.lstat())

	def __getstate__(self):
		"""Return picklable state

		This is necessary in case the RORPath is carrying around a
		file object, which can't/shouldn't be pickled.

		"""
		return (self.index, self.data)

	def __setstate__(self, rorp_state):
		"""Reproduce RORPath from __getstate__ output"""
		self.index, self.data = rorp_state

	def getRORPath(self):
		"""Return new rorpath based on self"""
		return RORPath(self.index, self.data.copy())

	def lstat(self):
		"""Returns type of file

		The allowable types are None if the file doesn't exist, 'reg'
		for a regular file, 'dir' for a directory, 'dev' for a device
		file, 'fifo' for a fifo, 'sock' for a socket, and 'sym' for a
		symlink.
		
		"""
		return self.data['type']
	gettype = lstat

	def isdir(self):
		"""True if self is a dir"""
		return self.data['type'] == 'dir'

	def isreg(self):
		"""True if self is a regular file"""
		return self.data['type'] == 'reg'

	def issym(self):
		"""True if path is of a symlink"""
		return self.data['type'] == 'sym'

	def isfifo(self):
		"""True if path is a fifo"""
		return self.data['type'] == 'fifo'

	def ischardev(self):
		"""True if path is a character device file"""
		return self.data['type'] == 'dev' and self.data['devnums'][0] == 'c'

	def isblkdev(self):
		"""True if path is a block device file"""
		return self.data['type'] == 'dev' and self.data['devnums'][0] == 'b'

	def isdev(self):
		"""True if path is a device file"""
		return self.data['type'] == 'dev'

	def issock(self):
		"""True if path is a socket"""
		return self.data['type'] == 'sock'

	def isspecial(self):
		"""True if the file is a sock, symlink, device, or fifo"""
		type = self.data['type']
		return (type == 'dev' or type == 'sock' or
				type == 'fifo' or type == 'sym')

	def getperms(self):
		"""Return permission block of file"""
		return self.data['perms']

	def getuname(self):
		"""Return username that owns the file"""
		try: return self.data['uname']
		except KeyError: return None

	def getgname(self):
		"""Return groupname that owns the file"""
		try: return self.data['gname']
		except KeyError: return None

	def hassize(self):
		"""True if rpath has a size parameter"""
		return self.data.has_key('size')

	def getsize(self):
		"""Return length of file in bytes"""
		return self.data['size']

	def getuidgid(self):
		"""Return userid/groupid of file"""
		return self.data['uid'], self.data['gid']

	def getatime(self):
		"""Return access time in seconds"""
		return self.data['atime']

	def getmtime(self):
		"""Return modification time in seconds"""
		return self.data['mtime']

	def getctime(self):
		"""Return change time in seconds"""
		return self.data['ctime']
	
	def getinode(self):
		"""Return inode number of file"""
		return self.data['inode']

	def getdevloc(self):
		"""Device number file resides on"""
		return self.data['devloc']

	def getnumlinks(self):
		"""Number of places inode is linked to"""
		if self.data.has_key('nlink'): return self.data['nlink']
		else: return 1

	def readlink(self):
		"""Wrapper around os.readlink()"""
		return self.data['linkname']

	def getdevnums(self):
		"""Return a devices major/minor numbers from dictionary"""
		return self.data['devnums'][1:]

	def setfile(self, file):
		"""Right now just set self.file to be the already opened file"""
		assert file and not self.file
		def closing_hook(): self.file_already_open = None
		self.file = RPathFileHook(file, closing_hook)
		self.file_already_open = None

	def get_indexpath(self):
		"""Return path of index portion

		For instance, if the index is ("a", "b"), return "a/b".

		"""
		if not self.index: return "."
		return "/".join(self.index)

	def get_attached_filetype(self):
		"""If there is a file attached, say what it is

		Currently the choices are 'snapshot' meaning an exact copy of
		something, and 'diff' for an rdiff style diff.

		"""
		return self.data['filetype']
	
	def set_attached_filetype(self, type):
		"""Set the type of the attached file"""
		self.data['filetype'] = type

	def isflaglinked(self):
		"""True if rorp is a signature/diff for a hardlink file

		This indicates that a file's data need not be transferred
		because it is hardlinked on the remote side.

		"""
		return self.data.has_key('linked')

	def get_link_flag(self):
		"""Return previous index that a file is hard linked to"""
		return self.data['linked']

	def flaglinked(self, index):
		"""Signal that rorp is a signature/diff for a hardlink file"""
		self.data['linked'] = index

	def open(self, mode):
		"""Return file type object if any was given using self.setfile"""
		if mode != "rb": raise RPathException("Bad mode %s" % mode)
		if self.file_already_open:
			raise RPathException("Attempt to open same file twice")
		self.file_already_open = 1
		return self.file

	def close_if_necessary(self):
		"""If file is present, discard data and close"""
		if self.file:
			while self.file.read(Globals.blocksize): pass
			assert not self.file.close(), \
			  "Error closing file\ndata = %s\nindex = %s\n" % (self.data,
															   self.index)
			self.file_already_open = None

	def set_acl(self, acl):
		"""Record access control list in dictionary.  Does not write"""
		self.data['acl'] = acl

	def get_acl(self):
		"""Return access control list object from dictionary"""
		return self.data['acl']

	def set_ea(self, ea):
		"""Record extended attributes in dictionary.  Does not write"""
		self.data['ea'] = ea

	def get_ea(self):
		"""Return extended attributes object"""
		return self.data['ea']

	def has_resource_fork(self):
		"""True if rpath has a resourcefork parameter"""
		return self.data.has_key('resourcefork')

	def get_resource_fork(self):
		"""Return the resource fork in binary data"""
		return self.data['resourcefork']

	def set_resource_fork(self, rfork):
		"""Record resource fork in dictionary.  Does not write"""
		self.data['resourcefork'] = rfork


class RPath(RORPath):
	"""Remote Path class - wrapper around a possibly non-local pathname

	This class contains a dictionary called "data" which should
	contain all the information about the file sufficient for
	identification (i.e. if two files have the the same (==) data
	dictionary, they are the same file).

	"""
	regex_chars_to_quote = re.compile("[\\\\\\\"\\$`]")

	def __init__(self, connection, base, index = (), data = None):
		"""RPath constructor

		connection = self.conn is the Connection the RPath will use to
		make system calls, and index is the name of the rpath used for
		comparison, and should be a tuple consisting of the parts of
		the rpath after the base split up.  For instance ("foo",
		"bar") for "foo/bar" (no base), and ("local", "bin") for
		"/usr/local/bin" if the base is "/usr".

		For the root directory "/", the index is empty and the base is
		"/".

		"""
		self.conn = connection
		self.index = index
		self.base = base
		if base is not None:
			if base == "/": self.path = "/" + "/".join(index)
			else: self.path = "/".join((base,) + index)
		self.file = None
		if data or base is None: self.data = data
		else: self.setdata()

	def __str__(self):
		return "Path: %s\nIndex: %s\nData: %s" % (self.path, self.index,
												  self.data)

	def __getstate__(self):
		"""Return picklable state

		The connection must be local because we can't pickle a
		connection.  Data and any attached file also won't be saved.

		"""
		assert self.conn is Globals.local_connection
		return (self.index, self.base, self.data)

	def __setstate__(self, rpath_state):
		"""Reproduce RPath from __getstate__ output"""
		self.conn = Globals.local_connection
		self.index, self.base, self.data = rpath_state
		self.path = "/".join((self.base,) + self.index)

	def setdata(self):
		"""Set data dictionary using C extension"""
		self.data = self.conn.C.make_file_dict(self.path)
		if self.lstat(): self.conn.rpath.setdata_local(self)

	def make_file_dict_old(self):
		"""Create the data dictionary"""
		statblock = self.conn.rpath.tupled_lstat(self.path)
		if statblock is None:
			return {'type':None}
		data = {}
		mode = statblock[stat.ST_MODE]

		if stat.S_ISREG(mode): type = 'reg'
		elif stat.S_ISDIR(mode): type = 'dir'
		elif stat.S_ISCHR(mode):
			type = 'dev'
			data['devnums'] = ('c',) + self._getdevnums()
		elif stat.S_ISBLK(mode):
			type = 'dev'
			data['devnums'] = ('b',) + self._getdevnums()
		elif stat.S_ISFIFO(mode): type = 'fifo'
		elif stat.S_ISLNK(mode):
			type = 'sym'
			data['linkname'] = self.conn.os.readlink(self.path)
		elif stat.S_ISSOCK(mode): type = 'sock'
		else: raise C.UnknownFileError(self.path)
		data['type'] = type
		data['size'] = statblock[stat.ST_SIZE]
		data['perms'] = stat.S_IMODE(mode)
		data['uid'] = statblock[stat.ST_UID]
		data['gid'] = statblock[stat.ST_GID]
		data['inode'] = statblock[stat.ST_INO]
		data['devloc'] = statblock[stat.ST_DEV]
		data['nlink'] = statblock[stat.ST_NLINK]

		if not (type == 'sym' or type == 'dev'):
			# mtimes on symlinks and dev files don't work consistently
			data['mtime'] = long(statblock[stat.ST_MTIME])
			data['atime'] = long(statblock[stat.ST_ATIME])
			data['ctime'] = long(statblock[stat.ST_CTIME])
		return data

	def check_consistency(self):
		"""Raise an error if consistency of rp broken

		This is useful for debugging when the cache and disk get out
		of sync and you need to find out where it happened.

		"""
		temptype = self.data['type']
		self.setdata()
		assert temptype == self.data['type'], \
			   "\nName: %s\nOld: %s --> New: %s\n" % \
			   (self.path, temptype, self.data['type'])

	def _getdevnums(self):
		"""Return tuple for special file (major, minor)"""
		s = self.conn.reval("lambda path: os.lstat(path).st_rdev", self.path)
		return (s >> 8, s & 0xff)

	def chmod(self, permissions):
		"""Wrapper around os.chmod"""
		self.conn.os.chmod(self.path, permissions)
		self.data['perms'] = permissions

	def settime(self, accesstime, modtime):
		"""Change file modification times"""
		log.Log("Setting time of %s to %d" % (self.path, modtime), 7)
		self.conn.os.utime(self.path, (accesstime, modtime))
		self.data['atime'] = accesstime
		self.data['mtime'] = modtime

	def setmtime(self, modtime):
		"""Set only modtime (access time to present)"""
		log.Log(lambda: "Setting time of %s to %d" % (self.path, modtime), 7)
		self.conn.os.utime(self.path, (long(time.time()), modtime))
		self.data['mtime'] = modtime

	def chown(self, uid, gid):
		"""Set file's uid and gid"""
		self.conn.os.chown(self.path, uid, gid)
		self.data['uid'] = uid
		self.data['gid'] = gid

	def mkdir(self):
		log.Log("Making directory " + self.path, 6)
		self.conn.os.mkdir(self.path)
		self.setdata()

	def rmdir(self):
		log.Log("Removing directory " + self.path, 6)
		self.conn.os.rmdir(self.path)
		self.data = {'type': None}

	def listdir(self):
		"""Return list of string paths returned by os.listdir"""
		return self.conn.os.listdir(self.path)

	def symlink(self, linktext):
		"""Make symlink at self.path pointing to linktext"""
		self.conn.os.symlink(linktext, self.path)
		self.setdata()
		assert self.issym()

	def hardlink(self, linkpath):
		"""Make self into a hardlink joined to linkpath"""
		log.Log("Hard linking %s to %s" % (self.path, linkpath), 6)
		self.conn.os.link(linkpath, self.path)
		self.setdata()

	def mkfifo(self):
		"""Make a fifo at self.path"""
		self.conn.os.mkfifo(self.path)
		self.setdata()
		assert self.isfifo()

	def mksock(self):
		"""Make a socket at self.path"""
		self.conn.rpath.make_socket_local(self)
		self.setdata()
		assert self.issock()

	def touch(self):
		"""Make sure file at self.path exists"""
		log.Log("Touching " + self.path, 7)
		self.conn.open(self.path, "w").close()
		self.setdata()
		assert self.isreg(), self.path

	def hasfullperms(self):
		"""Return true if current process has full permissions on the file"""
		if self.isowner(): return self.getperms() % 01000 >= 0700
		elif self.isgroup(): return self.getperms() % 0100 >= 070
		else: return self.getperms() % 010 >= 07

	def readable(self):
		"""Return true if current process has read permissions on the file"""
		if self.isowner(): return self.getperms() % 01000 >= 0400
		elif self.isgroup(): return self.getperms() % 0100 >= 040
		else: return self.getperms() % 010 >= 04

	def executable(self):
		"""Return true if current process has execute permissions"""
		if self.isowner(): return self.getperms() % 0200 >= 0100
		elif self.isgroup(): return self.getperms() % 020 >= 010
		else: return self.getperms() % 02 >= 01
		
	def isowner(self):
		"""Return true if current process is owner of rp or root"""
		uid = self.conn.os.getuid()
		return uid == 0 or uid == self.data['uid']

	def isgroup(self):
		"""Return true if current process is in group of rp"""
		return self.conn.Globals.get('process_gid') == self.data['gid']

	def delete(self):
		"""Delete file at self.path.  Recursively deletes directories."""
		log.Log("Deleting %s" % self.path, 7)
		if self.isdir():
			try: self.rmdir()
			except os.error: self.conn.shutil.rmtree(self.path)
		else: self.conn.os.unlink(self.path)
		self.setdata()

	def quote(self):
		"""Return quoted self.path for use with os.system()"""
		return '"%s"' % self.regex_chars_to_quote.sub(
			lambda m: "\\"+m.group(0), self.path)

	def normalize(self):
		"""Return RPath canonical version of self.path

		This just means that redundant /'s will be removed, including
		the trailing one, even for directories.  ".." components will
		be retained.

		"""
		newpath = "/".join(filter(lambda x: x and x != ".",
								  self.path.split("/")))
		if self.path[0] == "/": newpath = "/" + newpath
		elif not newpath: newpath = "."
		return self.newpath(newpath)

	def dirsplit(self):
		"""Returns a tuple of strings (dirname, basename)

		Basename is never '' unless self is root, so it is unlike
		os.path.basename.  If path is just above root (so dirname is
		root), then dirname is ''.  In all other cases dirname is not
		the empty string.  Also, dirsplit depends on the format of
		self, so basename could be ".." and dirname could be a
		subdirectory.  For an atomic relative path, dirname will be
		'.'.

		"""
		normed = self.normalize()
		if normed.path.find("/") == -1: return (".", normed.path)
		comps = normed.path.split("/")
		return "/".join(comps[:-1]), comps[-1]

	def get_parent_rp(self):
		"""Return new RPath of directory self is in"""
		if self.index:
			return self.__class__(self.conn, self.base, self.index[:-1])
		dirname = self.dirsplit()[0]
		if dirname: return self.__class__(self.conn, dirname)
		else: return self.__class__(self.conn, "/")

	def newpath(self, newpath, index = ()):
		"""Return new RPath with the same connection but different path"""
		return self.__class__(self.conn, newpath, index)

	def append(self, ext):
		"""Return new RPath with same connection by adjoing ext"""
		return self.__class__(self.conn, self.base, self.index + (ext,))

	def append_path(self, ext, new_index = ()):
		"""Like append, but add ext to path instead of to index"""
		return self.__class__(self.conn, "/".join((self.base, ext)), new_index)

	def new_index(self, index):
		"""Return similar RPath but with new index"""
		return self.__class__(self.conn, self.base, index)

	def open(self, mode, compress = None):
		"""Return open file.  Supports modes "w" and "r".

		If compress is true, data written/read will be gzip
		compressed/decompressed on the fly.  The extra complications
		below are for security reasons - try to make the extent of the
		risk apparent from the remote call.

		"""
		if self.conn is Globals.local_connection:
			if compress: return gzip.GzipFile(self.path, mode)
			else: return open(self.path, mode)

		if compress:
			if mode == "r" or mode == "rb":
				return self.conn.rpath.gzip_open_local_read(self)
			else: return self.conn.gzip.GzipFile(self.path, mode)
		else:
			if mode == "r" or mode == "rb":
				return self.conn.rpath.open_local_read(self)
			else: return self.conn.open(self.path, mode)

	def write_from_fileobj(self, fp, compress = None):
		"""Reads fp and writes to self.path.  Closes both when done

		If compress is true, fp will be gzip compressed before being
		written to self.

		"""
		log.Log("Writing file object to " + self.path, 7)
		assert not self.lstat(), "File %s already exists" % self.path
		outfp = self.open("wb", compress = compress)
		copyfileobj(fp, outfp)
		if fp.close() or outfp.close():
			raise RPathException("Error closing file")
		self.setdata()

	def write_string(self, s, compress = None):
		"""Write string s into rpath"""
		assert not self.lstat(), "File %s already exists" % (self.path,)
		outfp = self.open("wb", compress = compress)
		outfp.write(s)
		assert not outfp.close()
		self.setdata()

	def isincfile(self):
		"""Return true if path looks like an increment file

		Also sets various inc information used by the *inc* functions.

		"""
		if self.index: dotsplit = self.index[-1].split(".")
		else: dotsplit = self.base.split(".")
		if dotsplit[-1] == "gz":
			compressed = 1
			if len(dotsplit) < 4: return None
			timestring, ext = dotsplit[-3:-1]
		else:
			compressed = None
			if len(dotsplit) < 3: return None
			timestring, ext = dotsplit[-2:]
		if Time.stringtotime(timestring) is None: return None
		if not (ext == "snapshot" or ext == "dir" or
				ext == "missing" or ext == "diff" or ext == "data"):
			return None
		self.inc_timestr = timestring
		self.inc_compressed = compressed
		self.inc_type = ext
		if compressed: self.inc_basestr = ".".join(dotsplit[:-3])
		else: self.inc_basestr = ".".join(dotsplit[:-2])
		return 1

	def isinccompressed(self):
		"""Return true if inc file is compressed"""
		return self.inc_compressed

	def getinctype(self):
		"""Return type of an increment file"""
		return self.inc_type

	def getinctime(self):
		"""Return time in seconds of an increment file"""
		return Time.stringtotime(self.inc_timestr)
	
	def getincbase(self):
		"""Return the base filename of an increment file in rp form"""
		if self.index:
			return self.__class__(self.conn, self.base, self.index[:-1] +
								  (self.inc_basestr,))
		else: return self.__class__(self.conn, self.inc_basestr)

	def getincbase_str(self):
		"""Return the base filename string of an increment file"""
		rp = self.getincbase()
		if rp.index: return rp.index[-1]
		else: return rp.dirsplit()[1]

	def makedev(self, type, major, minor):
		"""Make a special file with specified type, and major/minor nums"""
		cmdlist = ['mknod', self.path, type, str(major), str(minor)]
		if self.conn.os.spawnvp(os.P_WAIT, 'mknod', cmdlist) != 0:
			raise RPathException("Error running %s" % cmdlist)
		if type == 'c': datatype = 'chr'
		elif type == 'b': datatype = 'blk'
		else: raise RPathException
		self.setdata()

	def fsync(self, fp = None):
		"""fsync the current file or directory

		If fp is none, get the file description by opening the file.
		This can be useful for directories.

		"""
		if not fp: self.conn.rpath.RPath.fsync_local(self)
		else: os.fsync(fp.fileno())

	def fsync_local(self):
		"""fsync current file, run locally"""
		assert self.conn is Globals.local_connection
		fd = os.open(self.path, os.O_RDONLY)
		os.fsync(fd)
		os.close(fd)

	def fsync_with_dir(self, fp = None):
		"""fsync self and directory self is under"""
		self.fsync(fp)
		if Globals.fsync_directories: self.get_parent_rp().fsync()

	def sync_delete(self):
		"""Delete self with sync to guarantee completion

		On some filesystems (like linux's ext2), we must sync both the
		file and the directory to make sure.

		"""
		if self.lstat() and not self.issym():
			fp = self.open("rb")
			self.delete()
			os.fsync(fp.fileno())
		assert not fp.close()
		if Globals.fsync_directories: self.get_parent_rp().fsync()

	def get_data(self):
		"""Open file as a regular file, read data, close, return data"""
		fp = self.open("rb")
		s = fp.read()
		assert not fp.close()
		return s

	def get_acl(self):
		"""Return access control list object, setting if necessary"""
		try: acl = self.data['acl']
		except KeyError: acl = self.data['acl'] = acl_get(self)
		return acl

	def write_acl(self, acl, map_names = 1):
		"""Change access control list of rp

		If map_names is true, map the ids in acl by user/group names.

		"""
		acl.write_to_rp(self, map_names)
		self.data['acl'] = acl

	def get_ea(self):
		"""Return extended attributes object, setting if necessary"""
		try: ea = self.data['ea']
		except KeyError: ea = self.data['ea'] = ea_get(self)
		return ea

	def write_ea(self, ea):
		"""Change extended attributes of rp"""
		ea.write_to_rp(self)
		self.data['ea'] = ea

	def get_resource_fork(self):
		"""Return resource fork data, setting if necessary"""
		assert self.isreg()
		try: rfork = self.data['resourcefork']
		except KeyError:
			try:
				rfork_fp = self.conn.open(os.path.join(self.path, 'rsrc'),
										  'rb')
				rfork = rfork_fp.read()
				assert not rfork_fp.close()
			except (IOError, OSError), e: rfork = ''
			self.data['resourcefork'] = rfork
		return rfork

	def write_resource_fork(self, rfork_data):
		"""Write new resource fork to self"""
		log.Log("Writing resource fork to %s" % (self.index,), 7)
		fp = self.conn.open(os.path.join(self.path, 'rsrc'), 'wb')
		fp.write(rfork_data)
		assert not fp.close()
		self.set_resource_fork(rfork_data)


class RPathFileHook:
	"""Look like a file, but add closing hook"""
	def __init__(self, file, closing_thunk):
		self.file = file
		self.closing_thunk = closing_thunk

	def read(self, length = -1): return self.file.read(length)
	def write(self, buf): return self.file.write(buf)

	def close(self):
		"""Close file and then run closing thunk"""
		result = self.file.close()
		self.closing_thunk()
		return result


def setdata_local(rpath):
	"""Set eas/acls, uid/gid, resource fork in data dictionary

	This is a global function because it must be called locally, since
	these features may exist or not depending on the connection.

	"""
	assert rpath.conn is Globals.local_connection
	rpath.data['uname'] = user_group.uid2uname(rpath.data['uid'])
	rpath.data['gname'] = user_group.gid2gname(rpath.data['gid'])
	if Globals.eas_conn: rpath.data['ea'] = ea_get(rpath)
	if Globals.acls_conn: rpath.data['acl'] = acl_get(rpath)
	if Globals.resource_forks_conn and rpath.isreg():
		rpath.get_resource_fork()


# These two are overwritten by the eas_acls.py module.  We can't
# import that module directly because of circular dependency problems.
def acl_get(rp): assert 0
def ea_get(rp): assert 0
