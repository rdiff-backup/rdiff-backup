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
Hold a variety of constants which should have the same value across client/server
connection. If those values change, are removed or added, this probably mean the
need for a new major version to show backward incompatible changes.
"""

import typing

# Pre-defined return codes, they must be potence of 2 so that they can be
# combined.
# FIXME consistent implementation of return codes isn't yet done
RET_CODE_OK: typing.Final[int] = 0  # everything is fine
RET_CODE_ERR: typing.Final[int] = 1  # some fatal error, the whole action failed
RET_CODE_WARN: typing.Final[int] = 2  # unexpected issue without complete failure
RET_CODE_FILE_ERR: typing.Final[int] = 4  # single file (or more) failure
RET_CODE_FILE_WARN: typing.Final[int] = 8  # single file (or more) warning or difference

# This determines how many bytes to read at a time when copying
BLOCKSIZE: typing.Final[int] = 131072

# This is used by the BufferedRead class to determine how many
# bytes to request from the underlying file per read().  Larger
# values may save on connection overhead and latency.
CONN_BUFSIZE: typing.Final[int] = 393216

# This is used in the CacheCollatedPostProcess and MiscIterToFile
# classes.  The number represents the number of rpaths which may be
# stuck in buffers when moving over a remote connection.
PIPELINE_MAX_LENGTH: int = 500

# This represents the pickle protocol used by rdiff-backup over the connection
# https://docs.python.org/3/library/pickle.html#pickle-protocols
# Note that the receiving end will automatically recognize the protocol used so
# that both ends don't need to use the same one to send, as long as they both
# understand the maximum protocol version used.
# Protocol 4 is understood since Python 3.4, protocol 5 since 3.8.
PICKLE_PROTOCOL: typing.Final[int] = 4

# the quoting character is used to mark quoted characters
QUOTING_CHAR: typing.Final[bytes] = b";"
