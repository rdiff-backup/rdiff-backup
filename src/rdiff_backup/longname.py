# DEPRECATED compat200
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
"""Handle long filenames

rdiff-backup sometimes wants to write filenames longer than allowed by
the destination directory.  This can happen in 3 ways:

1)  Because the destination directory has a low maximum length limit.
2)  When the source directory has a filename close to the limit, so
    that its increments would be above the limit.
3)  When quoting is enabled, so that even the mirror filenames are too
    long.

When rdiff-backup would otherwise write a file whose name is too long,
instead it either skips the operation altogether (for non-regular
files), or writes the data to a unique file in the
rdiff-backup-data/long-filename directory.  This file will have an
arbitrary basename, but if it's an increment the suffix will be the
same.  The name will be recorded in the mirror_metadata so we can find
it later.

"""

import errno
from rdiff_backup import Globals, log
from rdiffbackup.utils import safestr

_long_name_dir = b"long_filename_data"
_long_name_rootrp = None

# integer number of next free prefix.  Names will be created from
# integers consecutively like '1', '2', and so on.
_free_name_counter = None

# Filename which holds the next available free name in it
_counter_filename = b"next_free"

# This holds a dictionary {incbase: inclist}.  The keys are increment
# bases like '1' or '23', and the values are lists containing the
# associated increments.
_restore_inc_cache = None


# ------------------------------------------------------------------
# The following section is for backup
# ------------------------------------------------------------------


def get_mirror_rp(mirror_base, mirror_rorp):
    """Get the mirror_rp for reading a regular file

    This will just be in the mirror_base, unless rorp has an alt
    mirror name specified.  Use new_rorp, unless it is None or empty,
    and mirror_rorp exists.

    """
    if mirror_rorp.has_alt_mirror_name():
        return _get_long_rp(mirror_rorp.get_alt_mirror_name())
    else:
        rp = _check_new_index(mirror_base, mirror_rorp.index)
        if rp:
            return rp
        else:
            raise Exception("the following line doesn't make any sense but does it matter?")
            # FIXME index isn't defined anywhere, is mirror_rorp.index meant?
            # return mirror_base.new_index_empty(index)


def get_mirror_inc_rps(rorp_pair, mirror_root, inc_root=None):
    """Get (mirror_rp, inc_rp) pair, possibly making new longname base

    To test inc_rp, pad incbase with 50 random (non-quoted) characters
    and see if that raises an error.

    """
    if not inc_root:  # make fake inc_root if not available
        inc_root = mirror_root.append_path(b'rdiff-backup-data/increments')

    def mir_triple_old(old_rorp):
        """Return (mirror_rp, alt_mirror, alt_inc) from old_rorp"""
        if old_rorp.has_alt_mirror_name():
            alt_mirror = old_rorp.get_alt_mirror_name()
            return (_get_long_rp(alt_mirror), alt_mirror, None)
        else:
            mirror_rp = mirror_root.new_index(old_rorp.index)
            if old_rorp.has_alt_inc_name():
                return (mirror_rp, None, old_rorp.get_alt_inc_name())
            else:
                return (mirror_rp, None, None)

    def mir_triple_new(new_rorp):
        """Return (mirror_rp, alt_mirror, None) from new_rorp"""
        mirror_rp = _check_new_index(mirror_root, new_rorp.index)
        if mirror_rp:
            return (mirror_rp, None, None)
        alt_mirror = _get_next_free_filename()
        return (_get_long_rp(alt_mirror), alt_mirror, None)

    def update_rorp(new_rorp, alt_mirror, alt_inc):
        """Update new_rorp with alternate mirror/inc information"""
        if not new_rorp or not new_rorp.lstat():
            return
        if alt_mirror:
            new_rorp.set_alt_mirror_name(alt_mirror)
        elif alt_inc:
            new_rorp.set_alt_inc_name(alt_inc)

    def find_inc_pair(index, mirror_rp, alt_mirror, alt_inc):
        """Return (alt_inc, inc_rp) pair"""
        if alt_mirror:
            return (None, mirror_rp)
        elif alt_inc:
            return (alt_inc, _get_long_rp(alt_inc))
        elif not index:
            return (None, inc_root)

        trial_inc_index = index[:-1] + (index[-1] + (b'a' * 50), )
        if _check_new_index(inc_root, trial_inc_index, make_dirs=1):
            return (None, inc_root.new_index(index))
        alt_inc = _get_next_free_filename()
        return (alt_inc, _get_long_rp(alt_inc))

    (new_rorp, old_rorp) = rorp_pair
    if old_rorp and old_rorp.lstat():
        mirror_rp, alt_mirror, alt_inc = mir_triple_old(old_rorp)
        index = old_rorp.index
    elif new_rorp and new_rorp.lstat():
        mirror_rp, alt_mirror, alt_inc = mir_triple_new(new_rorp)
        index = new_rorp.index
    else:
        log.Log.FatalError(
            "Neither old '{op}' nor new path '{np}' is existing".format(
                op=old_rorp, np=new_rorp))

    alt_inc, inc_rp = find_inc_pair(index, mirror_rp, alt_mirror, alt_inc)
    update_rorp(new_rorp, alt_mirror, alt_inc)
    return mirror_rp, inc_rp


# ------------------------------------------------------------------
# The following section is for restoring or regressing
# ------------------------------------------------------------------


def update_rf(rf, rorp, mirror_root, rf_class):
    """
    Return new or updated file based on alt name info in rorp

    rf_class is the object type to return, RestoreFile or RegressFile
    """

    def update_incs(rf, inc_base):
        """Swap inclist in rf with those with base inc_base and return"""
        log.Log("Restoring with increment base {ib} for file {rp}".format(
            ib=safestr.to_str(inc_base), rp=rf), log.DEBUG)
        rf.inc_rp = _get_long_rp(inc_base)
        rf.inc_list = _get_inclist(inc_base, rf_class)
        rf.set_relevant_incs()

    def update_existing_rf(rf, rorp):
        """Update rf based on rorp, don't make new one"""
        if rorp.has_alt_mirror_name():
            inc_name = rorp.get_alt_mirror_name()
            raise Exception("the following line doesn't make any sense but does it matter?")
            # FIXME mirror_name isn't defined anywhere, is inc_name meant?
            # rf.mirror_rp = _get_long_rp(mirror_name)
        elif rorp.has_alt_inc_name():
            inc_name = rorp.get_alt_inc_name()
        else:
            inc_name = None

        if inc_name:
            update_incs(rf, inc_name)

    def make_new_rf(rorp, mirror_root):
        """Make a new rf when long name info is available"""
        if rorp.has_alt_mirror_name():
            inc_name = rorp.get_alt_mirror_name()
            mirror_rp = _get_long_rp(inc_name)
        else:
            mirror_rp = mirror_root.new_index(rorp.index)
            if rorp.has_alt_inc_name():
                inc_name = rorp.get_alt_inc_name()
            else:
                return rf_class(mirror_rp, None, [])

        rf = rf_class(mirror_rp, None, [])
        update_incs(rf, inc_name)
        return rf

    if not rorp:
        return rf
    if rf and not rorp.has_alt_mirror_name() and not rorp.has_alt_inc_name():
        return rf  # Most common case
    if rf:
        update_existing_rf(rf, rorp)
        return rf
    else:
        return make_new_rf(rorp, mirror_root)


# === INTERNAL FUNCTIONS ===


def _get_long_rp(base=None):
    """Return an rpath in long name directory with given base"""
    global _long_name_rootrp
    if not _long_name_rootrp:
        _long_name_rootrp = Globals.rbdir.append(_long_name_dir)
        if not _long_name_rootrp.lstat():
            _long_name_rootrp.mkdir()
    if base:
        return _long_name_rootrp.append(base)
    else:
        return _long_name_rootrp


def _get_next_free_filename():
    """Return next free filename available in the long filename directory"""
    global _free_name_counter

    def scan_next_free():
        """Return value of _free_name_counter by listing long filename dir"""
        log.Log("Setting next free from long filenames dir", log.INFO)
        cur_high = 0
        for filename in _get_long_rp().listdir():
            try:
                i = int(filename.split(b'.')[0])
            except ValueError:
                continue
            if i > cur_high:
                cur_high = i
        return cur_high + 1

    def read_next_free():
        """Return next int free by reading the next_free file, or None"""
        rp = _get_long_rp(_counter_filename)
        if not rp.lstat():
            return None
        return int(rp.get_string())

    def write_next_free(i):
        """Write value i into the counter file"""
        rp = _get_long_rp(_counter_filename)
        if rp.lstat():
            rp.delete()
        rp.write_string(str(_free_name_counter))
        rp.fsync_with_dir()

    if not _free_name_counter:
        _free_name_counter = read_next_free()
    if not _free_name_counter:
        _free_name_counter = scan_next_free()
    filename = b'%i' % _free_name_counter
    rp = _get_long_rp(filename)
    assert not rp.lstat(), (
        "Unexpected file '{rp}' found".format(rp=rp))
    _free_name_counter += 1
    write_next_free(_free_name_counter)
    return filename


def _check_new_index(base, index, make_dirs=0):
    """Return new rpath with given index, or None if that is too long

    If make_dir is True, make any parent directories to assure that
    file is really too long, and not just in directories that don't exist.

    """

    def wrap_call(func, *args):
        try:
            result = func(*args)
        except OSError as exc:
            # Windows with enabled long paths seems to consider too long
            # filenames as having an incorrect syntax, but only under certain
            # circumstances
            if (exc.errno == errno.ENAMETOOLONG
                    or (exc.errno == errno.EINVAL
                        and hasattr(exc, "winerror") and exc.winerror == 123)):
                return None
            raise
        return result

    def make_parent(rp):
        parent = rp.get_parent_rp()
        if parent.lstat():
            return 1
        parent.makedirs()
        return 2

    rp = wrap_call(base.new_index, index)
    if not make_dirs or not rp or rp.lstat():
        return rp

    parent_result = wrap_call(make_parent, rp)
    if not parent_result:
        return None
    elif parent_result == 1:
        return rp
    else:
        return wrap_call(base.new_index, index)


def _get_inclist(inc_base_name, rf_class):
    if not _restore_inc_cache:
        _set_restore_cache(rf_class)
    try:
        return _restore_inc_cache[inc_base_name]
    except KeyError:
        return []


def _set_restore_cache(rf_class):
    """Initialize _restore_inc_cache based on long filename dir"""
    global _restore_inc_cache
    _restore_inc_cache = {}
    root_rf = rf_class(_get_long_rp(), _get_long_rp(), [])
    for incbase_rp, inclist in root_rf.yield_inc_complexes(_get_long_rp()):
        _restore_inc_cache[incbase_rp.index[-1]] = inclist
