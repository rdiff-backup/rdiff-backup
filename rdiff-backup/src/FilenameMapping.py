# Copyright 2002 Ben Escoto
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
on the mirror end.  Also, if a source filename is very long (say 240
characters), the extra characters added to related increments may put
them over the usual 255 character limit.

"""

import re
from log import *
from robust import *
import Globals

max_filename_length = 255

# If true, enable character quoting, and set characters making
# regex-style range.
chars_to_quote = None

# These compiled regular expressions are used in quoting and unquoting
chars_to_quote_regexp = None
unquoting_regexp = None

# Use given char to quote.  Default is set in Globals.
quoting_char = None


def set_init_quote_vals():
	"""Set quoting value from Globals on all conns"""
	for conn in Globals.connections:
		conn.FilenameMapping.set_init_quote_vals_local()

def set_init_quote_vals_local():
	"""Set value on local connection, initialize regexps"""
	global chars_to_quote, quoting_char
	chars_to_quote = Globals.chars_to_quote
	if len(Globals.quoting_char) != 1:
		Log.FatalError("Expected single character for quoting char,"
					   "got '%s' instead" % (Globals.quoting_char,))
	quoting_char = Globals.quoting_char
	init_quoting_regexps()

def init_quoting_regexps():
	"""Compile quoting regular expressions"""
	global chars_to_quote_regexp, unquoting_regexp
	try:
		chars_to_quote_regexp = \
				 re.compile("[%s%s]" % (chars_to_quote, quoting_char), re.S)
		unquoting_regexp = re.compile("%s[0-9]{3}" % quoting_char, re.S)
	except re.error:
		Log.FatalError("Error '%s' when processing char quote list %s" %
					   (re.error, chars_to_quote))

def quote(path):
	"""Return quoted version of given path

	Any characters quoted will be replaced by the quoting char and
	the ascii number of the character.  For instance, "10:11:12"
	would go to "10;05811;05812" if ":" were quoted and ";" were
	the quoting character.

	"""
	return chars_to_quote_regexp.sub(quote_single, path)

def quote_single(match):
	"""Return replacement for a single character"""
	return "%s%03d" % (quoting_char, ord(match.group()))

def unquote(path):
	"""Return original version of quoted filename"""
	return unquoting_regexp.sub(unquote_single, path)

def unquote_single(match):
	"""Unquote a single quoted character"""
	assert len(match.group()) == 4
	return chr(int(match.group()[1:]))

def get_quoted_dir_children(rpath):
	"""For rpath directory, return list of quoted children in dir"""
	if not rpath.isdir(): return []
	dir_pairs = [(unquote(filename), filename)
				 for filename in Robust.listrp(rpath)]
	dir_pairs.sort() # sort by real index, not quoted part
	child_list = []
	for unquoted, filename in dir_pairs:
		childrp = rpath.append(unquoted)
		childrp.quote_path()
		child_list.append(childrp)
	return child_list



