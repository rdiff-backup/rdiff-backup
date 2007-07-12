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

"""Coordinate corresponding files with different names

For instance, some source filenames may contain characters not allowed
on the mirror end.  These files must be called something different on
the mirror end, so we escape the offending characters with semicolons.

One problem/complication is that all this escaping may put files over
the 256 or whatever limit on the length of file names.  (We just don't
handle that error.)

"""

import re, types
import Globals, log, rpath

# If true, enable character quoting, and set characters making
# regex-style range.
chars_to_quote = None

# These compiled regular expressions are used in quoting and unquoting
chars_to_quote_regexp = None
unquoting_regexp = None

# Use given char to quote.  Default is set in Globals.
quoting_char = None


class QuotingException(Exception): pass

def set_init_quote_vals():
	"""Set quoting value from Globals on all conns"""
	for conn in Globals.connections:
		conn.FilenameMapping.set_init_quote_vals_local()

def set_init_quote_vals_local():
	"""Set value on local connection, initialize regexps"""
	global chars_to_quote, quoting_char
	chars_to_quote = Globals.chars_to_quote
	if len(Globals.quoting_char) != 1:
		log.Log.FatalError("Expected single character for quoting char,"
						   "got '%s' instead" % (Globals.quoting_char,))
	quoting_char = Globals.quoting_char
	init_quoting_regexps()

def init_quoting_regexps():
	"""Compile quoting regular expressions"""
	global chars_to_quote_regexp, unquoting_regexp
	assert chars_to_quote and type(chars_to_quote) is types.StringType, \
		   "Chars to quote: '%s'" % (chars_to_quote,)
	try:
		chars_to_quote_regexp = \
				 re.compile("[%s]|%s" % (chars_to_quote, quoting_char), re.S)
		unquoting_regexp = re.compile("%s[0-9]{3}" % quoting_char, re.S)
	except re.error:
		log.Log.FatalError("Error '%s' when processing char quote list '%s'" %
						   (re.error, chars_to_quote))

def quote(path):
	"""Return quoted version of given path

	Any characters quoted will be replaced by the quoting char and
	the ascii number of the character.  For instance, "10:11:12"
	would go to "10;05811;05812" if ":" were quoted and ";" were
	the quoting character.

	"""
	QuotedPath = chars_to_quote_regexp.sub(quote_single, path)
	if not Globals.must_escape_dos_devices:
		return QuotedPath

	# Escape first char of any special DOS device files even if filename has an
	# extension.  Special names are: aux, prn, con, nul, com0-9, and lpt1-9.
	if not re.search(r"^aux(\..*)*$|^prn(\..*)*$|^con(\..*)*$|^nul(\..*)*$|" \
					 r"^com[0-9](\..*)*$|^lpt[1-9]{1}(\..*)*$", QuotedPath, \
					 re.I):
		return QuotedPath
	return "%s%03d" % (quoting_char, ord(QuotedPath[0])) + QuotedPath[1:]

def quote_single(match):
	"""Return replacement for a single character"""
	return "%s%03d" % (quoting_char, ord(match.group()))

def unquote(path):
	"""Return original version of quoted filename"""
	return unquoting_regexp.sub(unquote_single, path)

def unquote_single(match):
	"""Unquote a single quoted character"""
	if not len(match.group()) == 4:
		raise QuotingException("Quoted group wrong size: " + match.group())
	try: return chr(int(match.group()[1:]))
	except ValueError:
		raise QuotingException("Quoted out of range: " + match.group())


class QuotedRPath(rpath.RPath):
	"""RPath where the filename is quoted version of index

	We use QuotedRPaths so we don't need to remember to quote RPaths
	derived from this one (via append or new_index).  Note that only
	the index is quoted, not the base.

	"""
	def __init__(self, connection, base, index = (), data = None):
		"""Make new QuotedRPath"""
		self.quoted_index = tuple(map(quote, index))
		rpath.RPath.__init__(self, connection, base, self.quoted_index, data)
		self.index = index

	def listdir(self):
		"""Return list of unquoted filenames in current directory

		We want them unquoted so that the results can be sorted
		correctly and append()ed to the currect QuotedRPath.

		"""
		return map(unquote, self.conn.os.listdir(self.path))

	def __str__(self):
		return "QuotedPath: %s\nIndex: %s\nData: %s" % \
			   (self.path, self.index, self.data)

	def isincfile(self):
		"""Return true if path indicates increment, sets various variables"""
		if not self.index: # consider the last component as quoted
			dirname, basename = self.dirsplit()
			temp_rp = rpath.RPath(self.conn, dirname, (unquote(basename),))
			result = temp_rp.isincfile()
			if result:
				self.inc_basestr = unquote(temp_rp.inc_basestr)
				self.inc_timestr = unquote(temp_rp.inc_timestr)
		else:
			result = rpath.RPath.isincfile(self)
			if result: self.inc_basestr = unquote(self.inc_basestr)
		return result
		
def get_quotedrpath(rp, separate_basename = 0):
	"""Return quoted version of rpath rp"""
	assert not rp.index # Why would we starting quoting "in the middle"?
	if separate_basename:
		dirname, basename = rp.dirsplit()
		return QuotedRPath(rp.conn, dirname, (unquote(basename),), rp.data)
	else: return QuotedRPath(rp.conn, rp.base, (), rp.data)

def get_quoted_sep_base(filename):
	"""Get QuotedRPath from filename assuming last bit is quoted"""
	return get_quotedrpath(rpath.RPath(Globals.local_connection, filename), 1)
