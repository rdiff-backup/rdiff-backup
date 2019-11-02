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
"""list, delete, and otherwise manage increments"""

import os
from .log import Log
from . import Globals, Time, statistics, restore, selection, FilenameMapping


class ManageException(Exception):
    pass


def get_file_type(rp):
    """Returns one of "regular", "directory", "missing", or "special"."""
    if not rp.lstat():
        return "missing"
    elif rp.isdir():
        return "directory"
    elif rp.isreg():
        return "regular"
    else:
        return "special"


def get_inc_type(inc):
    """Return file type increment represents"""
    assert inc.isincfile()
    type = inc.getinctype()
    if type == b"dir":
        return "directory"
    elif type == b"diff":
        return "regular"
    elif type == b"missing":
        return "missing"
    elif type == b"snapshot":
        return get_file_type(inc)
    else:
        assert None, "Unknown type %s" % type


def describe_incs_parsable(incs, mirror_time, mirrorrp):
    """Return a string parsable by computer describing the increments

    Each line is a time in seconds of the increment, and then the
    type of the file.  It will be sorted oldest to newest.  For example:

    10000 regular
    20000 directory
    30000 special
    40000 missing
    50000 regular    <- last will be the current mirror

    """
    incpairs = [(inc.getinctime(), inc) for inc in incs]
    incpairs.sort()
    result = ["%s %s" % (time, get_inc_type(inc)) for time, inc in incpairs]
    result.append("%s %s" % (mirror_time, get_file_type(mirrorrp)))
    return "\n".join(result)


def describe_incs_human(incs, mirror_time, mirrorrp):
    """Return a string describing all the the root increments"""
    incpairs = [(inc.getinctime(), inc) for inc in incs]
    incpairs.sort()

    result = ["Found %d increments:" % len(incpairs)]
    if Globals.chars_to_quote:
        for time, inc in incpairs:
            result.append("    %s   %s" % (
                os.fsdecode(FilenameMapping.unquote(inc.dirsplit()[1])),
                Time.timetopretty(time)))
    else:
        for time, inc in incpairs:
            result.append("    %s   %s" % (
                os.fsdecode(inc.dirsplit()[1]),
                Time.timetopretty(time)))
    result.append("Current mirror: %s" % Time.timetopretty(mirror_time))
    return "\n".join(result)


def delete_earlier_than(baserp, time):
    """Deleting increments older than time in directory baserp

    time is in seconds.  It will then delete any empty directories
    in the tree.  To process the entire backup area, the
    rdiff-backup-data directory should be the root of the tree.

    """
    baserp.conn.manage.delete_earlier_than_local(baserp, time)


def delete_earlier_than_local(baserp, time):
    """Like delete_earlier_than, but run on local connection for speed"""
    assert baserp.conn is Globals.local_connection

    def yield_files(rp):
        if rp.isdir():
            for filename in rp.listdir():
                for sub_rp in yield_files(rp.append(filename)):
                    yield sub_rp
        yield rp

    for rp in yield_files(baserp):
        if ((rp.isincfile() and rp.getinctime() < time)
                or (rp.isdir() and not rp.listdir())):
            Log("Deleting increment file %s" % rp.get_safepath(), 5)
            rp.delete()


class IncObj:
    """Increment object - represent a completed increment"""

    def __init__(self, incrp):
        """IncObj initializer

        incrp is an RPath of a path like increments.TIMESTR.dir
        standing for the root of the increment.

        """
        if not incrp.isincfile():
            raise ManageException(
                "%s is not an inc file" % incrp.get_safepath())
        self.incrp = incrp
        self.time = incrp.getinctime()

    def getbaserp(self):
        """Return rp of the incrp without extensions"""
        return self.incrp.getincbase()

    def pretty_time(self):
        """Return a formatted version of inc's time"""
        return Time.timetopretty(self.time)


def ListIncrementSizes(mirror_root, index):
    """Return string summarizing the size of all the increments"""
    stat_obj = statistics.StatsObj()  # used for byte summary string

    def get_total(rp_iter):
        """Return the total size of everything in rp_iter"""
        total = 0
        for rp in rp_iter:
            total += rp.getsize()
        return total

    def get_time_dict(inc_iter):
        """Return dictionary pairing times to total size of incs"""
        time_dict = {}
        for inc in inc_iter:
            if not inc.isincfile():
                continue
            t = inc.getinctime()
            if t not in time_dict:
                time_dict[t] = 0
            time_dict[t] += inc.getsize()
        return time_dict

    def get_mirror_select():
        """Return iterator of mirror rpaths"""
        mirror_base = mirror_root.new_index(index)
        mirror_select = selection.Select(mirror_base)
        if not index:  # must exclude rdiff-backup-directory
            mirror_select.parse_rbdir_exclude()
        return mirror_select.set_iter()

    def get_inc_select():
        """Return iterator of increment rpaths"""
        inc_base = Globals.rbdir.append_path(b'increments', index)
        for base_inc in restore.get_inclist(inc_base):
            yield base_inc
        if inc_base.isdir():
            inc_select = selection.Select(inc_base).set_iter()
            for inc in inc_select:
                yield inc

    def get_summary_triples(mirror_total, time_dict):
        """Return list of triples (time, size, cumulative size)"""
        triples = []

        cur_mir_base = Globals.rbdir.append(b'current_mirror')
        mirror_time = restore.get_inclist(cur_mir_base)[0].getinctime()
        triples.append((mirror_time, mirror_total, mirror_total))

        inc_times = list(time_dict.keys())
        inc_times.sort()
        inc_times.reverse()
        cumulative_size = mirror_total
        for inc_time in inc_times:
            size = time_dict[inc_time]
            cumulative_size += size
            triples.append((inc_time, size, cumulative_size))
        return triples

    def triple_to_line(triple):
        """Convert triple to display string"""
        time, size, cum_size = triple
        return "%24s   %13s   %15s" % \
            (Time.timetopretty(time),
             stat_obj.get_byte_summary_string(size),
             stat_obj.get_byte_summary_string(cum_size))

    mirror_total = get_total(get_mirror_select())
    time_dict = get_time_dict(get_inc_select())
    triples = get_summary_triples(mirror_total, time_dict)

    sizes = [
        '%12s %9s  %15s   %20s' % ('Time', '', 'Size', 'Cumulative size'),
        '-' * 77,
        triple_to_line(triples[0]) + '   (current mirror)'
    ]
    for triple in triples[1:]:
        sizes.append(triple_to_line(triple))
    return '\n'.join(sizes)
