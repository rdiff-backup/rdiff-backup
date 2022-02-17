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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA
"""
Two simple functions to quote and unquote paths, quoting newlines to keep
any path on one line
"""

import re

_CHARS_TO_QUOTE = re.compile(b"\\n|\\\\")
_CHARS_TO_UNQUOTE = re.compile(b"\\\\n|\\\\\\\\")


def quote_path(path_string):
    """
    Return quoted version of path_string

    Because newlines are used to separate fields in a record, they are
    replaced with \n.  Backslashes become \\ and everything else is
    left the way it is.
    """

    def replacement_func(match_obj):
        """This is called on the match obj of any char that needs quoting"""
        char = match_obj.group(0)
        if char == b"\n":
            return b"\\n"
        elif char == b"\\":
            return b"\\\\"
        else:
            raise re.error(
                "Bad char '{bc}' shouldn't need quoting".format(bc=char))

    return _CHARS_TO_QUOTE.sub(replacement_func, path_string)


def unquote_path(quoted_string):
    """
    Reverse what was done by quote_path
    """

    def replacement_func(match_obj):
        """Unquote match obj of two character sequence"""
        two_chars = match_obj.group(0)
        if two_chars == b"\\n":
            return b"\n"
        elif two_chars == b"\\\\":
            return b"\\"
        else:
            raise re.error(
                "Unknown quoted sequence {qs} found".format(qs=two_chars))

    return _CHARS_TO_UNQUOTE.sub(replacement_func, quoted_string)
