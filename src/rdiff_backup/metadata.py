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
"""Store and retrieve metadata in destination directory

The plan is to store metadata information for all files in the
destination directory in a special metadata file.  There are two
reasons for this:

1)  The filesystem of the mirror directory may not be able to handle
    types of metadata that the source filesystem can.  For instance,
    rdiff-backup may not have root access on the destination side, so
    cannot set uid/gid.  Or the source side may have ACLs and the
    destination side doesn't.

    Hopefully every file system can store binary data.  Storing
    metadata separately allows us to back up anything (ok, maybe
    strange filenames are still a problem).

2)  Metadata can be more quickly read from a file than it can by
    traversing the mirror directory over and over again.  In many
    cases most of rdiff-backup's time is spent comparing metadata (like
    file size and modtime), trying to find differences.  Reading this
    data sequentially from a file is significantly less taxing than
    listing directories and statting files all over the mirror
    directory.

The metadata is stored in a text file, which is a bunch of records
concatenated together.  Each record has the format:

File <filename>
  <field_name1> <value>
  <field_name2> <value>
  ...

Where the lines are separated by newlines.  See the code below for the
field names and values.

"""

import re
import os
import binascii
from . import log, Globals, rpath, Time, rorpiter


_chars_to_quote = re.compile(b"\\n|\\\\")

ManagerObj = None  # Set this later to Manager instance


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
        """Translate filename, possibly quoted, into an index tuple

        The filename is the first group matched by
        regexp_boundary_regexp.

        """
        raise NotImplementedError()

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
                log.Log(
                    "Error parsing flat file: %s [%s(%s)]" %
                    (e, type(self), self.fileobj.fileobj.name), 2)

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
                log.Log("Error parsing metadata file: %s" % (e, ), 2)
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


class RorpExtractor(FlatExtractor):
    """Iterate rorps from metadata file"""
    record_boundary_regexp = re.compile(b"(?:\\n|^)(File (.*?))\\n")
    line_parsing_regexp = re.compile(b"^ *([A-Za-z0-9]+) (.+)$", re.M)

    # mapping for metadata fields to transform into integer
    _integer_mapping = {
        'Size': 'size',
        'NumHardLinks': 'nlink',
        'Inode': 'inode',
        'DeviceLoc': 'devloc',
        'ModTime': 'mtime',
        'Uid': 'uid',
        'Gid': 'gid',
        'Permissions': 'perms',
    }
    # mapping for metadata fields to transform into ascii strings
    _decode_mapping = {
        'Type': 'type',
        'SHA1Digest': 'sha1',
        'Uname': 'uname',
        'Gname': 'gname',
    }

    @staticmethod
    def _filename_to_index(quoted_filename):
        """Return tuple index given quoted filename"""
        if quoted_filename == b'.':
            return ()
        else:
            return tuple(unquote_path(quoted_filename).split(b'/'))

    @classmethod
    def _record_to_object(cls, record_string):
        """Given record_string, return RORPath

        For speed reasons, write the RORPath data dictionary directly
        instead of calling rorpath functions.  Profiling has shown this to
        be a time critical function.

        """
        data_dict = {}
        for field, data in cls.line_parsing_regexp.findall(record_string):
            field = field.decode('ascii')
            if field in cls._integer_mapping:
                data_dict[cls._integer_mapping[field]] = int(data)
            elif field in cls._decode_mapping:
                if data == b":" or data == b"None":
                    data_dict[cls._decode_mapping[field]] = None
                else:
                    data_dict[cls._decode_mapping[field]] = data.decode('ascii')
            elif field == "File":
                index = cls._filename_to_index(data)
            elif field == "ResourceFork":
                if data == b"None":
                    data_dict['resourcefork'] = b""
                else:
                    data_dict['resourcefork'] = binascii.unhexlify(data)
            elif field == "CarbonFile":
                if data == b"None":
                    data_dict['carbonfile'] = None
                else:
                    data_dict['carbonfile'] = _string2carbonfile(data)
            elif field == "SymData":
                data_dict['linkname'] = unquote_path(data)
            elif field == "DeviceNum":
                devchar, major_str, minor_str = data.split(b" ")
                data_dict['devnums'] = (devchar.decode('ascii'), int(major_str),
                                        int(minor_str))
            elif field == "AlternateMirrorName":
                data_dict['mirrorname'] = data
            elif field == "AlternateIncrementName":
                data_dict['incname'] = data
            else:
                log.Log("Unknown field in line '%s %s'" % (field, data), 2)
        return rpath.RORPath(index, data_dict)


class FlatFile:
    """Manage a flat file containing info on various files

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
    _prefix = None  # Set to required prefix

    def __init__(self, rp_base, mode, check_path=1, compress=1, callback=None):
        """Open rp (or rp+'.gz') for reading ('r') or writing ('w')

        If callback is available, it will be called on the rp upon
        closing (because the rp may not be known in advance).

        """
        self.mode = mode
        self.callback = callback
        self._record_buffer = []
        if check_path:
            if (rp_base.isincfile()
                    and rp_base.getincbase_bname() == self._prefix):
                compress = 1
            else:
                log.Log.FatalError(
                    "Checking the path '{rp!s}' went wrong.".format(rp=rp_base))
        if mode == 'r' or mode == 'rb':
            self.rp = rp_base
            self.fileobj = self.rp.open("rb", compress)
        elif mode == 'w' or mode == 'wb':
            if compress and check_path and not rp_base.isinccompressed():

                def callback(rp):
                    self.rp = rp

                self.fileobj = rpath.MaybeGzip(rp_base, callback)
            else:
                self.rp = rp_base
                assert not self.rp.lstat(), (
                    "Path '{rp!s}' can't exist before it's opened.".format(
                        rp=self.rp))
                self.fileobj = self.rp.open("wb", compress=compress)
        else:
            log.Log.FatalError(
                "File opening mode '{omode}' should have been one of "
                "r, rb, w or wb.".format(omode=mode))

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


class MetadataFile(FlatFile):
    """Store/retrieve metadata from mirror_metadata as rorps"""
    _prefix = b"mirror_metadata"
    _extractor = RorpExtractor

    @staticmethod
    def _object_to_record(rorpath):
        """From RORPath, return text record of file's metadata"""
        str_list = [b"File %s\n" % quote_path(rorpath.get_indexpath())]

        # Store file type, e.g. "dev", "reg", or "sym", and type-specific data
        type = rorpath.gettype()
        if type is None:
            type = "None"
        str_list.append(b"  Type %b\n" % type.encode('ascii'))
        if type == "reg":
            str_list.append(b"  Size %i\n" % rorpath.getsize())

            # If there is a resource fork, save it.
            if rorpath.has_resource_fork():
                if not rorpath.get_resource_fork():
                    rf = b"None"
                else:
                    rf = binascii.hexlify(rorpath.get_resource_fork())
                str_list.append(b"  ResourceFork %b\n" % (rf, ))

            # If there is Carbon data, save it.
            if rorpath.has_carbonfile():
                cfile = _carbonfile2string(rorpath.get_carbonfile())
                str_list.append(b"  CarbonFile %b\n" % (cfile, ))

            # If file is hardlinked, add that information
            if Globals.preserve_hardlinks != 0:
                numlinks = rorpath.getnumlinks()
                if numlinks > 1:
                    str_list.append(b"  NumHardLinks %i\n" % numlinks)
                    str_list.append(b"  Inode %i\n" % rorpath.getinode())
                    str_list.append(b"  DeviceLoc %i\n" % rorpath.getdevloc())

            # Save any hashes, if available
            if rorpath.has_sha1():
                str_list.append(
                    b'  SHA1Digest %b\n' % rorpath.get_sha1().encode('ascii'))

        elif type == "None":
            return b"".join(str_list)
        elif type == "dir" or type == "sock" or type == "fifo":
            pass
        elif type == "sym":
            str_list.append(b"  SymData %b\n" % quote_path(rorpath.readlink()))
        elif type == "dev":
            devchar, major, minor = rorpath.getdevnums()
            str_list.append(
                b"  DeviceNum %b %i %i\n" % (devchar.encode('ascii'), major, minor))

        # Store time information
        if type != 'sym' and type != 'dev':
            str_list.append(b"  ModTime %i\n" % rorpath.getmtime())

        # Add user, group, and permission information
        uid, gid = rorpath.getuidgid()
        str_list.append(b"  Uid %i\n" % uid)
        str_list.append(b"  Uname %b\n" % (rorpath.getuname() or ":").encode())
        str_list.append(b"  Gid %i\n" % gid)
        str_list.append(b"  Gname %b\n" % (rorpath.getgname() or ":").encode())
        str_list.append(b"  Permissions %d\n" % rorpath.getperms())

        # Add long filename information
        if rorpath.has_alt_mirror_name():
            str_list.append(
                b"  AlternateMirrorName %b\n" % (rorpath.get_alt_mirror_name(), ))
        elif rorpath.has_alt_inc_name():
            str_list.append(
                b"  AlternateIncrementName %b\n" % (rorpath.get_alt_inc_name(), ))

        return b"".join(str_list)


class CombinedWriter:
    """Used for simultaneously writing metadata, eas, and acls"""

    def __init__(self, metawriter, eawriter, aclwriter, winaclwriter):
        self.metawriter = metawriter
        self.eawriter, self.aclwriter, self.winaclwriter = \
            eawriter, aclwriter, winaclwriter  # these can be None

    def write_object(self, rorp):
        """Write information in rorp to all the writers"""
        self.metawriter.write_object(rorp)
        if self.eawriter and not rorp.get_ea().is_empty():
            self.eawriter.write_object(rorp.get_ea())
        if self.aclwriter and not rorp.get_acl().is_basic():
            self.aclwriter.write_object(rorp.get_acl())
        if self.winaclwriter:
            self.winaclwriter.write_object(rorp.get_win_acl())

    def close(self):
        self.metawriter.close()
        if self.eawriter:
            self.eawriter.close()
        if self.aclwriter:
            self.aclwriter.close()
        if self.winaclwriter:
            self.winaclwriter.close()


class Manager:
    """Read/Combine/Write metadata files by time"""
    meta_prefix = b'mirror_metadata'
    acl_prefix = b'access_control_lists'
    ea_prefix = b'extended_attributes'
    wacl_prefix = b'win_access_control_lists'

    def __init__(self):
        """Set listing of rdiff-backup-data dir"""
        self.rplist = []
        self.timerpmap, self.prefixmap = {}, {}
        for filename in Globals.rbdir.listdir():
            rp = Globals.rbdir.append(filename)
            if rp.isincfile():
                self._add_incrp(rp)

    def get_meta_at_time(self, time, restrict_index):
        """Return iter of metadata rorps at given time (or None)"""
        return self._iter_helper(self.meta_prefix, MetadataFile, time,
                                 restrict_index)

    def GetAtTime(self, time, restrict_index=None):
        """Return combined metadata iter with ea/acl info if necessary"""
        cur_iter = self.get_meta_at_time(time, restrict_index)
        if not cur_iter:
            log.Log(
                "Warning, could not find mirror_metadata file.\n"
                "Metadata will be read from filesystem instead.", 2)
            return None

        if Globals.acls_active:
            acl_iter = self._get_acls_at_time(time, restrict_index)
            if not acl_iter:
                log.Log("Warning: Access Control List file not found", 2)
                acl_iter = iter([])
            cur_iter = eas_acls.join_acl_iter(cur_iter, acl_iter)
        if Globals.eas_active:
            ea_iter = self._get_eas_at_time(time, restrict_index)
            if not ea_iter:
                log.Log("Warning: Extended Attributes file not found", 2)
                ea_iter = iter([])
            cur_iter = eas_acls.join_ea_iter(cur_iter, ea_iter)
        if Globals.win_acls_active:
            wacl_iter = self._get_win_acls_at_time(time, restrict_index)
            if not wacl_iter:
                log.Log(
                    "Warning: Windows Access Control List file not"
                    " found.", 2)
                wacl_iter = iter([])
            cur_iter = win_acls.join_wacl_iter(cur_iter, wacl_iter)

        return cur_iter

    def GetWriter(self, typestr=b'snapshot', time=None):
        """Get a writer object that can write meta and possibly acls/eas"""
        metawriter = self._get_meta_writer(typestr, time)
        if not Globals.eas_active and not Globals.acls_active and \
           not Globals.win_acls_active:
            return metawriter  # no need for a CombinedWriter

        if Globals.eas_active:
            ea_writer = self._get_ea_writer(typestr, time)
        else:
            ea_writer = None
        if Globals.acls_active:
            acl_writer = self._get_acl_writer(typestr, time)
        else:
            acl_writer = None
        if Globals.win_acls_active:
            win_acl_writer = self._get_win_acl_writer(typestr, time)
        else:
            win_acl_writer = None
        return CombinedWriter(metawriter, ea_writer, acl_writer,
                              win_acl_writer)

    def _add_incrp(self, rp):
        """Add rp to list of inc rps in the rbdir"""
        assert rp.isincfile(), (
            "Path '{irp!s}' must be an increment file.".format(irp=rp))
        self.rplist.append(rp)
        time = rp.getinctime()
        if time in self.timerpmap:
            self.timerpmap[time].append(rp)
        else:
            self.timerpmap[time] = [rp]

        incbase = rp.getincbase_bname()
        if incbase in self.prefixmap:
            self.prefixmap[incbase].append(rp)
        else:
            self.prefixmap[incbase] = [rp]

    def _iter_helper(self, prefix, flatfileclass, time, restrict_index):
        """Used below to find the right kind of file by time"""
        if time not in self.timerpmap:
            return None
        for rp in self.timerpmap[time]:
            if rp.getincbase_bname() == prefix:
                return flatfileclass(rp, 'r').get_objects(restrict_index)
        return None

    def _get_eas_at_time(self, time, restrict_index):
        """Return Extended Attributes iter at given time (or None)"""
        return self._iter_helper(self.ea_prefix,
                                 eas_acls.ExtendedAttributesFile, time,
                                 restrict_index)

    def _get_acls_at_time(self, time, restrict_index):
        """Return ACLs iter at given time from recordfile (or None)"""
        return self._iter_helper(self.acl_prefix,
                                 eas_acls.AccessControlListFile, time,
                                 restrict_index)

    def _get_win_acls_at_time(self, time, restrict_index):
        """Return WACLs iter at given time from recordfile (or None)"""
        return self._iter_helper(self.wacl_prefix,
                                 win_acls.WinAccessControlListFile, time,
                                 restrict_index)

    def _get_meta_writer(self, typestr, time):
        """Return MetadataFile object opened for writing at given time"""
        return self._writer_helper(self.meta_prefix, MetadataFile, typestr,
                                   time)

    def _get_ea_writer(self, typestr, time):
        """Return ExtendedAttributesFile opened for writing"""
        return self._writer_helper(
            self.ea_prefix, eas_acls.ExtendedAttributesFile, typestr, time)

    def _get_acl_writer(self, typestr, time):
        """Return AccessControlListFile opened for writing"""
        return self._writer_helper(
            self.acl_prefix, eas_acls.AccessControlListFile, typestr, time)

    def _get_win_acl_writer(self, typestr, time):
        """Return WinAccessControlListFile opened for writing"""
        return self._writer_helper(
            self.wacl_prefix, win_acls.WinAccessControlListFile, typestr, time)

    def _writer_helper(self, prefix, flatfileclass, typestr, time):
        """Used in the get_xx_writer functions, returns a writer class"""
        if time is None:
            timestr = Time.curtimestr
        else:
            timestr = Time.timetobytes(time)
        triple = map(os.fsencode, (prefix, timestr, typestr))
        filename = b'.'.join(triple)
        rp = Globals.rbdir.append(filename)
        assert not rp.lstat(), "File '{rp!s}' shouldn't exist.".format(rp=rp)
        assert rp.isincfile(), (
            "Path '{irp!s}' must be an increment file.".format(irp=rp))
        return flatfileclass(rp, 'w', callback=self._add_incrp)


class PatchDiffMan(Manager):
    """Contains functions for patching and diffing metadata

    To save space, we can record a full list of only the most recent
    metadata, using the normal rdiff-backup reverse increment
    strategy.  Instead of using librsync to compute diffs, though, we
    use our own technique so that the diff files are still
    hand-editable.

    A mirror_metadata diff has the same format as a mirror_metadata
    snapshot.  If the record for an index is missing from the diff, it
    indicates no change from the original.  If it is present it
    replaces the mirror_metadata entry, unless it has Type None, which
    indicates the record should be deleted from the original.

    """
    max_diff_chain = 9  # After this many diffs, make a new snapshot

    def _get_diffiter(self, new_iter, old_iter):
        """Iterate meta diffs of new_iter -> old_iter"""
        for new_rorp, old_rorp in rorpiter.Collate2Iters(new_iter, old_iter):
            if not old_rorp:
                yield rpath.RORPath(new_rorp.index)
            elif not new_rorp or new_rorp.data != old_rorp.data:
                # exact compare here, can't use == on rorps
                yield old_rorp

    def sorted_prefix_inclist(self, prefix, min_time=0):
        """Return reverse sorted (by time) list of incs with given prefix"""
        if prefix not in self.prefixmap:
            return []
        sortlist = [(rp.getinctime(), rp) for rp in self.prefixmap[prefix]]

        # we sort before we validate against duplicates so that we tell
        # first about the youngest case of duplication
        sortlist.sort(reverse=True, key=lambda x: x[0])

        # we had cases where the timestamp of the metadata files were
        # duplicates, we need to fail or at least warn about such cases
        unique_set = set()
        for (time, rp) in sortlist:
            if time in unique_set:
                if Globals.allow_duplicate_timestamps:
                    log.Log("Warning: metadata file '%s' has a duplicate "
                            "timestamp date, you might not be able to "
                            "recover files on or earlier than this date. "
                            "Assuming you're in the process of cleaning up "
                            "your repository." %
                            rp.get_safepath(), 2)
                else:
                    log.Log.FatalError(
                        "Metadata file '%s' has a duplicate timestamp date, "
                        "you might not be able to recover files on or earlier "
                        "than this date. "
                        "Check the man page on how to clean up your repository "
                        "using the '--allow-duplicate-timestamps' option." %
                        rp.get_safepath())
            else:
                unique_set.add(time)

        return [rp for (time, rp) in sortlist if time >= min_time]

    def _check_needs_diff(self):
        """Check if we should diff, returns (new, old) rps, or (None, None)"""
        inclist = self.sorted_prefix_inclist(b'mirror_metadata')
        assert len(inclist) >= 1, (
            "There must be a least one element in '{ilist}'.".format(
                ilist=inclist))
        if len(inclist) == 1:
            return (None, None)
        newrp, oldrp = inclist[:2]
        assert newrp.getinctype() == oldrp.getinctype() == b'snapshot', (
            "New '{nrp!s}' and old '{orp!s}' paths must be of "
            "type 'snapshot'.".format(nrp=newrp, orp=oldrp))

        chainlen = 1
        for rp in inclist[2:]:
            if rp.getinctype() != b'diff':
                break
            chainlen += 1
        if chainlen >= self.max_diff_chain:
            return (None, None)
        return (newrp, oldrp)

    def ConvertMetaToDiff(self):
        """Replace a mirror snapshot with a diff if it's appropriate"""
        newrp, oldrp = self._check_needs_diff()
        if not newrp:
            return
        log.Log("Writing mirror_metadata diff", 6)

        diff_writer = self._get_meta_writer(b'diff', oldrp.getinctime())
        new_iter = MetadataFile(newrp, 'r').get_objects()
        old_iter = MetadataFile(oldrp, 'r').get_objects()
        for diff_rorp in self._get_diffiter(new_iter, old_iter):
            diff_writer.write_object(diff_rorp)
        diff_writer.close()  # includes sync
        oldrp.delete()

    def get_meta_at_time(self, time, restrict_index):
        """Get metadata rorp iter, possibly by patching with diffs"""
        meta_iters = [
            MetadataFile(rp, 'r').get_objects(restrict_index)
            for rp in self._relevant_meta_incs(time)
        ]
        if not meta_iters:
            return None
        if len(meta_iters) == 1:
            return meta_iters[0]
        return self._iterate_patched_meta(meta_iters)

    def _relevant_meta_incs(self, time):
        """Return list [snapshotrp, diffrps ...] time sorted"""
        inclist = self.sorted_prefix_inclist(b'mirror_metadata', min_time=time)
        if not inclist:
            return inclist
        assert inclist[-1].getinctime() == time, (
            "The time of the last increment '{itime}' must be equal to "
            "the given time '{time}'.".format(itime=inclist[-1].getinctime(),
                                              time=time))
        for i in range(len(inclist) - 1, -1, -1):
            if inclist[i].getinctype() == b'snapshot':
                return inclist[i:]
        else:
            log.Log.FatalError(
                "Increments list '{ilist}' contains no snapshots".format(
                    ilist=inclist))

    def _iterate_patched_meta(self, meta_iter_list):
        """Return an iter of metadata rorps by combining the given iters

        The iters should be given as a list/tuple in reverse
        chronological order.  The earliest rorp in each iter will
        supercede all the later ones.

        """
        for meta_tuple in rorpiter.CollateIterators(*meta_iter_list):
            for i in range(len(meta_tuple) - 1, -1, -1):
                if meta_tuple[i]:
                    if meta_tuple[i].lstat():
                        yield meta_tuple[i]
                    break  # move to next index
            else:
                log.Log.FatalError("No valid metadata tuple in list")


def quote_path(path_string):
    """Return quoted version of path_string

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
            log.Log.FatalError(
                "Bad char '{char}' shouldn't need quoting.".format(char=char))

    return _chars_to_quote.sub(replacement_func, path_string)


def unquote_path(quoted_string):
    """Reverse what was done by quote_path"""

    def replacement_func(match_obj):
        """Unquote match obj of two character sequence"""
        two_chars = match_obj.group(0)
        if two_chars == b"\\n":
            return b"\n"
        elif two_chars == b"\\\\":
            return b"\\"
        log.Log("Warning, unknown quoted sequence %s found" % two_chars, 2)
        return two_chars

    return re.sub(b"\\\\n|\\\\\\\\", replacement_func, quoted_string)


def SetManager():
    global ManagerObj
    ManagerObj = PatchDiffMan()
    return ManagerObj


def _carbonfile2string(cfile):
    """Convert CarbonFile data to a string suitable for storing."""
    if not cfile:
        return "None"
    retvalparts = []
    retvalparts.append('creator:%s' % binascii.hexlify(cfile['creator']))
    retvalparts.append('type:%s' % binascii.hexlify(cfile['type']))
    retvalparts.append('location:%d,%d' % cfile['location'])
    retvalparts.append('flags:%d' % cfile['flags'])
    try:
        retvalparts.append('createDate:%d' % cfile['createDate'])
    except KeyError:
        log.Log("Writing pre-1.1.6 style metadata, without creation date", 9)
    return '|'.join(retvalparts)


def _string2carbonfile(data):
    """Re-constitute CarbonFile data from a string stored by
    _carbonfile2string."""
    retval = {}
    for component in data.split('|'):
        key, value = component.split(':')
        if key == 'creator':
            retval['creator'] = binascii.unhexlify(value)
        elif key == 'type':
            retval['type'] = binascii.unhexlify(value)
        elif key == 'location':
            a, b = value.split(',')
            retval['location'] = (int(a), int(b))
        elif key == 'flags':
            retval['flags'] = int(value)
        elif key == 'createDate':
            retval['createDate'] = int(value)
    return retval


from . import eas_acls, win_acls  # noqa: E402
