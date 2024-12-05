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
Simple functions to safely transform bytes and other objects to string and vice-versa
"""

import typing

# Pre-define the different byte abbreviations
BYTES_ABBREVS: typing.Final[list[str]] = [
    "B",
    "KiB",
    "MiB",
    "GiB",
    "TiB",
    "PiB",
    "EiB",
    "ZiB",
    "YiB",
]


def to_safe_str(something: typing.Any) -> str:
    """Transform bytes into string without risk of conversion error"""
    if isinstance(something, bytes):
        return str(something, errors="replace")
    else:
        return str(something)


def to_safe_bytes(something: str, encoding: str = "utf-8") -> bytes:
    """
    Convert string into bytes in a safe way
    """
    return something.encode(encoding=encoding, errors="backslashreplace")


def to_human_size_str(bytes_size: int) -> str:
    """
    Turn bytes sizes into human readable string like "7.23GB".
    """
    # Keep the sign of the size
    if bytes_size < 0:
        sign = "-"
        bytes_size = -bytes_size
    else:
        sign = ""

    # Special case for sizes in bytes
    if bytes_size < 1024:
        return "{0}{1} B".format(sign, bytes_size)

    # Find the nearest abbreviation based on the logarithm of the size
    bytes_num: float = float(bytes_size) / 1024.0
    bytes_log: int = 1
    while bytes_num >= 1024 and bytes_log < 8:
        bytes_num /= 1024.0
        bytes_log += 1
    abbrev = BYTES_ABBREVS[bytes_log]

    # Calculate the precision to keep at least 3 relevant digits
    precision: int
    if bytes_num >= 100:
        precision = 0
    elif bytes_num >= 10:
        precision = 1
    else:
        precision = 2

    return "{0}{1:.{2}f} {3}".format(sign, bytes_num, precision, abbrev)
