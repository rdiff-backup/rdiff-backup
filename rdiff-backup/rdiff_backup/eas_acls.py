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
import static, Globals, metadata, connection, rorpiter, log


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
	str_list = ['# file: %s' % ea.get_indexpath()]
	for (name, val) in ea.attr_dict.iteritems():
		if not val: str_list.append(name)
		else:
			encoded_val = base64.encodestring(val).replace('\n', '')
			str_list.append('%s=0s%s' % (name, encoded_val))
	return '\n'.join(str_list)+'\n'

def Record2EA(record):
	"""Convert text record to ExtendedAttributes object"""
	lines = record.split('\n')
	first = lines.pop(0)
	if not first[:8] == "# file: ":
		raise metadata.ParsingError("Bad record beginning: " + first[:8])
	filename = first[8:]
	if filename == '.': index = ()
	else: index = tuple(filename.split('/'))
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

def quote_path(path):
	"""Quote a path for use EA/ACL records.

	Right now no quoting!!!  Change this to reflect the updated
	quoting style of getfattr/setfattr when they are changed.

	"""
	return path


class EAExtractor(metadata.FlatExtractor):
	"""Iterate ExtendedAttributes objects from the EA information file"""
	record_boundary_regexp = re.compile("\\n# file:")
	record_to_object = staticmethod(Record2EA)
	def get_index_re(self, index):
		"""Find start of EA record with given index"""
		if not index: indexpath = '.'
		else: indexpath = '/'.join(index)
		# Right now there is no quoting, due to a bug in
		# getfacl/setfacl.  Replace later when bug fixed.
		return re.compile('(^|\\n)(# file: %s\\n)' % indexpath)

class ExtendedAttributesFile(metadata.FlatFile):
	"""Store/retrieve EAs from extended_attributes file"""
	_prefix = "extended_attributes"
	_extractor = EAExtractor
	_object_to_record = staticmethod(EA2Record)

	def get_combined_iter_at_time(cls, rbdir, rest_time,
								  restrict_index = None):
		"""Return an iter of rorps with extended attributes added"""
		def join_eas(basic_iter, ea_iter):
			"""Join basic_iter with ea iter"""
			collated = rorpiter.CollateIterators(basic_iter, ea_iter)
			for rorp, ea in collated:
				assert rorp, (rorp, (ea.index, ea.attr_dict), rest_time)
				if not ea: ea = ExtendedAttributes(rorp.index)
				rorp.set_ea(ea)
				yield rorp

		basic_iter = metadata.MetadataFile.get_objects_at_time(
			Globals.rbdir, rest_time, restrict_index)
		if not basic_iter: return None
		ea_iter = cls.get_objects_at_time(rbdir, rest_time, restrict_index)
		if not ea_iter:
			log.Log("Warning: Extended attributes file not found", 2)
			ea_iter = iter([])
		return join_eas(basic_iter, ea_iter)

static.MakeClass(ExtendedAttributesFile)


class AccessControlList:
	"""Hold a file's access control list information"""
	def __init__(self, index, text_acl = None):
		"""Initialize object with index and possibly text_acl"""
		self.index = index
		# self.ACL is a posix1e ACL object
		if text_acl is None: self.ACL = None
		else: self.ACL = posix1e.ACL(text_acl)

	def __eq__(self, acl):
		"""Compare self and other access control list"""
		return self.index == acl.index and str(self.ACL) == str(acl.ACL)
	def __ne__(self, acl): return not self.__eq__(acl)
	
	def get_indexpath(self): return self.index and '/'.join(self.index) or '.'


def get_acl_from_rp(rp):
	"""Return text acl from an rpath, or None if not supported"""
	try: acl = rp.conn.posix1e.ACL(file=rp.path)
	except IOError, exc:
		if exc[0] == errno.EOPNOTSUPP: return None
		raise
	return str(acl)

def acl_compare_rps(rp1, rp2):
	"""Return true if rp1 and rp2 have same acls"""
	return get_acl_from_rp(rp1) == get_acl_from_rp(rp2)


def ACL2Record(acl):
	"""Convert an AccessControlList object into a text record"""
	return "# file: %s\n%s" % (acl.get_indexpath(), str(acl.ACL))

def Record2EA(acl):
	"""Convert text record to an AccessControlList object"""
	XXXX




