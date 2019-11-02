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
"""Provides functions and *ITR classes, for writing increment files"""

import os
from . import Globals, Time, rpath, Rdiff, log, statistics, robust


def Increment(new, mirror, incpref):
    """Main file incrementing function, returns inc file created

    new is the file on the active partition,
    mirror is the mirrored file from the last backup,
    incpref is the prefix of the increment file.

    This function basically moves the information about the mirror
    file to incpref.

    """
    log.Log("Incrementing mirror file %s" % mirror.get_safepath(), 5)
    if ((new and new.isdir()) or mirror.isdir()) and not incpref.lstat():
        incpref.mkdir()

    if not mirror.lstat():
        incrp = makemissing(incpref)
    elif mirror.isdir():
        incrp = makedir(mirror, incpref)
    elif new.isreg() and mirror.isreg():
        incrp = makediff(new, mirror, incpref)
    else:
        incrp = makesnapshot(mirror, incpref)
    statistics.process_increment(incrp)
    return incrp


def makemissing(incpref):
    """Signify that mirror file was missing"""
    incrp = get_inc(incpref, "missing")
    incrp.touch()
    return incrp


def iscompressed(mirror):
    """Return true if mirror's increments should be compressed"""
    return (Globals.compression
            and not Globals.no_compression_regexp.match(mirror.path))


def makesnapshot(mirror, incpref):
    """Copy mirror to incfile, since new is quite different"""
    compress = iscompressed(mirror)
    if compress and mirror.isreg():
        snapshotrp = get_inc(incpref, b"snapshot.gz")
    else:
        snapshotrp = get_inc(incpref, b"snapshot")

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


def makediff(new, mirror, incpref):
    """Make incfile which is a diff new -> mirror"""
    compress = iscompressed(mirror)
    if compress:
        diff = get_inc(incpref, b"diff.gz")
    else:
        diff = get_inc(incpref, b"diff")

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


def makedir(mirrordir, incpref):
    """Make file indicating directory mirrordir has changed"""
    dirsign = get_inc(incpref, "dir")
    dirsign.touch()
    rpath.copy_attribs_inc(mirrordir, dirsign)
    return dirsign


def get_inc(rp, typestr, time=None):
    """Return increment like rp but with time and typestr suffixes

    To avoid any quoting, the returned rpath has empty index, and the
    whole filename is in the base (which is not quoted).

    """
    if time is None:
        time = Time.prevtime

    def addtostr(s):
        return b'.'.join(map(os.fsencode, (s, Time.timetostring(time), typestr)))

    if rp.index:
        incrp = rp.__class__(rp.conn, rp.base,
                             rp.index[:-1] + (addtostr(rp.index[-1]), ))
    else:
        dirname, basename = rp.dirsplit()
        incrp = rp.__class__(rp.conn, dirname, (addtostr(basename), ))
    assert not incrp.lstat(), incrp
    return incrp
