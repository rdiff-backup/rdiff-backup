execfile("rpath.py")

#######################################################################
#
# hardlink - code for preserving and restoring hardlinks
#
# If the preserve_hardlinks option is selected, linked files in the
# source directory will be linked in the mirror directory.  Linked
# files are treated like any other with respect to incrementing, but a
# database of all links will be recorded at each session, so linked
# files can still be restored from the increments.
#

class Hardlink:
	"""Hardlink class methods and data

	All these functions are meant to be executed on the destination
	side.  The source side should only transmit inode information.

	"""
	# In all of these lists of indicies are the values.  The keys in
	# _inode_ ones are (inode, devloc) pairs.
	_src_inode_indicies = {}
	_dest_inode_indicies = {}

	# The keys for these two are just indicies.  They share values
	# with the earlier dictionaries.
	_src_index_indicies = {}
	_dest_index_indicies = {}

	def get_inode_key(cls, rorp):
		"""Return rorp's key for _inode_ dictionaries"""
		return (rorp.getinode(), rorp.getdevloc())

	def get_indicies(cls, rorp, source):
		"""Return a list of similarly linked indicies, using rorp's index"""
		if source: dict = cls._src_index_indicies
		else: dict = cls._dest_index_indicies
		try: return dict[rorp.index]
		except KeyError: return []

	def add_rorp(cls, rorp, source):
		"""Process new rorp and update hard link dictionaries

		First enter it into src_inode_indicies.  If we have already
		seen all the hard links, then we can delete the entry.
		Everything must stay recorded in src_index_indicies though.

		"""
		if not rorp.isreg() or rorp.getnumlinks() < 2: return

		if source: inode_dict, index_dict = (cls._src_inode_indicies,
											 cls._src_index_indicies)
		else: inode_dict, index_dict = (cls._dest_inode_indicies,
										cls._dest_index_indicies)

		rp_inode_key = cls.get_inode_key(rorp)
		if inode_dict.has_key(rp_inode_key):
			index_list = inode_dict[rp_inode_key]
			index_list.append(rorp.index)
			if len(index_list) == rorp.getnumlinks():
				del inode_dict[rp_inode_key]
		else: # make new entry in both src dicts
			index_list = [rorp.index]
			inode_dict[rp_inode_key] = index_list
		index_dict[rorp.index] = index_list

	def add_rorp_iter(cls, iter, source):
		"""Return new rorp iterator like iter that cls.add_rorp's first"""
		for rorp in iter:
			cls.add_rorp(rorp, source)
			yield rorp

	def rorp_eq(cls, src_rorp, dest_rorp):
		"""Compare hardlinked for equality

		Two files may otherwise seem equal but be hardlinked in
		different ways.  This function considers them equal enough if
		they have been hardlinked correctly to the previously seen
		indicies.

		"""
		assert src_rorp.index == dest_rorp.index
		if (not src_rorp.isreg() or not dest_rorp.isreg() or
			src_rorp.getnumlinks() == dest_rorp.getnumlinks() == 1):
			return 1 # Hard links don't apply

		src_index_list = cls.get_indicies(src_rorp, 1)
		dest_index_list = cls.get_indicies(dest_rorp, None)

		# If a list only has one element, then it is only hardlinked
		# to itself so far, so that is not a genuine difference yet.
		if not src_index_list or len(src_index_list) == 1:
			return not dest_index_list or len(dest_index_list) == 1
		if not dest_index_list or len(dest_index_list) == 1: return None

		# Both index lists exist and are non-empty
		return src_index_list == dest_index_list # they are always sorted

	def islinked(cls, rorp):
		"""True if rorp's index is already linked to something on src side"""
		return len(cls.get_indicies(rorp, 1)) >= 2

	def restore_link(cls, mirror_rel_index, rpath):
		"""Restores a linked file by linking it

		When restoring, all the hardlink data is already present, and
		we can only link to something already written.  Returns true
		if succeeded in creating rpath, false if must restore rpath
		normally.

		"""
		full_index = mirror_rel_index + rpath.index
		if not cls._src_index_indicies.has_key(full_index): return None
		truncated_list = []
		for index in cls._src_index_indicies[full_index]:
			if index[:len(mirror_rel_index)] == mirror_rel_index:
				truncated_list.append(index[len(mirror_rel_index):])

		if not truncated_list or truncated_list[0] >= rpath.index: return None
		srclink = RPath(rpath.conn, rpath.base, truncated_list[0])
		rpath.hardlink(srclink.path)
		return 1

	def link_rp(cls, src_rorp, dest_rpath, dest_root = None):
		"""Make dest_rpath into a link analogous to that of src_rorp"""
		if not dest_root: dest_root = dest_rpath # use base of dest_rpath
		dest_link_rpath = RPath(dest_root.conn, dest_root.base,
								cls.get_indicies(src_rorp, 1)[0])
		dest_rpath.hardlink(dest_link_rpath.path)

	def write_linkdict(cls, rpath, dict, compress = None):
		"""Write link data to the rbdata dir

		It is stored as the a big pickled dictionary dated to match
		the current hardlinks.

		"""
		assert (Globals.isbackup_writer and
				rpath.conn is Globals.local_connection)
		tf = TempFileManager.new(rpath)
		def init():
			fp = tf.open("wb", compress)
			cPickle.dump(dict, fp)
			assert not fp.close()
		Robust.make_tf_robustaction(init, (tf,), (rpath,)).execute()

	def get_linkrp(cls, data_rpath, time, prefix):
		"""Return RPath of linkdata, or None if cannot find"""
		for rp in map(data_rpath.append, data_rpath.listdir()):
			if (rp.isincfile() and rp.getincbase_str() == prefix and
				rp.getinctype() == 'snapshot' and
				Time.stringtotime(rp.getinctime()) == time):
				return rp
		return None

	def get_linkdata(cls, data_rpath, time, prefix = 'hardlink_data'):
		"""Return index dictionary written by write_linkdata at time"""
		rp = cls.get_linkrp(data_rpath, time, prefix)
		if not rp: return None
		fp = rp.open("rb", rp.isinccompressed())
		index_dict = cPickle.load(fp)
		assert not fp.close()
		return index_dict

	def final_writedata(cls):
		"""Write final checkpoint data to rbdir after successful backup"""
		if not cls._src_index_indicies: return
		Log("Writing hard link data", 6)
		if Globals.compression:
			rp = Globals.rbdir.append("hardlink_data.%s.snapshot.gz" %
									  Time.curtimestr)
		else: rp = Globals.rbdir.append("hardlink_data.%s.snapshot" %
										Time.curtimestr)
		cls.write_linkdict(rp, cls._src_index_indicies, Globals.compression)

	def retrieve_final(cls, time):
		"""Set source index dictionary from hardlink_data file if avail"""
		hd = cls.get_linkdata(Globals.rbdir, time)
		if hd is None: return None
		cls._src_index_indicies = hd
		return 1

	def final_checkpoint(cls, data_rpath):
		"""Write contents of the four dictionaries to the data dir

		If rdiff-backup receives a fatal error, it may still be able
		to save the contents of the four hard link dictionaries.
		Because these dictionaries may be big, they are not saved
		after every 20 seconds or whatever, but just at the end.

		"""
		Log("Writing intermediate hard link data to disk", 2)
		src_inode_rp = data_rpath.append("hardlink_source_inode_checkpoint."
										 "%s.snapshot" % Time.curtimestr)
		src_index_rp = data_rpath.append("hardlink_source_index_checkpoint."
										 "%s.snapshot" % Time.curtimestr)
		dest_inode_rp = data_rpath.append("hardlink_dest_inode_checkpoint."
										  "%s.snapshot" % Time.curtimestr)
		dest_index_rp = data_rpath.append("hardlink_dest_index_checkpoint."
										  "%s.snapshot" % Time.curtimestr)
		for (rp, dict) in ((src_inode_rp, cls._src_inode_indicies),
						   (src_index_rp, cls._src_index_indicies),
						   (dest_inode_rp, cls._dest_inode_indicies),
						   (dest_index_rp, cls._dest_index_indicies)):
			cls.write_linkdict(rp, dict)

	def retrieve_checkpoint(cls, data_rpath, time):
		"""Retrieve hardlink data from final checkpoint

		Return true if the retrieval worked, false otherwise.

		"""
		try:
			src_inode = cls.get_linkdata(data_rpath, time,
										 "hardlink_source_inode_checkpoint")
			src_index = cls.get_linkdata(data_rpath, time,
										 "hardlink_source_index_checkpoint")
			dest_inode = cls.get_linkdata(data_rpath, time,
										  "hardlink_dest_inode_checkpoint")
			dest_index = cls.get_linkdata(data_rpath, time,
										  "hardlink_dest_index_checkpoint")
		except cPickle.UnpicklingError:
			Log("Unpickling Error", 2)
			return None
		if (src_inode is None or src_index is None or
			dest_inode is None or dest_index is None): return None
		cls._src_inode_indicies = src_inode
		cls._src_index_indicies = src_index
		cls._dest_inode_indicies = dest_inode
		cls._dest_index_indicies = dest_index
		return 1

	def remove_all_checkpoints(cls):
		"""Remove all hardlink checkpoint information from directory"""
		prefix_list = ["hardlink_source_inode_checkpoint",
					   "hardlink_source_index_checkpoint",
					   "hardlink_dest_inode_checkpoint",
					   "hardlink_dest_index_checkpoint"]
		for rp in map(Globals.rbdir.append, Globals.rbdir.listdir()):
			if (rp.isincfile() and rp.getincbase_str() in prefix_list and
				rp.getinctype() == 'snapshot'):
				rp.delete()

MakeClass(Hardlink)
