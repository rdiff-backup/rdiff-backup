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

"""Store and retrieve extended attributes and access control lists

Not all file systems will have EAs and ACLs, but if they do, store
this information in separate files in the rdiff-backup-data directory,
called extended_attributes.<time>.snapshot and
access_control_lists.<time>.snapshot.

"""

from __future__ import generators
import base64, errno, re
try: import posix1e
except ImportError: pass
import static, Globals, metadata, connection, rorpiter, log, C, rpath

class ExtendedAttributes:
	"""Hold a file's extended attribute information"""
	def __init__(self, index, attr_dict = None):
		"""Initialize EA object with no attributes"""
		self.index = index
		if attr_dict is None: self.attr_dict = {}
		else: self.attr_dict = attr_dict

	def __eq__(self, ea):
		"""Equal if all attributes and index are equal"""
		assert isinstance(ea, ExtendedAttributes)
		return ea.index == self.index and ea.attr_dict == self.attr_dict
	def __ne__(self, ea): return not self.__eq__(ea)

	def get_indexpath(self): return self.index and '/'.join(self.index) or '.'

	def read_from_rp(self, rp):
		"""Set the extended attributes from an rpath"""
		try: attr_list = rp.conn.xattr.listxattr(rp.path)
		except IOError, exc:
			if exc[0] == errno.EOPNOTSUPP: return # if not sup, consider empty
			raise
		for attr in attr_list:
			if not attr.startswith('user.'):
				# Only preserve user extended attributes
				continue
			try: self.attr_dict[attr] = rp.conn.xattr.getxattr(rp.path, attr)
			except IOError, exc:
				# File probably modified while reading, just continue
				if exc[0] == errno.ENODATA: continue
				elif exc[0] == errno.ENOENT: break
				else: raise

	def clear_rp(self, rp):
		"""Delete all the extended attributes in rpath"""
		for name in rp.conn.xattr.listxattr(rp.path):
			rp.conn.xattr.removexattr(rp.path, name)

	def write_to_rp(self, rp):
		"""Write extended attributes to rpath rp"""
		self.clear_rp(rp)
		for (name, value) in self.attr_dict.iteritems():
			rp.conn.xattr.setxattr(rp.path, name, value)

	def get(self, name):
		"""Return attribute attached to given name"""
		return self.attr_dict[name]

	def set(self, name, value = ""):
		"""Set given name to given value.  Does not write to disk"""
		self.attr_dict[name] = value

	def delete(self, name):
		"""Delete value associated with given name"""
		del self.attr_dict[name]

	def empty(self):
		"""Return true if no extended attributes are set"""
		return not self.attr_dict

def ea_compare_rps(rp1, rp2):
	"""Return true if rp1 and rp2 have same extended attributes"""
	ea1 = ExtendedAttributes(rp1.index)
	ea1.read_from_rp(rp1)
	ea2 = ExtendedAttributes(rp2.index)
	ea2.read_from_rp(rp2)
	return ea1 == ea2


def EA2Record(ea):
	"""Convert ExtendedAttributes object to text record"""
	str_list = ['# file: %s' % C.acl_quote(ea.get_indexpath())]
	for (name, val) in ea.attr_dict.iteritems():
		if not val: str_list.append(name)
		else:
			encoded_val = base64.encodestring(val).replace('\n', '')
			str_list.append('%s=0s%s' % (C.acl_quote(name), encoded_val))
	return '\n'.join(str_list)+'\n'

def Record2EA(record):
	"""Convert text record to ExtendedAttributes object"""
	lines = record.split('\n')
	first = lines.pop(0)
	if not first[:8] == "# file: ":
		raise metadata.ParsingError("Bad record beginning: " + first[:8])
	filename = first[8:]
	if filename == '.': index = ()
	else: index = tuple(C.acl_unquote(filename).split('/'))
	ea = ExtendedAttributes(index)

	for line in lines:
		line = line.strip()
		if not line: continue
		assert line[0] != '#', line
		eq_pos = line.find('=')
		if eq_pos == -1: ea.set(line)
		else:
			name = line[:eq_pos]
			assert line[eq_pos+1:eq_pos+3] == '0s', \
				   "Currently only base64 encoding supported"
			encoded_val = line[eq_pos+3:]
			ea.set(name, base64.decodestring(encoded_val))
	return ea


class EAExtractor(metadata.FlatExtractor):
	"""Iterate ExtendedAttributes objects from the EA information file"""
	record_boundary_regexp = re.compile('(?:\\n|^)(# file: (.*?))\\n')
	record_to_object = staticmethod(Record2EA)
	def filename_to_index(self, filename):
		"""Convert possibly quoted filename to index tuple"""
		if filename == '.': return ()
		else: return tuple(C.acl_unquote(filename).split('/'))

class ExtendedAttributesFile(metadata.FlatFile):
	"""Store/retrieve EAs from extended_attributes file"""
	_prefix = "extended_attributes"
	_extractor = EAExtractor
	_object_to_record = staticmethod(EA2Record)

	def join(cls, rorp_iter, rbdir, time, restrict_index):
		"""Add extended attribute information to existing rorp_iter"""
		def helper(rorp_iter, ea_iter):
			"""Add EA information in ea_iter to rorp_iter"""
			collated = rorpiter.CollateIterators(rorp_iter, ea_iter)
			for rorp, ea in collated:
				assert rorp, (rorp, (ea.index, ea.attr_dict), time)
				if not ea: ea = ExtendedAttributes(rorp.index)
				rorp.set_ea(ea)
				yield rorp
			
		ea_iter = cls.get_objects_at_time(rbdir, time, restrict_index)
		if ea_iter: return helper(rorp_iter, ea_iter)
		else:
			log.Log("Warning: Extended attributes file not found",2)
			return rorp_iter

static.MakeClass(ExtendedAttributesFile)


class AccessControlList:
	"""Hold a file's access control list information

	Since ACL objects cannot be picked, store everything as text, in
	self.acl_text and self.def_acl_text.

	"""
	def __init__(self, index, acl_text = None, def_acl_text = None):
		"""Initialize object with index and possibly acl_text"""
		self.index = index
		if acl_text: # Check validity of ACL, reorder if necessary
			ACL = posix1e.ACL(text=acl_text)
			assert ACL.valid(), "Bad ACL: "+acl_text
			self.acl_text = str(ACL)
		else: self.acl_text = None

		if def_acl_text:
			def_ACL = posix1e.ACL(text=def_acl_text)
			assert def_ACL.valid(), "Bad default ACL: "+def_acl_text
			self.def_acl_text = str(def_ACL)
		else: self.def_acl_text = None

	def __str__(self):
		"""Return human-readable string"""
		return ("acl_text: %s\ndef_acl_text: %s" %
				(self.acl_text, self.def_acl_text))

	def __eq__(self, acl):
		"""Compare self and other access control list

		Basic acl permissions are considered equal to an empty acl
		object.

		"""
		assert isinstance(acl, self.__class__)
		if self.index != acl.index: return 0
		if self.is_basic(): return acl.is_basic()
		if acl.is_basic(): return self.is_basic()
		if self.acl_text != acl.acl_text: return 0
		if not self.def_acl_text and not acl.def_acl_text: return 1
		return self.def_acl_text == acl.def_acl_text
	def __ne__(self, acl): return not self.__eq__(acl)
	
	def eq_verbose(self, acl):
		"""Returns same as __eq__ but print explanation if not equal"""
		if self.index != acl.index:
			print "index %s not equal to index %s" % (self.index, acl.index)
			return 0
		if self.acl_text != acl.acl_text:
			print "ACL texts not equal:"
			print self.acl_text
			print acl.acl_text
			return 0
		if (self.def_acl_text != acl.def_acl_text and
			(self.def_acl_text or acl.def_acl_text)):
			print "Unequal default acl texts:"
			print self.def_acl_text
			print acl.def_acl_text
			return 0
		return 1

	def get_indexpath(self): return self.index and '/'.join(self.index) or '.'

	def is_basic(self):
		"""True if acl can be reduced to standard unix permissions

		Assume that if they are only three entries, they correspond to
		user, group, and other, and thus don't use any special ACL
		features.

		"""
		if not self.acl_text and not self.def_acl_text: return 1
		lines = self.acl_text.strip().split('\n')
		assert len(lines) >= 3, lines
		return len(lines) == 3 and not self.def_acl_text

	def read_from_rp(self, rp):
		"""Set self.ACL from an rpath, or None if not supported"""
		self.acl_text, self.def_acl_text = \
					   rp.conn.eas_acls.get_acl_text_from_rp(rp)

	def write_to_rp(self, rp):
		"""Write current access control list to RPath rp"""
		rp.conn.eas_acls.set_rp_acl(rp, self.acl_text, self.def_acl_text)

	def acl_to_list(self, acl):
		"""Return list representation of posix1e.ACL object

		ACL objects cannot be pickled, so this representation keeps
		the structure while adding that option.  Also we insert the
		username along with the id, because that information will be
		lost when moved to another system.

		The result will be a list of tuples.  Each tuple will have the
		form (acltype, (uid or gid, uname or gname) or None,
		permissions as an int).

		"""
		def entry_to_tuple(entry):
			if entry.tag_type == posix1e.ACL_USER:
				uid = entry.qualifier
				owner_pair = (uid, user_group.uid2uname(uid))
			elif entry.tag_type == posix1e.ACL_GROUP:
				gid = entry.qualifier
				owner_pair = (gid, user_group.gid2gname(gid))
			else: owner_pair = None

			perms = (entry.permset.read << 2 | 
					 entry.permset.write << 1 |
					 entry.permset.execute)
			return (entry.tag_type, owner_pair, perms)
		return map(entry_to_tuple, acl)

	def list_to_acl(self, listacl):
		"""Return posix1e.ACL object from list representation"""
		acl = posix1e.ACL()
		for tag, owner_pair, perms in listacl:
			entry = posix1e.Entry(acl)
			entry.tag_type = tag
			if owner_pair:
				if tag == posix1e.ACL_USER:
					entry.qualifier = user_group.UserMap.get_id(*owner_pair)
				else:
					assert tag == posix1e.ACL_GROUP
					entry.qualifier = user_group.GroupMap.get_id(*owner_pair)
			entry.read = perms >> 2
			entry.write = perms >> 1 & 1
			entry.execute = perms & 1
		return acl
		

def set_rp_acl(rp, acl_text = None, def_acl_text = None):
	"""Set given rp with ACL that acl_text defines.  rp should be local"""
	assert rp.conn is Globals.local_connection
	if acl_text:
		acl = posix1e.ACL(text=acl_text)
		assert acl.valid()
	else: acl = posix1e.ACL()
	acl.applyto(rp.path)
	if rp.isdir():
		if def_acl_text:
			def_acl = posix1e.ACL(text=def_acl_text)
			assert def_acl.valid()
		else: def_acl = posix1e.ACL()
		def_acl.applyto(rp.path, posix1e.ACL_TYPE_DEFAULT)

def get_acl_text_from_rp(rp):
	"""Returns (acl_text, def_acl_text) from an rpath.  Call locally"""
	assert rp.conn is Globals.local_connection
	try: acl_text = str(posix1e.ACL(file=rp.path))
	except IOError, exc:
		if exc[0] == errno.EOPNOTSUPP: acl_text = None
		else: raise
	if rp.isdir():
		try: def_acl_text = str(posix1e.ACL(filedef=rp.path))
		except IOError, exc:
			if exc[0] == errno.EOPNOTSUPP: def_acl_text = None
			else: raise
	else: def_acl_text = None
	return (acl_text, def_acl_text)

def acl_compare_rps(rp1, rp2):
	"""Return true if rp1 and rp2 have same acl information"""
	acl1 = AccessControlList(rp1.index)
	acl1.read_from_rp(rp1)
	acl2 = AccessControlList(rp2.index)
	acl2.read_from_rp(rp2)
	return acl1 == acl2


def ACL2Record(acl):
	"""Convert an AccessControlList object into a text record"""
	start = "# file: %s\n%s" % (C.acl_quote(acl.get_indexpath()), acl.acl_text)
	if not acl.def_acl_text: return start
	default_lines = acl.def_acl_text.strip().split('\n')
	default_text = '\ndefault:'.join(default_lines)
	return "%sdefault:%s\n" % (start, default_text)

def Record2ACL(record):
	"""Convert text record to an AccessControlList object"""
	lines = record.split('\n')
	first_line = lines.pop(0)
	if not first_line.startswith('# file: '):
		raise metadata.ParsingError("Bad record beginning: "+ first_line)
	filename = first_line[8:]
	if filename == '.': index = ()
	else: index = tuple(C.acl_unquote(filename).split('/'))

	normal_entries = []; default_entries = []
	for line in lines:
		if line.startswith('default:'): default_entries.append(line[8:])
		else: normal_entries.append(line)
	return AccessControlList(index, acl_text='\n'.join(normal_entries),
							 def_acl_text='\n'.join(default_entries))
	

class ACLExtractor(EAExtractor):
	"""Iterate AccessControlList objects from the ACL information file

	Except for the record_to_object method, we can reuse everything in
	the EAExtractor class because the file formats are so similar.

	"""
	record_to_object = staticmethod(Record2ACL)

class AccessControlListFile(metadata.FlatFile):
	"""Store/retrieve ACLs from extended attributes file"""
	_prefix = 'access_control_lists'
	_extractor = ACLExtractor
	_object_to_record = staticmethod(ACL2Record)

	def join(cls, rorp_iter, rbdir, time, restrict_index):
		"""Add access control list information to existing rorp_iter"""
		def helper(rorp_iter, acl_iter):
			"""Add ACL information in acl_iter to rorp_iter"""
			collated = rorpiter.CollateIterators(rorp_iter, acl_iter)
			for rorp, acl in collated:
				assert rorp, "Missing rorp for index %s" % (acl.index,)
				if not acl: acl = AccessControlList(rorp.index)
				rorp.set_acl(acl)
				yield rorp

		acl_iter = cls.get_objects_at_time(rbdir, time, restrict_index)
		if acl_iter: return helper(rorp_iter, acl_iter)
		else:
			log.Log("Warning: Access Control List file not found", 2)
			return rorp_iter

static.MakeClass(AccessControlListFile)


def GetCombinedMetadataIter(rbdir, time, restrict_index = None,
							acls = None, eas = None):
	"""Return iterator of rorps from metadata and related files

	None will be returned if the metadata file is absent.  If acls or
	eas is true, access control list or extended attribute information
	will be added.

	"""
	metadata_iter = metadata.MetadataFile.get_objects_at_time(
		rbdir, time, restrict_index)
	if not metadata_iter:
		log.Log("Warning, metadata file not found.\n"
				"Metadata will be read from filesystem.", 2)
		return None
	if eas:
		metadata_iter = ExtendedAttributesFile.join(
			metadata_iter, rbdir, time, restrict_index)
	if acls:
		metadata_iter = AccessControlListFile.join(
			metadata_iter, rbdir, time, restrict_index)
	return metadata_iter


def rpath_acl_get(rp):
	"""Get acls of given rpath rp.

	This overrides a function in the rpath module.

	"""
	acl = AccessControlList(rp.index)
	if not rp.issym(): acl.read_from_rp(rp)
	return acl
rpath.acl_get = rpath_acl_get

def rpath_ea_get(rp):
	"""Get extended attributes of given rpath

	This overrides a function in the rpath module.

	"""
	ea = ExtendedAttributes(rp.index)
	if not rp.issym(): ea.read_from_rp(rp)
	return ea
rpath.ea_get = rpath_ea_get
