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
"""Provides functions and *ITR classes, for writing increment files"""

import os
from rdiff_backup import Globals, log, Rdiff, robust, rpath, statistics, Time


def Increment(new, mirror, incpref, inc_time=None):
    """
    Main file incrementing function, returns inc file created

    new is the file on the active partition,
    mirror is the mirrored file from the last backup,
    incpref is the prefix of the increment file.

    This function basically moves the information about the mirror
    file to incpref, inc_time being the (previous) time of the mirror.
    """
    log.Log("Incrementing mirror file {mf}".format(mf=mirror), log.INFO)
    if ((new and new.isdir()) or mirror.isdir()) and not incpref.lstat():
        incpref.mkdir()

    if inc_time is None:  # compat200
        inc_time = Time.prevtime

    if not mirror.lstat():
        incrp = _make_missing_increment(incpref, inc_time)
    elif mirror.isdir():
        incrp = _make_dir_increment(mirror, incpref, inc_time)
    elif new.isreg() and mirror.isreg():
        incrp = _make_diff_increment(new, mirror, incpref, inc_time)
    else:
        incrp = _make_snapshot_increment(mirror, incpref, inc_time)
    statistics.process_increment(incrp)
    return incrp


def get_inc(rp, typestr, inc_time):
    """
    Return increment like rp but with time and typestr suffixes

    To avoid any quoting, the returned rpath has empty index, and the
    whole filename is in the base (which is not quoted).
    """
    if inc_time is None:  # compat200
        inc_time = Time.prevtime

    def addtostr(s):
        return b'.'.join(map(os.fsencode,
                             (s, Time.timetostring(inc_time), typestr)))

    if rp.index:
        incrp = rp.__class__(rp.conn, rp.base,
                             rp.index[:-1] + (addtostr(rp.index[-1]), ))
    else:
        dirname, basename = rp.dirsplit()
        incrp = rp.__class__(rp.conn, dirname, (addtostr(basename), ))
    if incrp.lstat():
        log.Log.FatalError(
            "New increment path '{ip}' shouldn't exist, something went "
            "really wrong.".format(ip=incrp))
    return incrp


# === Internal functions ===


def _make_missing_increment(incpref, inc_time):
    """Signify that mirror file was missing"""
    incrp = get_inc(incpref, "missing", inc_time)
    incrp.touch()
    return incrp


def _is_compressed(mirror):
    """Return true if mirror's increments should be compressed"""
    return (Globals.compression
            and not Globals.no_compression_regexp.match(mirror.path))


def _make_snapshot_increment(mirror, incpref, inc_time):
    """Copy mirror to incfile, since new is quite different"""
    compress = _is_compressed(mirror)
    if compress and mirror.isreg():
        snapshotrp = get_inc(incpref, b"snapshot.gz", inc_time)
    else:
        snapshotrp = get_inc(incpref, b"snapshot", inc_time)

    if mirror.isspecial():  # check for errors when creating special increments
        eh = robust.get_error_handler("SpecialFileError")
        if robust.check_common_error(eh, rpath.copy_with_attribs,
                                     (mirror, snapshotrp, compress)) == 0:
            snapshotrp.setdata()
            if snapshotrp.lstat():
                snapshotrp.delete()
            snapshotrp.touch()
    else:
        rpath.copy_with_attribs(mirror, snapshotrp, compress)
    return snapshotrp


def _make_diff_increment(new, mirror, incpref, inc_time):
    """Make incfile which is a diff new -> mirror"""
    compress = _is_compressed(mirror)
    if compress:
        diff = get_inc(incpref, b"diff.gz", inc_time)
    else:
        diff = get_inc(incpref, b"diff", inc_time)

    old_new_perms, old_mirror_perms = (None, None)

    if Globals.process_uid != 0:
        # Check for unreadable files
        if not new.readable():
            old_new_perms = new.getperms()
            new.chmod(0o400 | old_new_perms)
        if not mirror.readable():
            old_mirror_perms = mirror.getperms()
            mirror.chmod(0o400 | old_mirror_perms)

    Rdiff.write_delta(new, mirror, diff, compress)

    if old_new_perms:
        new.chmod(old_new_perms)
    if old_mirror_perms:
        mirror.chmod(old_mirror_perms)

    rpath.copy_attribs_inc(mirror, diff)
    return diff


def _make_dir_increment(mirrordir, incpref, inc_time):
    """Make file indicating directory mirrordir has changed"""
    dirsign = get_inc(incpref, "dir", inc_time)
    dirsign.touch()
    rpath.copy_attribs_inc(mirrordir, dirsign)
    return dirsign
