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
Store and retrieve metadata in destination directory

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
import binascii
from rdiff_backup import log, Globals, rpath
from rdiffbackup import meta
from rdiffbackup.utils import quoting


class AttrExtractor(meta.FlatExtractor):
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
            return tuple(quoting.unquote_path(quoted_filename).split(b'/'))

    @classmethod
    def _record_to_object(cls, record_string):
        """
        Given record_string, return RORPath

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
            elif field == "ResourceFork":  # pragma: no cover
                if data == b"None":
                    data_dict['resourcefork'] = b""
                else:
                    data_dict['resourcefork'] = binascii.unhexlify(data)
            elif field == "CarbonFile":  # pragma: no cover
                if data == b"None":
                    data_dict['carbonfile'] = None
                else:
                    data_dict['carbonfile'] = _string2carbonfile(data)
            elif field == "SymData":
                data_dict['linkname'] = quoting.unquote_path(data)
            elif field == "DeviceNum":
                devchar, major_str, minor_str = data.split(b" ")
                data_dict['devnums'] = (devchar.decode('ascii'), int(major_str),
                                        int(minor_str))
            elif field == "AlternateMirrorName":
                data_dict['mirrorname'] = data
            elif field == "AlternateIncrementName":
                data_dict['incname'] = data
            else:
                log.Log("Unknown field in line field/data '{uf}/{ud}'".format(
                    uf=field, ud=data), log.WARNING)
        return rpath.RORPath(index, data_dict)


class AttrFile(meta.FlatFile):
    """Store/retrieve metadata from mirror_metadata as rorps"""
    _name = "stdattr"
    _description = "Standard File Attributes"
    _prefix = b"mirror_metadata"
    _extractor = AttrExtractor
    _is_main = True

    @staticmethod
    def _object_to_record(rorpath):
        """From RORPath, return text record of file's metadata"""
        str_list = [b"File %s\n" % quoting.quote_path(rorpath.get_indexpath())]

        # Store file type, e.g. "dev", "reg", or "sym", and type-specific data
        type = rorpath.gettype()
        if type is None:
            type = "None"
        str_list.append(b"  Type %b\n" % type.encode('ascii'))
        if type == "reg":
            str_list.append(b"  Size %i\n" % rorpath.getsize())

            # If there is a resource fork, save it.
            if rorpath.has_resource_fork():  # pragma: no cover
                if not rorpath.get_resource_fork():
                    rf = b"None"
                else:
                    rf = binascii.hexlify(rorpath.get_resource_fork())
                str_list.append(b"  ResourceFork %b\n" % (rf, ))

            # If there is Carbon data, save it.
            if rorpath.has_carbonfile():  # pragma: no cover
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
            str_list.append(
                b"  SymData %b\n" % quoting.quote_path(rorpath.readlink()))
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


def _carbonfile2string(cfile):  # pragma: no cover
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
        log.Log("Writing pre-1.1.6 style metadata, without creation date",
                log.DEBUG)
    return '|'.join(retvalparts)


def _string2carbonfile(data):  # pragma: no cover
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


def get_plugin_class():
    return AttrFile
