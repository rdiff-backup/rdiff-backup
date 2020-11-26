# Copyright 2005 Ben Escoto
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
"""Contains a file wrapper that returns a hash on close"""

import hashlib
from . import Globals


class FileWrapper:
    """Wrapper around a file-like object

    Only use this with files that will be read through in a single
    pass and then closed.  (There is no seek().)  When you close it,
    return value will be a Report.

    Currently this just calculates a sha1sum of the datastream.

    """

    def __init__(self, fileobj):
        self.fileobj = fileobj
        self.sha1 = hashlib.sha1()
        self.closed = False

    def read(self, length=-1):
        assert not self.closed, "You can't read from an already closed file."
        buf = self.fileobj.read(length)
        self.sha1.update(buf)
        return buf

    def close(self):
        self.closed = True
        return Report(self.fileobj.close(), self.sha1.hexdigest())


class Report:
    """Hold final information about a byte stream"""

    def __init__(self, close_val, sha1_digest):
        # FIXME this is a strange construct because it looks like the fileobj
        # wrapped in a FileWrapper already returns a Report as closing value,
        # which we can't wrap again in a Report, so we only check that the
        # hash values do fit.
        if isinstance(close_val, Report):
            assert close_val.sha1_digest == sha1_digest, (
                "Hashes from return code {hash1} and given {hash2} "
                "don't match".format(
                    hash1=close_val.sha1_digest, hash2=sha1_digest))
        else:
            assert not close_val, (
                "Return code {rc} of type {rctype} isn't null".format(
                    rc=close_val, rctype=type(close_val)))
        self.sha1_digest = sha1_digest


def compute_sha1(rp, compressed=0):
    """Return the hex sha1 hash of given rpath"""
    assert rp.conn is Globals.local_connection, (
        "It's inefficient to calculate hash remotely.")
    digest = compute_sha1_fp(rp.open("rb", compressed))
    rp.set_sha1(digest)
    return digest


def compute_sha1_fp(fp, compressed=0):
    """Return hex sha1 hash of given file-like object"""
    blocksize = Globals.blocksize
    fw = FileWrapper(fp)
    while fw.read(blocksize):
        pass  # we rely on FileWrapper to calculate the checksum
    return fw.close().sha1_digest
