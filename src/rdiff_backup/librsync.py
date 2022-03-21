# Copyright 2002 2005 Ben Escoto
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
"""Provides a high-level interface to some librsync functions

This is a python wrapper around the lower-level _librsync module,
which is written in C.  The goal was to use C as little as possible...

"""

import array
from rdiff_backup import _librsync

blocksize = _librsync.RSM_JOB_BLOCKSIZE


class librsyncError(Exception):
    """Signifies error in internal librsync processing (bad signature, etc.)

    underlying _librsync.librsyncError's are regenerated using this
    class because the C-created exceptions are by default
    unPickleable.  There is probably a way to fix this in _librsync,
    but this scheme was easier.

    """
    pass


class LikeFile:
    """File-like object used by SigFile, DeltaFile, and PatchFile"""
    mode = "rb"

    # This will be replaced in subclasses by an object with
    # appropriate cycle() method
    maker = None

    def __init__(self, infile, need_seek=None):
        """LikeFile initializer - zero buffers, set eofs off"""
        self._check_file(infile, need_seek)
        self.infile = infile
        self.closed = self.infile_closed = None
        self.inbuf = b""
        self.outbuf = array.array('b')
        self.eof = self.infile_eof = None

    def read(self, length=-1):
        """Build up self.outbuf, return first length bytes"""
        if length == -1:
            while not self.eof:
                self._add_to_outbuf_once()
            real_len = len(self.outbuf)
        else:
            while not self.eof and len(self.outbuf) < length:
                self._add_to_outbuf_once()
            real_len = min(length, len(self.outbuf))

        return_val = self.outbuf[:real_len].tobytes()
        del self.outbuf[:real_len]
        return return_val

    def close(self):
        """Close infile and pass on infile close value"""
        self.closed = 1
        if self.infile_closed:
            return self.infile_closeval
        else:
            return self.infile.close()

    def _check_file(self, file, need_seek=None):
        """Raise type error if file doesn't have necessary attributes"""
        if not hasattr(file, "read"):
            raise TypeError("Basis file must have a read() method")
        if not hasattr(file, "close"):
            raise TypeError("Basis file must have a close() method")
        if need_seek and not hasattr(file, "seek"):
            raise TypeError("Basis file must have a seek() method")

    def _add_to_outbuf_once(self):
        """Add one cycle's worth of output to self.outbuf"""
        if not self.infile_eof:
            self._add_to_inbuf()
        try:
            self.eof, len_inbuf_read, cycle_out = self.maker.cycle(self.inbuf)
        except _librsync.librsyncError as e:
            raise librsyncError(str(e))
        self.inbuf = self.inbuf[len_inbuf_read:]
        self.outbuf.frombytes(cycle_out)

    def _add_to_inbuf(self):
        """Make sure len(self.inbuf) >= blocksize"""
        while len(self.inbuf) < blocksize:
            new_in = self.infile.read(blocksize)
            if not new_in:
                self.infile_eof = 1
                self.infile_closeval = self.infile.close()
                self.infile_closed = 1
                break
            self.inbuf += new_in


class SigFile(LikeFile):
    """File-like object which incrementally generates a librsync signature"""

    def __init__(self, infile, blocksize=_librsync.RS_DEFAULT_BLOCK_LEN):
        """
        SigFile initializer - takes basis file

        basis file only needs to have read() and close() methods.  It
        will be closed when we come to the end of the signature.
        """
        LikeFile.__init__(self, infile)
        try:
            self.maker = _librsync.new_sigmaker(blocksize)
        except _librsync.librsyncError as e:
            raise librsyncError(str(e))


class DeltaFile(LikeFile):
    """File-like object which incrementally generates a librsync delta"""

    def __init__(self, signature, new_file):
        """DeltaFile initializer - call with signature and new file

        Signature can either be a string or a file with read() and
        close() methods.  New_file also only needs to have read() and
        close() methods.  It will be closed when self is closed.

        """
        LikeFile.__init__(self, new_file)
        if type(signature) is bytes:
            sig_string = signature
        else:
            self._check_file(signature)
            sig_string = signature.read()
            signature.close()
        try:
            self.maker = _librsync.new_deltamaker(sig_string)
        except _librsync.librsyncError as e:
            raise librsyncError(str(e))


class PatchedFile(LikeFile):
    """File-like object which applies a librsync delta incrementally"""

    def __init__(self, basis_file, delta_file):
        """PatchedFile initializer - call with basis delta

        Here basis_file must be a true Python file, because we may
        need to seek() around in it a lot, and this is done in C.
        delta_file only needs read() and close() methods.

        """
        LikeFile.__init__(self, delta_file)
        if hasattr(basis_file, 'file'):
            self.basis_file = basis_file.file
        else:
            self.basis_file = basis_file
        if not (self.basis_file.fileno() and self.basis_file.seekable()):
            raise TypeError("basis_file must be a (true) file")
        try:
            self.maker = _librsync.new_patchmaker(self.basis_file)
        except _librsync.librsyncError as e:
            raise librsyncError(str(e))

    def close(self):
        delta_close = LikeFile.close(self)
        self.basis_file.close()
        # sadly, we can only return one value, which also contains the SHA1 digest
        return delta_close


class SigGenerator:
    """Calculate signature.

    Input and output is same as SigFile, but the interface is like md5
    module, not filelike object
    FIXME: is only used within test suite librsynctest.py
    """

    def __init__(self, blocksize=_librsync.RS_DEFAULT_BLOCK_LEN):
        """Return new signature instance"""
        try:
            self.sig_maker = _librsync.new_sigmaker(blocksize)
        except _librsync.librsyncError as e:
            raise librsyncError(str(e))
        self.gotsig = None
        self.buffer = b""
        self.sig_string = b""

    def update(self, buf):
        """Add buf to data that signature will be calculated over"""
        if self.gotsig:
            raise librsyncError("SigGenerator already provided signature")
        self.buffer += buf
        while len(self.buffer) >= blocksize:
            if self._process_buffer():
                raise librsyncError("Premature EOF received from sig_maker")

    def get_sig(self):
        """Return signature over given data"""
        while not self._process_buffer():
            pass  # keep running until eof
        return self.sig_string

    def _process_buffer(self):
        """Run self.buffer through sig_maker, add to self.sig_string"""
        try:
            eof, len_buf_read, cycle_out = self.sig_maker.cycle(self.buffer)
        except _librsync.librsyncError as e:
            raise librsyncError(str(e))
        self.buffer = self.buffer[len_buf_read:]
        self.sig_string += cycle_out
        return eof
