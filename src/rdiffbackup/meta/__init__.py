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
Base module for any metadata class to derive from.
"""

from rdiff_backup import log


class ParsingError(Exception):
    """This is raised when bad or unparsable data is received"""
    pass


class FlatExtractor:
    """Controls iterating objects from flat file"""

    # Set this in subclass.  record_boundary_regexp should match
    # beginning of next record.  The first group should start at the
    # beginning of the record.  The second group should contain the
    # (possibly quoted) filename.
    record_boundary_regexp = None

    # Set in subclass to function that converts text record to object
    _record_to_object = None

    @staticmethod
    def _filename_to_index(filename):
        """
        Translate filename, possibly quoted, into an index tuple

        The filename is the first group matched by
        regexp_boundary_regexp.
        """
        raise NotImplementedError(__class__ + '._filename_to_index')

    def __init__(self, fileobj):
        self.fileobj = fileobj  # holds file object we are reading from
        self.buf = b""  # holds the next part of the file
        self.at_end = 0  # True if we are at the end of the file
        self.blocksize = 32 * 1024

    def iterate(self):
        """Return iterator that yields all objects with records"""
        for record in self._iterate_records():
            try:
                yield self._record_to_object(record)
            except (ParsingError, ValueError) as e:
                if self.at_end:
                    break  # Ignore whitespace/bad records at end
                log.Log("Error parsing flat file {ff} of type {ty} due to "
                        "exception '{ex}', metadata record ignored".format(
                            ex=e, ty=type(self),
                            ff=self.fileobj.fileobj.name), log.WARNING)

    def _iterate_records(self):
        """Yield all text records in order"""
        while 1:
            next_pos = self._get_next_pos()
            if self.at_end:
                if next_pos:
                    yield self.buf[:next_pos]
                break
            yield self.buf[:next_pos]
            self.buf = self.buf[next_pos:]
        self.fileobj.close()

    def _iterate_starting_with(self, index):
        """Iterate objects whose index starts with given index"""
        self._skip_to_index(index)
        if self.at_end:
            return
        while 1:
            next_pos = self._get_next_pos()
            try:
                obj = self._record_to_object(self.buf[:next_pos])
            except (ParsingError, ValueError) as e:
                log.Log("Error parsing metadata file at given index {gi} due "
                        "to exception '{ex}'".format(ex=e, gi=index),
                        log.WARNING)
            else:
                if obj.index[:len(index)] != index:
                    break
                yield obj
            if self.at_end:
                break
            self.buf = self.buf[next_pos:]
        self.fileobj.close()

    def _skip_to_index(self, index):
        """Scan through the file, set buffer to beginning of index record

        Here we make sure that the buffer always ends in a newline, so
        we will not be splitting lines in half.

        """
        assert not self.buf or self.buf.endswith(b"\n"), (
            "Something is wrong with buffer '{buf}'.".format(buf=self.buf))
        while 1:
            self.buf = self.fileobj.read(self.blocksize)
            self.buf += self.fileobj.readline()
            if not self.buf:
                self.at_end = 1
                return
            while 1:
                m = self.record_boundary_regexp.search(self.buf)
                if not m:
                    break
                cur_index = self._filename_to_index(m.group(2))
                if cur_index >= index:
                    self.buf = self.buf[m.start(1):]
                    return
                else:
                    self.buf = self.buf[m.end(1):]

    def _get_next_pos(self):
        """Return position of next record in buffer, or end pos if none"""
        while 1:
            m = self.record_boundary_regexp.search(self.buf, 1)
            if m:
                return m.start(1)
            else:  # add next block to the buffer, loop again
                newbuf = self.fileobj.read(self.blocksize)
                if not newbuf:
                    self.at_end = 1
                    return len(self.buf)
                else:
                    self.buf += newbuf


class FlatFile:
    """
    Manage a flat file containing info on various files

    This is used for metadata information, and possibly EAs and ACLs.
    The main read interface is as an iterator.  The storage format is
    a flat, probably compressed file, so random access is not
    recommended.

    Even if the file looks like a text file, it is actually a binary file,
    so that (especially) paths can be stored as bytes, without issue
    with encoding / decoding.
    """
    rp, fileobj, mode = None, None, None
    _buffering_on = 1  # Buffering may be useful because gzip writes are slow
    _record_buffer, _max_buffer_size = None, 100
    _extractor = FlatExtractor  # Override to class that iterates objects
    _object_to_record = None  # Set to function converting object to record
    _name = None  # simple name to be used as dictionary key
    _description = None  # human readable name of the metadata type
    _prefix = None  # Set to required prefix
    _is_main = None  # is the metadata object carrying a RORP? Only one allowed
    _version = "0.0.0"

    @classmethod
    def get_name(cls):
        return cls._name

    @classmethod
    def get_desc(cls):
        return cls._description

    @classmethod
    def get_prefix(cls):
        return cls._prefix

    @classmethod
    def get_version(cls):
        return cls._version

    @classmethod
    def is_active(cls):
        """
        Is the metadata active?

        The main metadata is _always_ active, else overwrite in children class.
        """
        return cls._is_main

    @classmethod
    def is_main_meta(cls):
        """
        Returns a boolean defining if the meta class is the "main" one.

        A main metadata class is defined as the class holding/producing the
        original RORpath object. To be honest, it is a workaround because the
        structure foresees it, else all metadata classes should be more
        equivalent.

        Note that only one class can be the main one, else the behaviour is
        undefined.
        """
        return cls._is_main

    def __init__(self, rp_base, mode, check_path=1,
                 compress=None, callback=None):
        """
        Open rp (or rp+'.gz') for reading ('r') or writing ('w')

        If callback is available, it will be called on the rp upon
        closing (because the rp may not be known in advance).
        """
        self.mode = mode
        self.callback = callback
        self._record_buffer = []
        if check_path:
            if not (rp_base.isincfile()
                    and rp_base.getincbase_bname() == self._prefix):
                log.Log.FatalError(
                    "Checking the path '{pa}' went wrong.".format(pa=rp_base))
        if mode == 'r' or mode == 'rb':
            self.rp = rp_base
            if compress is None:
                if self.rp.isinccompressed():
                    compress = True
                else:
                    compress = False
            self.fileobj = self.rp.open("rb", compress)
        elif mode == 'w' or mode == 'wb':
            if compress and check_path and not rp_base.isinccompressed():

                def callback(rp):
                    self.rp = rp

                from rdiff_backup import rpath  # to avoid a circular dependency
                self.fileobj = rpath.MaybeGzip(rp_base, callback)
            else:
                self.rp = rp_base
                assert not self.rp.lstat(), (
                    "Path '{rp}' can't exist before it's opened.".format(
                        rp=self.rp))
                self.fileobj = self.rp.open("wb", compress=compress)
        else:
            log.Log.FatalError(
                "File opening mode '{om}' should have been one of "
                "r, rb, w or wb".format(om=mode))

    def write_object(self, object):
        """Convert one object to record and write to file"""
        self._write_record(self._object_to_record(object))

    def get_objects(self, restrict_index=None):
        """Return iterator of objects records from file rp"""
        if not restrict_index:
            return self._extractor(self.fileobj).iterate()
        extractor = self._extractor(self.fileobj)
        return extractor._iterate_starting_with(restrict_index)

    def close(self):
        """Close file, for when any writing is done"""
        assert self.fileobj, "Can't close file already closed."
        if self._buffering_on and self._record_buffer:
            self.fileobj.write(b"".join(self._record_buffer))
            self._record_buffer = []
        result = self.fileobj.close()
        self.fileobj = None
        self.rp.fsync_with_dir()
        self.rp.setdata()
        if self.callback:
            self.callback(self.rp)
        return result

    def _write_record(self, record):
        """Write a (text) record into the file"""
        if self._buffering_on:
            self._record_buffer.append(record)
            if len(self._record_buffer) >= self._max_buffer_size:
                self.fileobj.write(b"".join(self._record_buffer))
                self._record_buffer = []
        else:
            self.fileobj.write(record)
