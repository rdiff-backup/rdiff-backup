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
"""Convert an iterator to a file object and vice-versa"""

import pickle
import array
from . import Globals, robust, rpath


class IterFileException(Exception):
    pass


class UnwrapFile:
    """Contains some basic methods for parsing a file containing an iter"""

    def __init__(self, file):
        self.file = file

    def _get(self):
        """Return pair (type, data) next in line on the file

        type is a single character which is either
        "o" for an object,
        "f" for file,
        "c" for a continuation of a file,
        "h" for the close value of a file
        "e" for an exception, or
        None if no more data can be read.

        Data is either the file's data, if type is "c" or "f", or the
        actual object if the type is "o", "e", or "r"

        """
        header = self.file.read(8)
        if not header:
            return None, None
        if len(header) != 8:
            assert None, "Header %s is only %d bytes" % (header, len(header))
        # [0:1] makes sure that the type remains a byte and not an int
        type, length = header[0:1], self._b2i(header[1:])
        buf = self.file.read(length)
        if type in b"oeh":
            return type, pickle.loads(buf)
        else:
            assert type in b"fc"
            return type, buf

    def _b2i(self, b):
        """Convert bytes to int using big endian byteorder"""
        return int.from_bytes(b, byteorder='big')


class IterWrappingFile(UnwrapFile):
    """An iterator generated from a file.

    Initialize with a file type object, and then it will return the
    elements of the file in order.

    """

    def __init__(self, file):
        UnwrapFile.__init__(self, file)
        self.currently_in_file = None

    def __iter__(self):
        return self

    def __next__(self):
        if self.currently_in_file:
            self.currently_in_file.close()  # no error checking by this point
        type, data = self._get()
        if not type:
            raise StopIteration
        if type == b"o" or type == b"e":
            return data
        elif type == b"f":
            return IterVirtualFile(self, data)
        else:
            raise IterFileException("Bad file type %s" % type)


class IterVirtualFile(UnwrapFile):
    """Another version of a pretend file

    This is returned by IterWrappingFile when a file is embedded in
    the main file that the IterWrappingFile is based around.

    """

    def __init__(self, iwf, initial_data):
        """Initializer

        initial_data is the data from the first block of the file.
        iwf is the iter wrapping file that spawned this
        IterVirtualFile.

        """
        UnwrapFile.__init__(self, iwf.file)
        self.iwf = iwf
        iwf.currently_in_file = self
        self.buffer = initial_data
        self.closed = None
        if not initial_data:
            self.set_close_val()

    def read(self, length=-1):
        """Read length bytes from the file, updating buffers as necessary"""
        assert not self.closed
        if self.iwf.currently_in_file:
            if length >= 0:
                while length >= len(self.buffer):
                    if not self.addtobuffer():
                        break
                real_len = min(length, len(self.buffer))
            else:
                while 1:
                    if not self.addtobuffer():
                        break
                real_len = len(self.buffer)
        else:
            real_len = min(length, len(self.buffer))

        return_val = self.buffer[:real_len]
        self.buffer = self.buffer[real_len:]
        return return_val

    def addtobuffer(self):
        """Read a chunk from the file and add it to the buffer"""
        assert self.iwf.currently_in_file
        type, data = self.iwf._get()
        if type == b"e":
            self.iwf.currently_in_file = None
            raise data
        assert type == b"c", "Type is %s instead of c" % type
        if data:
            self.buffer += data
            return 1
        else:
            self.set_close_val()
            return None

    def set_close_val(self):
        """Read the close value and clear currently_in_file"""
        assert self.iwf.currently_in_file
        self.iwf.currently_in_file = None
        type, object = self.iwf._get()
        assert type == b'h', type
        self.close_value = object

    def close(self):
        """Currently just reads whats left and discards it"""
        while self.iwf.currently_in_file:
            self.addtobuffer()
            self.buffer = ""
        self.closed = 1
        return self.close_value


class FileWrappingIter:
    """A file interface wrapping around an iterator

    This is initialized with an iterator, and then converts it into a
    stream of characters.  The object will evaluate as little of the
    iterator as is necessary to provide the requested bytes.

    The actual file is a sequence of marshaled objects, each preceded
    by 8 bytes which identifies the following the type of object, and
    specifies its length.  File objects are not marshalled, but the
    data is written in chunks of Globals.blocksize, and the following
    blocks can identify themselves as continuations.

    """

    def __init__(self, iter):
        """Initialize with iter"""
        self.iter = iter
        self.array_buf = array.array('b')
        self.currently_in_file = None
        self.closed = None

    def read(self, length):
        """Return next length bytes in file"""
        assert not self.closed
        while len(self.array_buf) < length:
            if not self.addtobuffer():
                break

        result = self.array_buf[:length].tobytes()
        del self.array_buf[:length]
        return result

    def addtobuffer(self):
        """Updates self.buffer, adding a chunk from the iterator.

        Returns None if we have reached the end of the iterator,
        otherwise return true.

        """
        if self.currently_in_file:
            self.addfromfile(b"c")
        else:
            try:
                currentobj = next(self.iter)
            except StopIteration:
                return None
            if hasattr(currentobj, "read") and hasattr(currentobj, "close"):
                self.currently_in_file = currentobj
                self.addfromfile(b"f")
            else:
                pickled_data = pickle.dumps(currentobj, 1)
                self.array_buf.frombytes(b"o")
                self.array_buf.frombytes(self._i2b(len(pickled_data), 7))
                self.array_buf.frombytes(pickled_data)
        return 1

    def addfromfile(self, prefix_letter):
        """Read a chunk from the current file and add to array_buf

        prefix_letter and the length will be prepended to the file
        data.  If there is an exception while reading the file, the
        exception will be added to array_buf instead.

        """
        buf = robust.check_common_error(self.read_error_handler,
                                        self.currently_in_file.read,
                                        [Globals.blocksize])
        if buf is None:  # error occurred above, encode exception
            self.currently_in_file = None
            excstr = pickle.dumps(self.last_exception, 1)
            total = b"".join((b'e', self._i2b(len(excstr), 7), excstr))
        else:
            total = b"".join((prefix_letter, self._i2b(len(buf), 7), buf))
            if buf == b"":  # end of file
                cstr = pickle.dumps(self.currently_in_file.close(), 1)
                self.currently_in_file = None
                total += b"".join((b'h', self._i2b(len(cstr), 7), cstr))
        self.array_buf.frombytes(total)

    def read_error_handler(self, exc, blocksize):
        """Log error when reading from file"""
        self.last_exception = exc
        return None

    def _i2b(self, i, size=0):
        """Convert int to string using big endian byteorder"""
        if (size == 0):
            size = (i.bit_length() + 7) // 8
        return i.to_bytes(size, byteorder='big')

    def close(self):
        self.closed = 1


class MiscIterFlush:
    """Used to signal that a MiscIterToFile should flush buffer"""
    pass


class MiscIterFlushRepeat(MiscIterFlush):
    """Flush, but then cause Misc Iter to yield this same object

    Thus if we put together a pipeline of these, one MiscIterFlushRepeat
    can cause all the segments to flush in sequence.

    """
    pass


class MiscIterToFile(FileWrappingIter):
    """Take an iter and give it a file-ish interface

    This expands on the FileWrappingIter by understanding how to
    process RORPaths with file objects attached.  It adds a new
    character "r" to mark these.

    This is how we send signatures and diffs across the line.  As
    sending each one separately via a read() call would result in a
    lot of latency, the read()'s are buffered - a read() call with no
    arguments will return a variable length string (possibly empty).

    To flush the MiscIterToFile, have the iterator yield a
    MiscIterFlush class.

    """

    def __init__(self, rpiter, max_buffer_bytes=None, max_buffer_rps=None):
        """MiscIterToFile initializer

        max_buffer_bytes is the maximum size of the buffer in bytes.
        max_buffer_rps is the maximum size of the buffer in rorps.

        """
        self.max_buffer_bytes = max_buffer_bytes or Globals.conn_bufsize
        self.max_buffer_rps = max_buffer_rps or Globals.pipeline_max_length
        self.rorps_in_buffer = 0
        self.next_in_line = None
        FileWrappingIter.__init__(self, rpiter)

    def read(self, length=None):
        """Return some number of bytes, including 0"""
        assert not self.closed
        if length is None:
            while (len(self.array_buf) < self.max_buffer_bytes
                   and self.rorps_in_buffer < self.max_buffer_rps):
                if not self.addtobuffer():
                    break

            result = self.array_buf.tobytes()
            del self.array_buf[:]
            self.rorps_in_buffer = 0
            return result
        else:
            assert length >= 0
            read_buffer = self.read()
            while len(read_buffer) < length:
                read_buffer += self.read()
            self.array_buf.frombytes(read_buffer[length:])
            return read_buffer[length:]

    def addtobuffer(self):
        """Add some number of bytes to the buffer.  Return false if done"""
        if self.currently_in_file:
            self.addfromfile(b"c")
            if not self.currently_in_file:
                self.rorps_in_buffer += 1
        else:
            if self.next_in_line:
                currentobj = self.next_in_line
                self.next_in_line = 0
            else:
                try:
                    currentobj = next(self.iter)
                except StopIteration:
                    self.addfinal()
                    return None

            if hasattr(currentobj, "read") and hasattr(currentobj, "close"):
                self.currently_in_file = currentobj
                self.addfromfile(b"f")
            elif currentobj is MiscIterFlush:
                return None
            elif currentobj is MiscIterFlushRepeat:
                self.add_misc(currentobj)
                return None
            elif isinstance(currentobj, rpath.RORPath):
                self.addrorp(currentobj)
            else:
                self.add_misc(currentobj)
        return 1

    def add_misc(self, obj):
        """Add an arbitrary pickleable object to the buffer"""
        pickled_data = pickle.dumps(obj, 1)
        self.array_buf.frombytes(b"o")
        self.array_buf.frombytes(self._i2b(len(pickled_data), 7))
        self.array_buf.frombytes(pickled_data)

    def addrorp(self, rorp):
        """Add a rorp to the buffer"""
        if rorp.file:
            pickled_data = pickle.dumps((rorp.index, rorp.data, 1), 1)
            self.next_in_line = rorp.file
        else:
            pickled_data = pickle.dumps((rorp.index, rorp.data, 0), 1)
            self.rorps_in_buffer += 1
        self.array_buf.frombytes(b"r")
        self.array_buf.frombytes(self._i2b(len(pickled_data), 7))
        self.array_buf.frombytes(pickled_data)

    def addfinal(self):
        """Signal the end of the iterator to the other end"""
        self.array_buf.frombytes(b"z")
        self.array_buf.frombytes(self._i2b(0, 7))

    def close(self):
        self.closed = 1


class FileToMiscIter(IterWrappingFile):
    """Take a MiscIterToFile and turn it back into a iterator"""

    def __init__(self, file):
        IterWrappingFile.__init__(self, file)
        self.buf = b""

    def __iter__(self):
        return self

    def __next__(self):
        """Return next object in iter, or raise StopIteration"""
        if self.currently_in_file:
            self.currently_in_file.close()
        type = None
        while not type:
            type, data = self._get()
        if type == b"z":
            raise StopIteration
        elif type == b"r":
            return self.get_rorp(data)
        elif type == b"o":
            return data
        else:
            raise IterFileException("Bad file type %s" % (type, ))

    def get_rorp(self, pickled_tuple):
        """Return rorp that data represents"""
        index, data_dict, num_files = pickled_tuple
        rorp = rpath.RORPath(index, data_dict)
        if num_files:
            assert num_files == 1, "Only one file accepted right now"
            rorp.setfile(self.get_file())
        return rorp

    def get_file(self):
        """Read file object from file"""
        type, data = self._get()
        if type == b"f":
            return IterVirtualFile(self, data)
        assert type == b"e", "Expected type e, got %s" % (type, )
        assert isinstance(data, Exception)
        return ErrorFile(data)

    def _get(self):
        """Return (type, data or object) pair

        This is like UnwrapFile._get() but reads in variable length
        blocks.  Also type "z" is allowed, which means end of
        iterator.  An empty read() is not considered to mark the end
        of remote iter.

        """
        if not self.buf:
            self.buf += self.file.read()
        if not self.buf:
            return None, None

        assert len(self.buf) >= 8, "Unexpected end of MiscIter file"
        # [0:1] makes sure that the type remains a byte and not an int
        type, length = self.buf[0:1], self._b2i(self.buf[1:8])
        data = self.buf[8:8 + length]
        self.buf = self.buf[8 + length:]
        if type in b"oerh":
            return type, pickle.loads(data)
        else:
            return type, data


class ErrorFile:
    """File-like that just raises error (used by FileToMiscIter above)"""

    def __init__(self, exc):
        """Initialize new ErrorFile.  exc is the exception to raise on read"""
        self.exc = exc

    def read(self, lines=-1):
        raise self.exc

    def close(self):
        return None
