from __future__ import generators
execfile("destructive_stepping.py")
import re

#######################################################################
#
# selection - Provides the iterator-like DSRPIterator class
#
# Parses includes and excludes to yield correct files.  More
# documentation on what this code does can be found on the man page.
#

class SelectError(Exception):
	"""Some error dealing with the Select class"""
	pass

class FilePrefixError(SelectError):
	"""Signals that a specified file doesn't start with correct prefix"""
	pass

class GlobbingError(SelectError):
	"""Something has gone wrong when parsing a glob string"""
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
	# This re should not match normal filenames, but usually just globs
	glob_re = re.compile("(.*[*?[]|ignorecase\\:)", re.I | re.S)

	def __init__(self, dsrpath, quoted_filenames = None):
		"""DSRPIterator initializer.  dsrp is the root directory

		When files have quoted characters in them, quoted_filenames
		should be true.  Then RPath's index will be the unquoted
		version.

		"""
		assert isinstance(dsrpath, DSRPath)
		self.selection_functions = []
		self.dsrpath = dsrpath
		self.prefix = self.dsrpath.path
		self.quoting_on = Globals.quoting_enabled and quoted_filenames

	def set_iter(self, starting_index = None, sel_func = None):
		"""Initialize more variables, get ready to iterate

		Will iterate indicies greater than starting_index.  Selection
		function sel_func is called on each dsrp and is usually
		self.Select.  Returns self just for convenience.

		"""
		if not sel_func: sel_func = self.Select
		self.dsrpath.setdata() # this may have changed since Select init
		if starting_index is not None:
			self.starting_index = starting_index
			self.iter = self.iterate_starting_from(self.dsrpath,
						            self.iterate_starting_from, sel_func)
		else: self.iter = self.Iterate(self.dsrpath, self.Iterate, sel_func)
		self.next = self.iter.next
		self.__iter__ = lambda: self
		return self

	def Iterate(self, dsrpath, rec_func, sel_func):
		"""Return iterator yielding dsrps in dsrpath

		rec_func is usually the same as this function and is what
		Iterate uses to find files in subdirectories.  It is used in
		iterate_starting_from.

		sel_func is the selection function to use on the dsrps.  It is
		usually self.Select.

		"""
		s = sel_func(dsrpath)
		if s == 0: return
		elif s == 1: # File is included
			yield dsrpath
			if dsrpath.isdir():
				for dsrp in self.iterate_in_dir(dsrpath, rec_func, sel_func):
					yield dsrp
		elif s == 2 and dsrpath.isdir(): # Directory is merely scanned
			iid = self.iterate_in_dir(dsrpath, rec_func, sel_func)
			try: first = iid.next()
			except StopIteration: return # no files inside; skip dsrp
			yield dsrpath
			yield first
			for dsrp in iid: yield dsrp

	def iterate_in_dir(self, dsrpath, rec_func, sel_func):
		"""Iterate the dsrps in directory dsrpath."""
		if self.quoting_on:
			for subdir in FilenameMapping.get_quoted_dir_children(dsrpath):
				for dsrp in rec_func(subdir, rec_func, sel_func): yield dsrp
		else:
			for filename in Robust.listrp(dsrpath):
				new_dsrp = Robust.check_common_error(
					lambda: dsrpath.append(filename))
				if not new_dsrp:
					Log("Error initializing file %s" % dsrpath.path, 2)
				else:
					for dsrp in rec_func(new_dsrp, rec_func, sel_func):
						yield dsrp

	def iterate_starting_from(self, dsrpath, rec_func, sel_func):
		"""Like Iterate, but only yield indicies > self.starting_index"""
		if dsrpath.index > self.starting_index: # past starting_index
			for dsrp in self.Iterate(dsrpath, self.Iterate, sel_func):
				yield dsrp
		elif dsrpath.index == self.starting_index[:len(dsrpath.index)]:
			# May encounter starting index on this branch
			for dsrp in self.iterate_in_dir(dsrpath,
											self.iterate_starting_from,
											sel_func): yield dsrp

	def iterate_with_finalizer(self):
		"""Like Iterate, but missing some options, and add finalizer"""
		finalize = DestructiveSteppingFinalizer()
		for dsrp in self:
			yield dsrp
			finalize(dsrp.index, dsrp)
		finalize.Finish()

	def Select(self, dsrp):
		"""Run through the selection functions and return dominant val 0/1/2"""
		for sf in self.selection_functions:
			result = sf(dsrp)
			if result is not None: return result
		return 1

	def ParseArgs(self, argtuples, filelists):
		"""Create selection functions based on list of tuples

		The tuples have the form (option string, additional argument)
		and are created when the initial commandline arguments are
		read.  The reason for the extra level of processing is that
		the filelists may only be openable by the main connection, but
		the selection functions need to be on the backup reader or
		writer side.  When the initial arguments are parsed the right
		information is sent over the link.

		"""
		filelists_index = 0
		try:
			for opt, arg in argtuples:
				if opt == "--exclude":
					self.add_selection_func(self.glob_get_sf(arg, 0))
				elif opt == "--exclude-device-files":
					self.add_selection_func(self.devfiles_get_sf())
				elif opt == "--exclude-filelist":
					self.add_selection_func(self.filelist_get_sf(
						filelists[filelists_index], 0, arg))
					filelists_index += 1
				elif opt == "--exclude-regexp":
					self.add_selection_func(self.regexp_get_sf(arg, 0))
				elif opt == "--include":
					self.add_selection_func(self.glob_get_sf(arg, 1))
				elif opt == "--include-filelist":
					self.add_selection_func(self.filelist_get_sf(
						filelists[filelists_index], 1, arg))
					filelists_index += 1
				elif opt == "--include-regexp":
					self.add_selection_func(self.regexp_get_sf(arg, 1))
				else: assert 0, "Bad selection option %s" % opt
		except SelectError, e: self.parse_catch_error(e)
		assert filelists_index == len(filelists)

		self.parse_last_excludes()
		self.parse_rbdir_exclude()
		self.parse_proc_exclude()

	def parse_catch_error(self, exc):
		"""Deal with selection error exc"""
		if isinstance(exc, FilePrefixError):
			Log.FatalError(
"""Fatal Error: The file specification
    %s
cannot match any files in the base directory
    %s
Useful file specifications begin with the base directory or some
pattern (such as '**') which matches the base directory.""" %
			(exc, self.prefix))
		elif isinstance(e, GlobbingError):
			Log.FatalError("Fatal Error while processing expression\n"
						   "%s" % exc)
		else: raise

	def parse_rbdir_exclude(self):
		"""Add exclusion of rdiff-backup-data dir to front of list"""
		self.add_selection_func(
			self.glob_get_tuple_sf(("rdiff-backup-data",), 0), 1)

	def parse_proc_exclude(self):
		"""Exclude the /proc directory if starting from /"""
		if self.prefix == "/":
			self.add_selection_func(self.glob_get_tuple_sf(("proc",), 0), 1)

	def parse_last_excludes(self):
		"""Exit with error if last selection function isn't an exclude"""
		if (self.selection_functions and
			not self.selection_functions[-1].exclude):
			Log.FatalError(
"""Last selection expression:
    %s
only specifies that files be included.  Because the default is to
include all files, the expression is redundant.  Exiting because this
probably isn't what you meant.""" %
			(self.selection_functions[-1].name, self.prefix))

	def add_selection_func(self, sel_func, add_to_start = None):
		"""Add another selection function at the end or beginning"""
		if add_to_start: self.selection_functions.insert(0, sel_func)
		else: self.selection_functions.append(sel_func)

	def filelist_get_sf(self, filelist_fp, inc_default, filelist_name):
		"""Return selection function by reading list of files

		The format of the filelist is documented in the man page.
		filelist_fp should be an (open) file object.
		inc_default should be true if this is an include list,
		false for an exclude list.
		filelist_name is just a string used for logging.

		"""
		Log("Reading filelist %s" % filelist_name, 4)
		tuple_list, something_excluded = \
					self.filelist_read(filelist_fp, inc_default, filelist_name)
		Log("Sorting filelist %s" % filelist_name, 4)
		tuple_list.sort()
		i = [0] # We have to put index in list because of stupid scoping rules

		def selection_function(dsrp):
			while 1:
				if i[0] >= len(tuple_list): return None
				include, move_on = \
						 self.filelist_pair_match(dsrp, tuple_list[i[0]])
				if move_on:
					i[0] += 1
					if include is None: continue # later line may match
				return include

		selection_function.exclude = something_excluded
		selection_function.name = "Filelist: " + filelist_name
		return selection_function

	def filelist_read(self, filelist_fp, include, filelist_name):
		"""Read filelist from fp, return (tuplelist, something_excluded)"""
		something_excluded, tuple_list = None, []
		prefix_warnings = 0
		for line in filelist_fp:
			if not line.strip(): continue # skip blanks
			try: tuple = self.filelist_parse_line(line, include)
			except FilePrefixError, exp:
				prefix_warnings += 1
				if prefix_warnings < 6:
					Log("Warning: file specification %s in filelist %s\n"
						"doesn't start with correct prefix %s, ignoring." %
						(exp, filelist_name, self.prefix), 2)
					if prefix_warnings == 5:
						Log("Future prefix errors will not be logged.", 2)
			tuple_list.append(tuple)
			if not tuple[1]: something_excluded = 1
		if filelist_fp.close():
			Log("Error closing filelist %s" % filelist_name, 2)
		return (tuple_list, something_excluded)

	def filelist_parse_line(self, line, include):
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

		if not line.startswith(self.prefix): raise FilePrefixError(line)
		line = line[len(self.prefix):] # Discard prefix
		index = tuple(filter(lambda x: x, line.split("/"))) # remove empties
		return (index, include)

	def filelist_pair_match(self, dsrp, pair):
		"""Matches a filelist tuple against a dsrp

		Returns a pair (include, move_on).  include is None if the
		tuple doesn't match either way, and 0/1 if the tuple excludes
		or includes the dsrp.

		move_on is true if the tuple cannot match a later index, and
		so we should move on to the next tuple in the index.

		"""
		index, include = pair
		if include == 1:
			if index < dsrp.index: return (None, 1)
			if index == dsrp.index: return (1, 1)
			elif index[:len(dsrp.index)] == dsrp.index:
				return (1, None) # /foo/bar implicitly includes /foo
			else: return (None, None) # dsrp greater, not initial sequence
		elif include == 0:
			if dsrp.index[:len(index)] == index:
				return (0, None) # /foo implicitly excludes /foo/bar
			elif index < dsrp.index: return (None, 1)
			else: return (None, None) # dsrp greater, not initial sequence
		else: assert 0, "Include is %s, should be 0 or 1" % (include,)

	def regexp_get_sf(self, regexp_string, include):
		"""Return selection function given by regexp_string"""
		assert include == 0 or include == 1
		try: regexp = re.compile(regexp_string)
		except:
			Log("Error compiling regular expression %s" % regexp_string, 1)
			raise
		
		def sel_func(dsrp):
			if regexp.search(dsrp.path): return include
			else: return None

		sel_func.exclude = not include
		sel_func.name = "Regular expression: %s" % regexp_string
		return sel_func

	def devfiles_get_sf(self):
		"""Return a selection function to exclude all dev files"""
		if self.selection_functions:
			Log("Warning: exclude-device-files is not the first "
				"selector.\nThis may not be what you intended", 3)
		def sel_func(dsrp):
			if dsrp.isdev(): return 0
			else: return None
		sel_func.exclude = 1
		sel_func.name = "Exclude device files"
		return sel_func

	def glob_get_sf(self, glob_str, include):
		"""Return selection function given by glob string"""
		assert include == 0 or include == 1
		if glob_str == "**": sel_func = lambda dsrp: include
		elif not self.glob_re.match(glob_str): # normal file
			sel_func = self.glob_get_filename_sf(glob_str, include)
		else: sel_func = self.glob_get_normal_sf(glob_str, include)

		sel_func.exclude = not include
		sel_func.name = "Command-line glob: %s" % glob_str
		return sel_func

	def glob_get_filename_sf(self, filename, include):
		"""Get a selection function given a normal filename

		Some of the parsing is better explained in
		filelist_parse_line.  The reason this is split from normal
		globbing is things are a lot less complicated if no special
		globbing characters are used.

		"""
		if not filename.startswith(self.prefix):
			raise FilePrefixError(filename)
		index = tuple(filter(lambda x: x,
							 filename[len(self.prefix):].split("/")))
		return self.glob_get_tuple_sf(index, include)

	def glob_get_tuple_sf(self, tuple, include):
		"""Return selection function based on tuple"""
		def include_sel_func(dsrp):
			if (dsrp.index == tuple[:len(dsrp.index)] or
				dsrp.index[:len(tuple)] == tuple):
				return 1 # /foo/bar implicitly matches /foo, vice-versa
			else: return None

		def exclude_sel_func(dsrp):
			if dsrp.index[:len(tuple)] == tuple:
				return 0 # /foo excludes /foo/bar, not vice-versa
			else: return None

		if include == 1: sel_func = include_sel_func
		elif include == 0: sel_func = exclude_sel_func
		sel_func.exclude = not include
		sel_func.name = "Tuple select %s" % (tuple,)
		return sel_func

	def glob_get_normal_sf(self, glob_str, include):
		"""Return selection function based on glob_str

		The basic idea is to turn glob_str into a regular expression,
		and just use the normal regular expression.  There is a
		complication because the selection function should return '2'
		(scan) for directories which may contain a file which matches
		the glob_str.  So we break up the glob string into parts, and
		any file which matches an initial sequence of glob parts gets
		scanned.

		Thanks to Donovan Baarda who provided some code which did some
		things similar to this.

		"""
		if glob_str.lower().startswith("ignorecase:"):
			re_comp = lambda r: re.compile(r, re.I | re.S)
			glob_str = glob_str[len("ignorecase:"):]
		else: re_comp = lambda r: re.compile(r, re.S)

		# matches what glob matches and any files in directory
		glob_comp_re = re_comp("^%s($|/)" % self.glob_to_re(glob_str))

		if glob_str.find("**") != -1:
			glob_str = glob_str[:glob_str.find("**")+2] # truncate after **

		scan_comp_re = re_comp("^(%s)$" %
							   "|".join(self.glob_get_prefix_res(glob_str)))

		def include_sel_func(dsrp):
			if glob_comp_re.match(dsrp.path): return 1
			elif scan_comp_re.match(dsrp.path): return 2
			else: return None

		def exclude_sel_func(dsrp):
			if glob_comp_re.match(dsrp.path): return 0
			else: return None

		# Check to make sure prefix is ok
		if not include_sel_func(self.dsrpath): raise FilePrefixError(glob_str)
		
		if include: return include_sel_func
		else: return exclude_sel_func

	def glob_get_prefix_res(self, glob_str):
		"""Return list of regexps equivalent to prefixes of glob_str"""
		glob_parts = glob_str.split("/")
		if "" in glob_parts[1:-1]: # "" OK if comes first or last, as in /foo/
			raise GlobbingError("Consecutive '/'s found in globbing string "
								+ glob_str)

		prefixes = map(lambda i: "/".join(glob_parts[:i+1]),
					   range(len(glob_parts)))
		# we must make exception for root "/", only dir to end in slash
		if prefixes[0] == "": prefixes[0] = "/"
		return map(self.glob_to_re, prefixes)

	def glob_to_re(self, pat):
		"""Returned regular expression equivalent to shell glob pat

		Currently only the ?, *, [], and ** expressions are supported.
		Ranges like [a-z] are also currently unsupported.  There is no
		way to quote these special characters.

		This function taken with minor modifications from efnmatch.py
		by Donovan Baarda.

		"""
		i, n, res = 0, len(pat), ''
		while i < n:
			c, s = pat[i], pat[i:i+2]
			i = i+1
			if s == '**':
				res = res + '.*'
				i = i + 1
			elif c == '*': res = res + '[^/]*'
			elif c == '?': res = res + '[^/]'
			elif c == '[':
				j = i
				if j < n and pat[j] in '!^': j = j+1
				if j < n and pat[j] == ']': j = j+1
				while j < n and pat[j] != ']': j = j+1
				if j >= n: res = res + '\\[' # interpret the [ literally
				else: # Deal with inside of [..]
					stuff = pat[i:j].replace('\\','\\\\')
					i = j+1
					if stuff[0] in '!^': stuff = '^' + stuff[1:]
					res = res + '[' + stuff + ']'
			else: res = res + re.escape(c)
		return res

