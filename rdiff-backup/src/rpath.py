execfile("connection.py")
import os, stat, re, sys, shutil, gzip

#######################################################################
#
# rpath - Wrapper class around a real path like "/usr/bin/env"
#
# The RPath and associated classes make some function calls more
# convenient (e.g. RPath.getperms()) and also make working with files
# on remote systems transparent.
#

class RPathException(Exception): pass

class RPathStatic:
	"""Contains static methods for use with RPaths"""
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
				raise RPathException("File %s does not exist" % rp.path)

	def move(rpin, rpout):
		"""Move rpin to rpout, renaming if possible"""
		try: RPath.rename(rpin, rpout)
		except os.error:
			RPath.copy(rpin, rpout)
			rpin.delete()

	def copy(rpin, rpout):
		"""Copy RPath rpin to rpout.  Works for symlinks, dirs, etc."""
		Log("Regular copying %s to %s" % (rpin.index, rpout.path), 6)
		if not rpin.lstat():
			raise RPathException, ("File %s does not exist" % rpin.index)

		if rpout.lstat():
			if rpin.isreg() or not RPath.cmp(rpin, rpout):
				rpout.delete()   # easier to write that compare
			else: return
			
		if rpin.isreg(): RPath.copy_reg_file(rpin, rpout)
		elif rpin.isdir(): rpout.mkdir()
		elif rpin.issym(): rpout.symlink(rpin.readlink())
		elif rpin.ischardev():
			major, minor = rpin.getdevnums()
			rpout.makedev("c", major, minor)
		elif rpin.isblkdev():
			major, minor = rpin.getdevnums()
			rpout.makedev("b", major, minor)
		elif rpin.isfifo(): rpout.mkfifo()
		elif rpin.issock(): Log("Found socket, ignoring", 1)
		else: raise RPathException("File %s has unknown type" % rpin.path)

	def copy_reg_file(rpin, rpout):
		"""Copy regular file rpin to rpout, possibly avoiding connection"""
		try:
			if rpout.conn is rpin.conn:
				rpout.conn.shutil.copyfile(rpin.path, rpout.path)
				rpout.setdata()
				return
		except AttributeError: pass
		rpout.write_from_fileobj(rpin.open("rb"))

	def cmp(rpin, rpout):
		"""True if rpin has the same data as rpout

		cmp does not compare file ownership, permissions, or times, or
		examine the contents of a directory.

		"""
		RPath.check_for_files(rpin, rpout)
		if rpin.isreg():
			if not rpout.isreg(): return None
			fp1, fp2 = rpin.open("rb"), rpout.open("rb")
			result = RPathStatic.cmpfileobj(fp1, fp2)
			if fp1.close() or fp2.close():
				raise RPathException("Error closing file")
			return result
		elif rpin.isdir(): return rpout.isdir()
		elif rpin.issym():
			return rpout.issym() and (rpin.readlink() == rpout.readlink())
		elif rpin.ischardev():
			return rpout.ischardev() and \
				   (rpin.getdevnums() == rpout.getdevnums())
		elif rpin.isblkdev():
			return rpout.isblkdev() and \
				   (rpin.getdevnums() == rpout.getdevnums())
		elif rpin.isfifo(): return rpout.isfifo()
		elif rpin.issock(): return rpout.issock()
		else: raise RPathException("File %s has unknown type" % rpin.path)

	def copy_attribs(rpin, rpout):
		"""Change file attributes of rpout to match rpin

		Only changes the chmoddable bits, uid/gid ownership, and
		timestamps, so both must already exist.

		"""
		Log("Copying attributes from %s to %s" % (rpin.index, rpout.path), 7)
		RPath.check_for_files(rpin, rpout)
		if rpin.issym(): return # symlinks have no valid attributes
		if Globals.change_ownership: apply(rpout.chown, rpin.getuidgid())
		rpout.chmod(rpin.getperms())
		if not rpin.isdev(): rpout.setmtime(rpin.getmtime())

	def cmp_attribs(rp1, rp2):
		"""True if rp1 has the same file attributes as rp2

		Does not compare file access times.  If not changing
		ownership, do not check user/group id.

		"""
		RPath.check_for_files(rp1, rp2)
		if Globals.change_ownership and rp1.getuidgid() != rp2.getuidgid():
			result = None
		elif rp1.getperms() != rp2.getperms(): result = None
		elif rp1.issym() and rp2.issym(): # Don't check times for some types
			result = 1
		elif rp1.isblkdev() and rp2.isblkdev(): result = 1
		elif rp1.ischardev() and rp2.ischardev(): result = 1
		else: result = (rp1.getmtime() == rp2.getmtime())
		Log("Compare attribs %s and %s: %s" % (rp1.path, rp2.path, result), 7)
		return result

	def copy_with_attribs(rpin, rpout):
		"""Copy file and then copy over attributes"""
		RPath.copy(rpin, rpout)
		RPath.copy_attribs(rpin, rpout)

	def quick_cmp_with_attribs(rp1, rp2):
		"""Quicker version of cmp_with_attribs

		Instead of reading all of each file, assume that regular files
		are the same if the attributes compare.

		"""
		if not RPath.cmp_attribs(rp1, rp2): return None
		if rp1.isreg() and rp2.isreg() and (rp1.getlen() == rp2.getlen()):
			return 1
		return RPath.cmp(rp1, rp2)

	def cmp_with_attribs(rp1, rp2):
		"""Combine cmp and cmp_attribs"""
		return RPath.cmp_attribs(rp1, rp2) and RPath.cmp(rp1, rp2)

	def rename(rp_source, rp_dest):
		"""Rename rp_source to rp_dest"""
		assert rp_source.conn is rp_dest.conn
		Log("Renaming %s to %s" % (rp_source.path, rp_dest.path), 7)
		rp_source.conn.os.rename(rp_source.path, rp_dest.path)
		rp_dest.data = rp_source.data
		rp_source.data = {'type': None}

		# If we are moving to a DSRPath, assume that the current times
		# are the intended ones.  We need to save them now in case
		# they are changed later.
		if isinstance(rp_dest, DSRPath):
			if rp_dest.delay_mtime:
				if 'mtime' in rp_dest.data:
					rp_dest.setmtime(rp_dest.data['mtime'])
			if rp_dest.delay_atime:
				if 'atime' in rp_dest.data:
					rp_dest.setatime(rp_dest.data['atime'])

	def tupled_lstat(filename):
		"""Like os.lstat, but return only a tuple, or None if os.error

		Later versions of os.lstat return a special lstat object,
		which can confuse the pickler and cause errors in remote
		operations.  This has been fixed in Python 2.2.1.

		"""
		try: return tuple(os.lstat(filename))
		except os.error: return None

MakeStatic(RPathStatic)


class RORPath(RPathStatic):
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

	def __eq__(self, other):
		"""True iff the two rorpaths are equivalent"""
		if self.index != other.index: return None

		for key in self.data.keys(): # compare dicts key by key
			if ((key == 'uid' or key == 'gid') and
				(not Globals.change_ownership or self.issym())):
				# Don't compare gid/uid for symlinks or if not change_ownership
				pass
			elif key == 'devloc' or key == 'inode' or key == 'nlink': pass
			elif (not other.data.has_key(key) or
				  self.data[key] != other.data[key]): return None
		return 1

	def __ne__(self, other): return not self.__eq__(other)

	def __str__(self):
		"""Pretty print file statistics"""
		return "Index: %s\nData: %s" % (self.index, self.data)

	def __getstate__(self):
		"""Return picklable state

		This is necessary in case the RORPath is carrying around a
		file object, which can't/shouldn't be pickled.

		"""
		return (self.index, self.data)

	def __setstate__(self, rorp_state):
		"""Reproduce RORPath from __getstate__ output"""
		self.index, self.data = rorp_state

	def make_placeholder(self):
		"""Make rorp into a placeholder

		This object doesn't contain any information about the file,
		but, when passed along, may show where the previous stages are
		in their processing.  It is the RORPath equivalent of fiber.

		"""
		self.data = {'placeholder':
					 ("It is actually good for placeholders to use"
					  "up a bit of memory, so the buffers get flushed"
					  "more often when placeholders move through."
					  "See the get_dissimilar docs for more info.")}

	def isplaceholder(self):
		"""True if the object is a placeholder"""
		return self.data.has_key('placeholder')

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

	def getperms(self):
		"""Return permission block of file"""
		return self.data['perms']

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
	
	def getinode(self):
		"""Return inode number of file"""
		return self.data['inode']

	def getdevloc(self):
		"""Device number file resides on"""
		return self.data['devloc']

	def getnumlinks(self):
		"""Number of places inode is linked to"""
		return self.data['nlink']

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

	def flaglinked(self):
		"""Signal that rorp is a signature/diff for a hardlink file"""
		self.data['linked'] = 1

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
		self.path = apply(os.path.join, (base,) + self.index)
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
		self.index, self.base, self.data = rpath_state

	def setdata(self):
		"""Create the data dictionary"""
		statblock = self.conn.RPathStatic.tupled_lstat(self.path)
		if statblock is None:
			self.data = {'type':None}
			return
		data = {}
		mode = statblock[stat.ST_MODE]

		if stat.S_ISREG(mode):
			type = 'reg'
			data['size'] = statblock[stat.ST_SIZE]
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
		else: raise RPathException("Unknown type for %s" % self.path)
		data['type'] = type
		data['perms'] = stat.S_IMODE(mode)
		data['uid'] = statblock[stat.ST_UID]
		data['gid'] = statblock[stat.ST_GID]
		data['inode'] = statblock[stat.ST_INO]
		data['devloc'] = statblock[stat.ST_DEV]
		data['nlink'] = statblock[stat.ST_NLINK]

		if not (type == 'sym' or type == 'dev'):
			# mtimes on symlinks and dev files don't work consistently
			data['mtime'] = long(statblock[stat.ST_MTIME])

		if Globals.preserve_atime and not type == 'sym':
			data['atime'] = long(statblock[stat.ST_ATIME])
		self.data = data

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

	def quote_path(self):
		"""Set path from quoted version of index"""
		quoted_list = [FilenameMapping.quote(path) for path in self.index]
		self.path = apply(os.path.join, [self.base] + quoted_list)
		self.setdata()

	def chmod(self, permissions):
		"""Wrapper around os.chmod"""
		self.conn.os.chmod(self.path, permissions)
		self.data['perms'] = permissions

	def settime(self, accesstime, modtime):
		"""Change file modification times"""
		Log("Setting time of %s to %d" % (self.path, modtime), 7)
		self.conn.os.utime(self.path, (accesstime, modtime))
		self.data['atime'] = accesstime
		self.data['mtime'] = modtime

	def setmtime(self, modtime):
		"""Set only modtime (access time to present)"""
		Log("Setting time of %s to %d" % (self.path, modtime), 7)
		self.conn.os.utime(self.path, (time.time(), modtime))
		self.data['mtime'] = modtime

	def chown(self, uid, gid):
		"""Set file's uid and gid"""
		self.conn.os.chown(self.path, uid, gid)
		self.data['uid'] = uid
		self.data['gid'] = gid

	def mkdir(self):
		Log("Making directory " + self.path, 6)
		self.conn.os.mkdir(self.path)
		self.setdata()

	def rmdir(self):
		Log("Removing directory " + self.path, 6)
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
		self.conn.os.link(linkpath, self.path)
		self.setdata()

	def mkfifo(self):
		"""Make a fifo at self.path"""
		self.conn.os.mkfifo(self.path)
		self.setdata()
		assert self.isfifo()

	def touch(self):
		"""Make sure file at self.path exists"""
		Log("Touching " + self.path, 7)
		self.conn.open(self.path, "w").close()
		self.setdata()
		assert self.isreg()

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
		uid = self.conn.Globals.get('process_uid')
		return uid == 0 or uid == self.data['uid']

	def isgroup(self):
		"""Return true if current process is in group of rp"""
		return self.conn.Globals.get('process_gid') == self.data['gid']

	def delete(self):
		"""Delete file at self.path

		The destructive stepping allows this function to delete
		directories even if they have files and we lack permissions.

		"""
		Log("Deleting %s" % self.path, 7)
		self.setdata()
		if not self.lstat(): return # must have been deleted in meantime
		elif self.isdir():
			itm = RpathDeleter()
			for dsrp in Select(DSRPath(None, self)).set_iter():
				itm(dsrp.index, dsrp)
			itm.Finish()
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

	def newpath(self, newpath, index = ()):
		"""Return new RPath with the same connection but different path"""
		return self.__class__(self.conn, newpath, index)

	def append(self, ext):
		"""Return new RPath with same connection by adjoing ext"""
		return self.__class__(self.conn, self.base, self.index + (ext,))

	def append_path(self, ext, new_index = ()):
		"""Like append, but add ext to path instead of to index"""
		assert not self.index # doesn't make sense if index isn't ()
		return self.__class__(self.conn, os.path.join(self.base, ext),
							  new_index)

	def new_index(self, index):
		"""Return similar RPath but with new index"""
		return self.__class__(self.conn, self.base, index)

	def open(self, mode, compress = None):
		"""Return open file.  Supports modes "w" and "r".

		If compress is true, data written/read will be gzip
		compressed/decompressed on the fly.

		"""
		if compress: return self.conn.gzip.GzipFile(self.path, mode)
		else: return self.conn.open(self.path, mode)

	def write_from_fileobj(self, fp, compress = None):
		"""Reads fp and writes to self.path.  Closes both when done

		If compress is true, fp will be gzip compressed before being
		written to self.

		"""
		Log("Writing file object to " + self.path, 7)
		assert not self.lstat(), "File %s already exists" % self.path
		outfp = self.open("wb", compress = compress)
		RPath.copyfileobj(fp, outfp)
		if fp.close() or outfp.close():
			raise RPathException("Error closing file")
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
		"""Return timestring of an increment file"""
		return self.inc_timestr
	
	def getincbase(self):
		"""Return the base filename of an increment file in rp form"""
		if self.index:
			return self.__class__(self.conn, self.base, self.index[:-1] +
								  (self.inc_basestr,))
		else: return self.__class__(self.conn, self.inc_basestr)

	def getincbase_str(self):
		"""Return the base filename string of an increment file"""
		return self.getincbase().dirsplit()[1]

	def makedev(self, type, major, minor):
		"""Make a special file with specified type, and major/minor nums"""
		cmdlist = ['mknod', self.path, type, str(major), str(minor)]
		if self.conn.os.spawnvp(os.P_WAIT, 'mknod', cmdlist) != 0:
			RPathException("Error running %s" % cmdlist)
		if type == 'c': datatype = 'chr'
		elif type == 'b': datatype = 'blk'
		else: raise RPathException
		self.data = {'type': datatype, 'devnums': (type, major, minor)}

	def getRORPath(self, include_contents = None):
		"""Return read only version of self"""
		rorp = RORPath(self.index, self.data)
		if include_contents: rorp.setfile(self.open("rb"))
		return rorp


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


class RpathDeleter(IterTreeReducer):
	"""Delete a directory.  Called by RPath.delete()"""
	def start_process(self, index, dsrp):
		self.dsrp = dsrp

	def end_process(self):
		if self.dsrp.isdir(): self.dsrp.rmdir()
		else: self.dsrp.delete()

		
