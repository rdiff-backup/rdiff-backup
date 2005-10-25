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

"""This module deal with users and groups

On each connection we may need to map unames and gnames to uids and
gids, and possibly vice-versa.  So maintain a separate dictionary for
this.

On the destination connection only, if necessary have a separate
dictionary of mappings, which specify how to map users/groups on one
connection to the users/groups on the other.

"""

import grp, pwd
import log, Globals

# This should be set to the user UserMap class object if using
# user-defined user mapping, and a Map class object otherwise.
UserMap = None

# This should be set to the group UserMap class object if using
# user-defined group mapping, and a Map class object otherwise.
GroupMap = None


uid2uname_dict = {}; gid2gname_dict = {}
def uid2uname(uid):
	"""Given uid, return uname or None if cannot find"""
	try: return uid2uname_dict[uid]
	except KeyError:
		try: uname = pwd.getpwuid(uid)[0]
		except (KeyError, OverflowError), e: uname = None
		uid2uname_dict[uid] = uname
		return uname

def gid2gname(gid):
	"""Given gid, return group name or None if cannot find"""
	try: return gid2gname_dict[gid]
	except KeyError:
		try: gname = grp.getgrgid(gid)[0]
		except (KeyError, OverflowError), e: gname = None
		gid2gname_dict[gid] = gname
		return gname

def uname2uid(uname):
	"""Given uname, return uid or None if cannot find"""
	try: uname = pwd.getpwnam(uname)[2]
	except KeyError: return None

def gname2gid(gname):
	"""Given gname, return gid or None if cannot find"""
	try: gname = grp.getgrnam(gname)[2]
	except KeyError: return None


class Map:
	"""Used for mapping names and id on source side to dest side"""
	def __init__(self, name2id_func):
		"""Map initializer, set dictionaries"""
		self.name2id_dict = {}
		self.name2id_func = name2id_func

	def get_id(self, id, name = None):
		"""Return mapped id from id and, if available, name"""
		if not name: return self.get_id_from_id(id)
		try: return self.name2id_dict[name]
		except KeyError:
			out_id = self.find_id(id, name)
			self.name2id_dict[name] = out_id
			return out_id

	def get_id_from_name(self, name):
		"""Return mapped id from name only, or None if cannot"""
		try: return self.name2id_dict[name]
		except KeyError:
			out_id = self.find_id_from_name(name)
			self.name2id_dict[name] = out_id
			return out_id

	def get_id_from_id(self, id): return id

	def find_id(self, id, name):
		"""Find the proper id to use with given id and name"""
		try: return self.name2id_func(name)
		except KeyError: return id

	def find_id_from_name(self, name):
		"""Look up proper id to use with name, or None"""
		try: return self.name2id_func(name)
		except KeyError: return None
			
class DefinedMap(Map):
	"""Map names and ids on source side to appropriate ids on dest side

	Like map, but initialize with user-defined mapping string, which
	supersedes Map.

	"""
	def __init__(self, name2id_func, mapping_string):
		"""Initialize object with given mapping string

		The mapping_string should consist of a number of lines, each which
		should have the form "source_id_or_name:dest_id_or_name".  Do user
		mapping unless user is false, then do group.

		"""
		Map.__init__(self, name2id_func)
		self.name_mapping_dict = {}; self.id_mapping_dict = {}

		for line in mapping_string.split('\n'):
			line = line.strip()
			if not line: continue
			comps = line.split(':')
			if not len(comps) == 2:
				log.Log.FatalError("Error parsing mapping file, bad line: "
								   + line)
			old, new = comps

			try: self.id_mapping_dict[int(old)] = self.init_get_new_id(new)
			except ValueError:
				self.name_mapping_dict[old] = self.init_get_new_id(new)

	def init_get_new_id(self, id_or_name):
		"""Return id of id_or_name, failing if cannot.  Used in __init__"""
		try: return int(id_or_name)
		except ValueError:
			try: id = self.name2id_func(id_or_name)
			except KeyError:
				log.Log.FatalError("Cannot get id for user or group name "
								   + id_or_name)
			return id

	def get_id_from_id(self, id): return self.id_mapping_dict.get(id, id)

	def find_id(self, id, name):
		"""Find proper id to use when source file has give id and name"""
		try: return self.name_mapping_dict[name]
		except KeyError:
			try: return self.id_mapping_dict[id]
			except KeyError: return Map.find_id(self, id, name)

	def find_id_from_name(self, name):
		"""Find id to map name to, or None if we can't"""
		try: return self.name_mapping_dict[name]
		except KeyError: return Map.find_id_from_name(name)

def init_user_mapping(mapping_string = None):
	"""Initialize user mapping with given mapping string or None"""
	global UserMap
	name2id_func = lambda name: pwd.getpwnam(name)[2]
	if mapping_string: UserMap = DefinedMap(name2id_func, mapping_string)
	else: UserMap = Map(name2id_func)

def init_group_mapping(mapping_string = None):
	"""Initialize the group mapping dictionary with given mapping string"""
	global GroupMap
	name2id_func = lambda name: grp.getgrnam(name)[2]
	if mapping_string: GroupMap = DefinedMap(name2id_func, mapping_string)
	else: GroupMap = Map(name2id_func)

	
def map_rpath(rp):
	"""Return (uid, gid) of mapped ownership of given rpath"""
	old_uid, old_gid = rp.getuidgid()
	new_uid = UserMap.get_id(old_uid, rp.getuname())
	new_gid = GroupMap.get_id(old_gid, rp.getgname())
	return (new_uid, new_gid)
