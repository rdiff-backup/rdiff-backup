execfile("destructive_stepping.py")

#######################################################################
#
# selection - Provides the iterator-like DSRPIterator class
#
# Parses includes and excludes to yield correct files.  More
# documentation on what this code does can be found on the man page.
#

class FilePrefixError(Exception):
	"""Signals that a specified file doesn't start with correct prefix"""
	pass


class Select:
	"""Iterate appropriate DSRPaths in given directory

	This class acts as an iterator on account of its next() method.
	Basically, it just goes through all the files in a directory in
	order (depth-first) and subjects each file to a bunch of tests
	(selection functions) in order.  The first test that includes or
	excludes the file means that the file gets included (iterated) or
	excluded.  The default is include, so with no tests we would just
	iterate all the files in the directory in order.

	The one complication to this is that sometimes we don't know
	whether or not to include a directory until we examine its
	contents.  For instance, if we want to include all the **.py
	files.  If /home/ben/foo.py exists, we should also include /home
	and /home/ben, but if these directories contain no **.py files,
	they shouldn't be included.  For this reason, a test may not
	include or exclude a directory, but merely "scan" it.  If later a
	file in the directory gets included, so does the directory.

	As mentioned above, each test takes the form of a selection
	function.  The selection function takes a dsrp, and returns:

	None - means the test has nothing to say about the related file
	0 - the file is excluded by the test
	1 - the file is included
	2 - the test says the file (must be directory) should be scanned

	Also, a selection function f has a variable f.exclude which should
	be true iff f could potentially exclude some file.  This is used
	to signal an error if the last function only includes, which would
	be redundant and presumably isn't what the user intends.

	"""
	def __init__(self, dsrpath, starting_index = None):
		"""DSRPIterator initializer.  dsrpath should be the root dir"""
		self.selection_functions = []
		if starting_index:
			self.iter = self.iterate_starting_from(dsrpath, starting_index,
												   self.iterate_starting_from)
		else: self.iter = self.Iterate(dsrpath, self.Iterate)
		self.next = self.iter.next

	def Iterate(self, dsrpath, rec_func):
		"""Return iterator yielding dsrps in dsrpath

		rec_func is usually the same as this function and is what
		Iterate uses to find files in subdirectories.  It is used in
		iterate_starting_from.

		"""
		s = self.Select(dsrpath)
		if s == 1: # File is included
			yield dsrpath
			if dsrpath.isdir():
				for dsrp in self.iterate_in_dir(dsrpath, rec_func): yield dsrp
		elif s == 2 and dsrpath.isdir(): # Directory is merely scanned
			iid = self.iterate_in_dir(dsrpath, rec_func)
			try: first = iid.next()
			except StopIteration: return # no files inside; skip dsrp
			yield dsrpath
			yield first
			for dsrp in iid: yield dsrp

	def iterate_in_dir(self, dsrpath, rec_func):
		"""Iterate the dsrps in directory dsrpath."""
		dir_listing = dsrpath.listdir()
		dir_listing.sort()
		for filename in dir_listing:
			for dsrp in rec_func(dsrpath.append(filename)): yield dsrp

	def iterate_starting_from(self, dsrpath):
		"""Like Iterate, but only yield indicies > self.starting_index"""
		if dsrpath.index > self.starting_index: # past starting_index
			for dsrp in self.Iterate(dsrpath, self.iterate): yield dsrp
		elif dsrpath.index = self.starting_index[:len(dsrpath.index)]:
			# May encounter starting index on this branch
			for dsrp in self.Iterate(dsrpath, self.iterate_starting_from):
				yield dsrp
			
	def Select(self, dsrp):
		"""Run through the selection functions and return dominant value"""
		for sf in self.selection_functions:
			result = sf(dsrp)
			if result is not None: return result
		return 1

	def add_selection_func(self, sel_func):
		"""Add another selection function at the end"""
		self.selection_functions.append(sel_func)

	def filelist_add_sf(self, filelist_fp, include, filelist_name):
		"""Adds selection function by reading list of files

		The format of the filelist is documented in the man page.
		filelist_fp should be an (open) file object.
		include should be true if this is an include list, false for
		an exclude list.
		filelist_name is just a string used for logging.

		"""
		Log("Reading filelist %s" % filelist_name, 4)
		tuple_list, something_excluded = \
					self.filelist_read(filelist_fp, include, filelist_name)
		Log("Sorting filelist %s" % filelist_name, 4)
		tuple_list.sort()
		current_index = 0
		def selection_function(dsrp):
			
		
	def filelist_read(self, filelist_fp, include, filelist_name):
		"""Read filelist from fp, return (tuplelist, something_excluded)"""
		something_excluded, tuple_list = None, []
		prefix_warnings = 0
		while 1:
			line = filelist_fp.readline()
			if not line: break
			try: tuple = self.filelist_parse_line(line, include)
			except FilePrefixError, exp:
				prefix_warnings += 1
				if prefix_warnings < 6:
					Log("Warning: file specification %s in filelist %s\n"
						"doesn't start with correct prefix %s, ignoring." %
						(exp[0], filelist_name, exp[1]), 2)
					if prefix_warnings == 5:
						Log("Future prefix errors will not be logged.", 2)
			tuple_list.append(tuple)
			if not tuple[1]: something_excluded = 1
		return (tuple_list, something_excluded)

	def filelist_parse_line(self, line, include, prefix):
		"""Parse a single line of a filelist, returning a pair

		pair will be of form (index, include), where index is another
		tuple, and include is 1 if the line specifies that we are
		including a file.  The default is given as an argument.
		prefix is the string that the index is relative to.

		"""
		line = line.strip()
		if line[:2] == "+ ": # Check for "+ "/"- " syntax
			include = 1
			line = line[2:]
		elif line[:2] == "- ":
			include = 0
			line = line[2:]

		if not line.startswith(prefix+"/"):
			raise FilePrefixError(line, prefix+"/")
		index = filter(lambda x: x, line.split("/")) # remove empties
		return (index, include)

	def filelist_pair_match(self, dsrp, pair):
		"""Return 0/1 if pair excludes/includes dsrp, None if doesn't match"""
		index, include = pair
		assert include == 0 or include == 1
		if not include and dsrp.index[:len(index)] == index:
			return 0 # /foo matches /foo/bar/baz
		elif include and index[:len(dsrp.index)] == dsrp.index:
			return 1 # /foo/bar implicitly matches /foo for includes only
		else: return None
