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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
# USA
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
from . import log, Globals, restore, regress

long_name_dir = b"long_filename_data"
rootrp = None


def get_long_rp(base=None):
    """Return an rpath in long name directory with given base"""
    global rootrp
    if not rootrp:
        rootrp = Globals.rbdir.append(long_name_dir)
        if not rootrp.lstat():
            rootrp.mkdir()
    if base:
        return rootrp.append(base)
    else:
        return rootrp


# ------------------------------------------------------------------
# These functions used mainly for backing up

# integer number of next free prefix.  Names will be created from
# integers consecutively like '1', '2', and so on.
free_name_counter = None

# Filename which holds the next available free name in it
counter_filename = b"next_free"


def get_next_free():
    """Return next free filename available in the long filename directory"""
    global free_name_counter

    def scan_next_free():
        """Return value of free_name_counter by listing long filename dir"""
        log.Log("Setting next free from long filenames dir", 5)
        cur_high = 0
        for filename in get_long_rp().listdir():
            try:
                i = int(filename.split(b'.')[0])
            except ValueError:
                continue
            if i > cur_high:
                cur_high = i
        return cur_high + 1

    def read_next_free():
        """Return next int free by reading the next_free file, or None"""
        rp = get_long_rp(counter_filename)
        if not rp.lstat():
            return None
        return int(rp.get_string())

    def write_next_free(i):
        """Write value i into the counter file"""
        rp = get_long_rp(counter_filename)
        if rp.lstat():
            rp.delete()
        rp.write_string(str(free_name_counter))
        rp.fsync_with_dir()

    if not free_name_counter:
        free_name_counter = read_next_free()
    if not free_name_counter:
        free_name_counter = scan_next_free()
    filename = b'%i' % free_name_counter
    rp = get_long_rp(filename)
    assert not rp.lstat(), "Unexpected file at %a found" % (rp.path, )
    free_name_counter += 1
    write_next_free(free_name_counter)
    return filename


def check_new_index(base, index, make_dirs=0):
    """Return new rpath with given index, or None if that is too long

    If make_dir is True, make any parent directories to assure that
    file is really too long, and not just in directories that don't exist.

    """

    def wrap_call(func, *args):
        try:
            result = func(*args)
        except EnvironmentError as exc:
            if (exc.errno == errno.ENAMETOOLONG):
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


def get_mirror_rp(mirror_base, mirror_rorp):
    """Get the mirror_rp for reading a regular file

    This will just be in the mirror_base, unless rorp has an alt
    mirror name specified.  Use new_rorp, unless it is None or empty,
    and mirror_rorp exists.

    """
    if mirror_rorp.has_alt_mirror_name():
        return get_long_rp(mirror_rorp.get_alt_mirror_name())
    else:
        rp = check_new_index(mirror_base, mirror_rorp.index)
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
            return (get_long_rp(alt_mirror), alt_mirror, None)
        else:
            mirror_rp = mirror_root.new_index(old_rorp.index)
            if old_rorp.has_alt_inc_name():
                return (mirror_rp, None, old_rorp.get_alt_inc_name())
            else:
                return (mirror_rp, None, None)

    def mir_triple_new(new_rorp):
        """Return (mirror_rp, alt_mirror, None) from new_rorp"""
        mirror_rp = check_new_index(mirror_root, new_rorp.index)
        if mirror_rp:
            return (mirror_rp, None, None)
        alt_mirror = get_next_free()
        return (get_long_rp(alt_mirror), alt_mirror, None)

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
            return (alt_inc, get_long_rp(alt_inc))
        elif not index:
            return (None, inc_root)

        trial_inc_index = index[:-1] + (index[-1] + (b'a' * 50), )
        if check_new_index(inc_root, trial_inc_index, make_dirs=1):
            return (None, inc_root.new_index(index))
        alt_inc = get_next_free()
        return (alt_inc, get_long_rp(alt_inc))

    (new_rorp, old_rorp) = rorp_pair
    if old_rorp and old_rorp.lstat():
        mirror_rp, alt_mirror, alt_inc = mir_triple_old(old_rorp)
        index = old_rorp.index
    else:
        assert new_rorp and new_rorp.lstat(), (old_rorp, new_rorp)
        mirror_rp, alt_mirror, alt_inc = mir_triple_new(new_rorp)
        index = new_rorp.index

    alt_inc, inc_rp = find_inc_pair(index, mirror_rp, alt_mirror, alt_inc)
    update_rorp(new_rorp, alt_mirror, alt_inc)
    return mirror_rp, inc_rp


# ------------------------------------------------------------------
# The following section is for restoring

# This holds a dictionary {incbase: inclist}.  The keys are increment
# bases like '1' or '23', and the values are lists containing the
# associated increments.
restore_inc_cache = None


def set_restore_cache():
    """Initialize restore_inc_cache based on long filename dir"""
    global restore_inc_cache
    restore_inc_cache = {}
    root_rf = restore.RestoreFile(get_long_rp(), get_long_rp(), [])
    for incbase_rp, inclist in root_rf.yield_inc_complexes(get_long_rp()):
        restore_inc_cache[incbase_rp.index[-1]] = inclist


def get_inclist(inc_base_name):
    if not restore_inc_cache:
        set_restore_cache()
    try:
        return restore_inc_cache[inc_base_name]
    except KeyError:
        return []


def update_rf(rf, rorp, mirror_root):
    """Return new or updated restorefile based on alt name info in rorp"""

    def update_incs(rf, inc_base):
        """Swap inclist in rf with those with base inc_base and return"""
        log.Log(
            "Restoring with increment base %a for file %s" %
            (inc_base, rorp.get_safeindexpath()), 6)
        rf.inc_rp = get_long_rp(inc_base)
        rf.inc_list = get_inclist(inc_base)
        rf.set_relevant_incs()

    def update_existing_rf(rf, rorp):
        """Update rf based on rorp, don't make new one"""
        if rorp.has_alt_mirror_name():
            inc_name = rorp.get_alt_mirror_name()
            raise Exception("the following line doesn't make any sense but does it matter?")
            # FIXME mirror_name isn't defined anywhere, is inc_name meant?
            # rf.mirror_rp = get_long_rp(mirror_name)
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
            mirror_rp = get_long_rp(inc_name)
        else:
            mirror_rp = mirror_root.new_index(rorp.index)
            if rorp.has_alt_inc_name():
                inc_name = rorp.get_alt_inc_name()
            else:
                return restore.RestoreFile(mirror_rp, None, [])

        rf = restore.RestoreFile(mirror_rp, None, [])
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


def update_regressfile(rf, rorp, mirror_root):
    """Like update_rf except return a regress file object"""
    rf = update_rf(rf, rorp, mirror_root)
    if isinstance(rf, regress.RegressFile):
        return rf
    return regress.RegressFile(rf.mirror_rp, rf.inc_rp, rf.inc_list)
