execfile("selection.py")
import re

#######################################################################
#
# filename_mapping - used to coordinate related filenames
#
# For instance, some source filenames may contain characters not
# allowed on the mirror end.  Also, if a source filename is very long
# (say 240 characters), the extra characters added to related
# increments may put them over the usual 255 character limit.
#

class FilenameMapping:
	"""Contains class methods which coordinate related filenames"""
	max_filename_length = 255

	# If true, enable character quoting, and set characters making
	# regex-style range.
	chars_to_quote = None

	# These compiled regular expressions are used in quoting and unquoting
	chars_to_quote_regexp = None
	unquoting_regexp = None

	# Use given char to quote.  Default is set in Globals.
	quoting_char = None

	def set_init_quote_vals(cls):
		"""Set quoting value from Globals on all conns"""
		for conn in Globals.connections:
			conn.FilenameMapping.set_init_quote_vals_local()
		
	def set_init_quote_vals_local(cls):
		"""Set value on local connection, initialize regexps"""
		cls.chars_to_quote = Globals.chars_to_quote
		if len(Globals.quoting_char) != 1:
			Log.FatalError("Expected single character for quoting char,"
						   "got '%s' instead" % (Globals.quoting_char,))
		cls.quoting_char = Globals.quoting_char
		cls.init_quoting_regexps()

	def init_quoting_regexps(cls):
		"""Compile quoting regular expressions"""
		try:
			cls.chars_to_quote_regexp = \
			   re.compile("[%s%s]" % (cls.chars_to_quote,
									  cls.quoting_char), re.S)
			cls.unquoting_regexp = \
			   re.compile("%s[0-9]{3}" % cls.quoting_char, re.S)
		except re.error:
			Log.FatalError("Error '%s' when processing char quote list %s" %
						   (re.error, cls.chars_to_quote))

	def quote(cls, path):
		"""Return quoted version of given path

		Any characters quoted will be replaced by the quoting char and
		the ascii number of the character.  For instance, "10:11:12"
		would go to "10;05811;05812" if ":" were quoted and ";" were
		the quoting character.

		"""
		return cls.chars_to_quote_regexp.sub(cls.quote_single, path)

	def quote_single(cls, match):
		"""Return replacement for a single character"""
		return "%s%03d" % (cls.quoting_char, ord(match.group()))

	def unquote(cls, path):
		"""Return original version of quoted filename"""
		return cls.unquoting_regexp.sub(cls.unquote_single, path)

	def unquote_single(cls, match):
		"""Unquote a single quoted character"""
		assert len(match.group()) == 4
		return chr(int(match.group()[1:]))

	def get_quoted_dir_children(cls, rpath):
		"""For rpath directory, return list of quoted children in dir"""
		if not rpath.isdir(): return []
		dir_pairs = [(cls.unquote(filename), filename)
					 for filename in rpath.listdir()]
		dir_pairs.sort() # sort by real index, not quoted part
		child_list = []
		for unquoted, filename in dir_pairs:
			childrp = rpath.append(unquoted)
			childrp.quote_path()
			child_list.append(childrp)
		return child_list

MakeClass(FilenameMapping)

