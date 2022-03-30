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
The metadata manager discovers all metadata plugins and use them to
store and retrieve different types of metadata.
"""

import os
from rdiff_backup import log, Globals, rpath, Time, rorpiter
from rdiffbackup.utils import plugins
import rdiffbackup.meta


class CombinedWriter:
    """
    Used for writing all kind of metadata available
    """

    def __init__(self, writers):
        self.writers = writers

    def write_object(self, rorp):
        """
        Write information in rorp to all the writers
        """
        for writer in self.writers:
            writer.write_object(rorp)

    def close(self):
        for writer in self.writers:
            writer.close()


class Manager:
    """
    Read/Combine/Write metadata files by time
    """
    def __init__(self, data_dir=None):
        """
        Set listing of rdiff-backup-data dir
        """
        self.rplist = []
        self.timerpmap, self.prefixmap = {}, {}
        if data_dir is None:  # compat200
            self.data_dir = Globals.rbdir
        else:
            self.data_dir = data_dir
        for filename in self.data_dir.listdir():
            rp = self.data_dir.append(filename)
            if rp.isincfile():
                self._add_incrp(rp)
        # the manager shouldn't need to know so much about the main class
        # but it does currently, so we save it here for convenience
        self._meta_main_class = get_meta_list()[0]

    def get_metas_at_time(self, time, restrict_index=None):
        """
        Return combined metadata iter with all available metadata info
        """
        meta_iters = []
        meta_main_iter = self._get_meta_main_at_time(time, restrict_index)
        if not meta_main_iter:
            log.Log("Could not find mirror metadata file. "
                    "Metadata will be read from filesystem instead",
                    log.WARNING)
            return None
        # loop through the non-main meta classes
        for meta_class in get_meta_list()[1:]:
            if meta_class.is_active():
                meta_iter = self._iter_helper(time, restrict_index, meta_class)
                if meta_iter:
                    meta_iters.append((meta_class, meta_iter))
                else:
                    log.Log("{md} file not found".format(
                        md=meta_class.get_desc()), log.WARNING)
                    meta_iters.append((meta_class, iter([])))

        # join all iterators into the main iterator
        for meta_class, meta_iter in meta_iters:
            meta_main_iter = meta_class.join_iter(meta_main_iter, meta_iter)

        return meta_main_iter

    def get_writer(self, typestr=b'snapshot', time=None):
        """
        Get a writer object that can write any kind of metadata
        """
        writers = []

        for meta_class in get_meta_list():
            writer = self._writer_helper(typestr, time, meta_class)
            if writer is not None:
                writers.append(writer)

        return CombinedWriter(writers)

    def recreate_attr(self, regress_time):
        """
        Make regress_time mirror_metadata snapshot by patching

        We write to a tempfile first.  Otherwise, in case of a crash, it
        would seem we would have an intact snapshot and partial diff, not
        the reverse.
        """
        temprp = [self.data_dir.get_temp_rpath()]

        def callback(rp):
            temprp[0] = rp

        # Before API 201, metafiles couldn't be compressed
        writer = self._meta_main_class(
            temprp[0], 'wb',
            compress=(Globals.compression
                      or Globals.get_api_version() < 201),
            check_path=0, callback=callback)
        for rorp in self._get_meta_main_at_time(regress_time, None):
            writer.write_object(rorp)
        writer.close()

        finalrp = self.data_dir.append(
            b"mirror_metadata.%b.snapshot.gz" % Time.timetobytes(regress_time))
        assert not finalrp.lstat(), (
            "Metadata path '{mrp}' shouldn't exist.".format(mrp=finalrp))
        rpath.rename(temprp[0], finalrp)
        if Globals.fsync_directories:
            self.data_dir.fsync()

    def _get_meta_main_at_time(self, time, restrict_index):
        """
        Return iter of metadata rorps at given time (or None)
        """
        return self._iter_helper(time, restrict_index, self._meta_main_class)

    def _add_incrp(self, rp):
        """
        Add rp to list of inc rps in the rbdir
        """
        assert rp.isincfile(), (
            "Path '{irp}' must be an increment file.".format(irp=rp))
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

    def _iter_helper(self, time, restrict_index, meta_class):
        """
        Used below to find the right kind of file by time
        """
        if time not in self.timerpmap:
            return None
        for rp in self.timerpmap[time]:
            if rp.getincbase_bname() == meta_class.get_prefix():
                return meta_class(rp, 'r').get_objects(restrict_index)
        return None

    def _writer_helper(self, typestr, time, meta_class, force=False):
        """
        Returns a writer class or None if the meta class isn't active.

        For testing purposes, the force option allows to skip the activity
        validation.
        """
        if time is None:
            timestr = Time.getcurtimestr()
        else:
            timestr = Time.timetobytes(time)
        triple = map(os.fsencode, (meta_class.get_prefix(), timestr, typestr))
        filename = b'.'.join(triple)
        rp = self.data_dir.append(filename)
        assert not rp.lstat(), "File '{rp}' shouldn't exist.".format(rp=rp)
        assert rp.isincfile(), (
            "Path '{irp}' must be an increment file.".format(irp=rp))
        if meta_class.is_active() or force:
            # Before API 201, metafiles couldn't be compressed
            return meta_class(rp, 'w',
                              compress=(Globals.compression
                                        or Globals.get_api_version() < 201),
                              callback=self._add_incrp)
        else:
            return None


class PatchDiffMan(Manager):
    """
    Contains functions for patching and diffing metadata

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

    def sorted_prefix_inclist(self, prefix, min_time=0):
        """
        Return reverse sorted (by time) list of incs with given prefix
        """
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
                    log.Log("Metadata file '{mf}' has a duplicate "
                            "timestamp date, you might not be able to "
                            "recover files on or earlier than this date. "
                            "Assuming you're in the process of cleaning up "
                            "your repository".format(mf=rp), log.WARNING)
                else:
                    log.Log.FatalError(
                        "Metadata file '{mf}' has a duplicate timestamp "
                        "date, you might not be able to recover files on or "
                        "earlier than this date. "
                        "Check the man page on how to clean up your repository "
                        "using the '--allow-duplicate-timestamps' "
                        "option".format(mf=rp))
            else:
                unique_set.add(time)

        return [rp for (time, rp) in sortlist if time >= min_time]

    def convert_meta_main_to_diff(self):
        """
        Replace a mirror snapshot with a diff if it's appropriate
        """
        newrp, oldrp = self._check_needs_diff()
        if not newrp:
            return
        log.Log("Writing mirror_metadata diff", log.DEBUG)

        diff_writer = self._writer_helper(b'diff', oldrp.getinctime(),
                                          self._meta_main_class)
        new_iter = self._meta_main_class(newrp, 'r').get_objects()
        old_iter = self._meta_main_class(oldrp, 'r').get_objects()
        for diff_rorp in self._get_diffiter(new_iter, old_iter):
            diff_writer.write_object(diff_rorp)
        diff_writer.close()  # includes sync
        oldrp.delete()

    def _get_diffiter(self, new_iter, old_iter):
        """
        Iterate meta diffs of new_iter -> old_iter
        """
        for new_rorp, old_rorp in rorpiter.Collate2Iters(new_iter, old_iter):
            if not old_rorp:
                yield rpath.RORPath(new_rorp.index)
            elif not new_rorp or new_rorp.data != old_rorp.data:
                # exact compare here, can't use == on rorps
                yield old_rorp

    def _check_needs_diff(self):
        """
        Check if we should diff, returns (new, old) rps, or (None, None)
        """
        inclist = self.sorted_prefix_inclist(b'mirror_metadata')
        assert len(inclist) >= 1, (
            "There must be a least one element in '{ilist}'.".format(
                ilist=inclist))
        if len(inclist) == 1:
            return (None, None)
        newrp, oldrp = inclist[:2]
        assert newrp.getinctype() == oldrp.getinctype() == b'snapshot', (
            "New '{nrp}' and old '{orp}' paths must be of "
            "type 'snapshot'.".format(nrp=newrp, orp=oldrp))

        chainlen = 1
        for rp in inclist[2:]:
            if rp.getinctype() != b'diff':
                break
            chainlen += 1
        if chainlen >= self.max_diff_chain:
            return (None, None)
        return (newrp, oldrp)

    def _get_meta_main_at_time(self, time, restrict_index):
        """
        Get metadata rorp iter, possibly by patching with diffs
        """
        meta_iters = [
            self._meta_main_class(rp, 'r').get_objects(restrict_index)
            for rp in self._relevant_meta_main_incs(time)
        ]
        if not meta_iters:
            return None
        if len(meta_iters) == 1:
            return meta_iters[0]
        return self._iterate_patched_attr(meta_iters)

    def _relevant_meta_main_incs(self, time):
        """
        Return list [snapshotrp, diffrps ...] time sorted
        """
        inclist = self.sorted_prefix_inclist(b'mirror_metadata', min_time=time)
        if not inclist:
            return inclist
        assert inclist[-1].getinctime() == time, (
            "The time of the last increment '{it}' must be equal to "
            "the given time '{gt}'.".format(it=inclist[-1].getinctime(),
                                            gt=time))
        for i in range(len(inclist) - 1, -1, -1):
            if inclist[i].getinctype() == b'snapshot':
                return inclist[i:]
        else:
            log.Log.FatalError(
                "Increments list '{il}' contains no snapshots".format(
                    il=inclist))

    def _iterate_patched_attr(self, attr_iter_list):
        """
        Return an iter of metadata rorps by combining the given iters

        The iters should be given as a list/tuple in reverse
        chronological order.  The earliest rorp in each iter will
        supercede all the later ones.
        """
        for meta_tuple in rorpiter.CollateIterators(*attr_iter_list):
            for i in range(len(meta_tuple) - 1, -1, -1):
                if meta_tuple[i]:
                    if meta_tuple[i].lstat():
                        yield meta_tuple[i]
                    break  # move to next index
            else:
                log.Log.FatalError("No valid metadata tuple in list")


def get_meta_dict():
    """
    Discover all rdiff-backup meta plug-ins

    They may come either from the 'rdiffbackup.actions' spacename, or
    top-level modules with a name starting with 'rdb_action_'.
    Returns a dictionary with the name of each Action-class as key, and
    the class returned by get_plugin_class() as value.
    """
    # we attach the dictionary of plugins to an element of the function to
    # make it permanent
    if not hasattr(get_meta_dict, 'plugins'):
        get_meta_dict.plugins = plugins.get_discovered_plugins(
            rdiffbackup.meta, "rdb_meta_")
        log.Log("Found meta plugins: {mp}".format(mp=get_meta_dict.plugins),
                log.DEBUG)

    return get_meta_dict.plugins


def get_meta_list():
    """
    return a sorted list of meta plugins, the main meta being the first element
    """
    if not hasattr(get_meta_list, 'plugins'):
        main_meta = None
        meta_classes = []
        for meta_class in get_meta_dict().values():
            if meta_class.is_main_meta():
                if main_meta is None:
                    main_meta = meta_class
                else:  # there can only be one
                    log.Log.FatalError(
                        "There can only be one main metadata class, but "
                        "both {m1} and {m2} claim to be the main one".format(
                            m1=main_meta, m2=meta_class))
            else:
                meta_classes.append(meta_class)
        if main_meta is None:
            log.Log.FatalError("Couldn't identify main metadata class")
        get_meta_list.plugins = [main_meta] + meta_classes
    return get_meta_list.plugins


def get_meta_manager(recreate=False):
    """
    return current metadata manager or new one if doesn't exist yet

    The recreate variable forces the generation of a new metadata manager
    FIXME it's still rather unclear to me when a new instance is required and
    when not.
    """
    # we attach the manager to an element of the function to make it permanent
    if not hasattr(get_meta_manager, 'manager') or recreate:
        get_meta_manager.manager = PatchDiffMan()
    return get_meta_manager.manager
