# Copyright 2002, 2003, 2004, 2005 Ben Escoto
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
"""Read increment files and restore to original"""

import tempfile
import io
from rdiff_backup import rorpiter
from rdiffbackup import meta_mgr


class RestoreError(Exception):
    pass


# @API(MirrorStruct, 200, 200)
class MirrorStruct:
    """Hold functions to be run on the mirror side"""
    # If selection command line arguments given, use Select here
    _select = None
    # This will be set to the time of the current mirror
    _mirror_time = None
    # This will be set to the exact time to restore to (not restore_to_time)
    _rest_time = None

    # @API(MirrorStruct.set_mirror_and_rest_times, 200, 200)
    @classmethod
    def set_mirror_and_rest_times(cls, restore_to_time):
        """Set class variables _mirror_time and _rest_time on mirror conn"""
        MirrorStruct._mirror_time = cls.get_mirror_time()
        MirrorStruct._rest_time = cls._get_rest_time(restore_to_time)

    @classmethod
    def get_mirror_time(cls):
        """Return time (in seconds) of latest mirror"""
        cur_mirror_incs = Globals.rbdir.append(
            b"current_mirror").get_incfiles_list()
        if not cur_mirror_incs:
            log.Log.FatalError("Could not get time of current mirror")
        elif len(cur_mirror_incs) > 1:
            log.Log("Two different times for current mirror found",
                    log.WARNING)
        return cur_mirror_incs[0].getinctime()

    # @API(MirrorStruct.get_increment_times, 200, 200)
    @classmethod
    def get_increment_times(cls, rp=None):
        """Return list of times of backups, including current mirror

        Take the total list of times from the increments.<time>.dir
        file and the mirror_metadata file.  Sorted ascending.

        """
        # use dictionary to remove dups
        if not cls._mirror_time:
            d = {cls.get_mirror_time(): None}
        else:
            d = {cls._mirror_time: None}
        if not rp or not rp.index:
            rp = Globals.rbdir.append(b"increments")
        for inc in rp.get_incfiles_list():
            d[inc.getinctime()] = None
        mirror_meta_rp = Globals.rbdir.append(b"mirror_metadata")
        for inc in mirror_meta_rp.get_incfiles_list():
            d[inc.getinctime()] = None
        return_list = list(d.keys())
        return_list.sort()
        return return_list

    # @API(MirrorStruct.initialize_rf_cache, 200, 200)
    @classmethod
    def initialize_rf_cache(cls, mirror_base, inc_base):
        """Set cls.rf_cache to CachedRF object"""
        inc_list = inc_base.get_incfiles_list()
        rf = RestoreFile(mirror_base, inc_base, inc_list)
        cls.mirror_base, cls.inc_base = mirror_base, inc_base
        cls.root_rf = rf
        cls.rf_cache = CachedRF(rf)

    # @API(MirrorStruct.close_rf_cache, 200, 200)
    @classmethod
    def close_rf_cache(cls):
        """Run anything remaining on CachedRF object"""
        cls.rf_cache.close()

    @classmethod
    def get_mirror_rorp_iter(cls, rest_time=None, require_metadata=None):
        """Return iter of mirror rps at given restore time

        Usually we can use the metadata file, but if this is
        unavailable, we may have to build it from scratch.

        If the cls._select object is set, use it to filter out the
        unwanted files from the metadata_iter.

        """
        if rest_time is None:
            rest_time = cls._rest_time

        meta_manager = meta_mgr.get_meta_manager(True)
        rorp_iter = meta_manager.get_metas_at_time(rest_time,
                                                   cls.mirror_base.index)
        if not rorp_iter:
            if require_metadata:
                log.Log.FatalError("Mirror metadata not found")
            log.Log("Mirror metadata not found, reading from directory",
                    log.WARNING)
            rorp_iter = cls._get_rorp_iter_from_rf(cls.root_rf)

        if cls._select:
            rorp_iter = selection.FilterIter(cls._select, rorp_iter)
        return rorp_iter

    # @API(MirrorStruct.set_mirror_select, 200, 200)
    @classmethod
    def set_mirror_select(cls, target_rp, select_opts, *filelists):
        """Initialize the mirror selection object"""
        if not select_opts:
            return  # nothing to do...
        cls._select = selection.Select(target_rp)
        cls._select.parse_selection_args(select_opts, filelists)

    @classmethod
    def subtract_indices(cls, index, rorp_iter):
        """Subtract index from index of each rorp in rorp_iter

        subtract_indices is necessary because we
        may not be restoring from the root index.

        """
        if index == ():
            return rorp_iter

        def get_iter():
            for rorp in rorp_iter:
                assert rorp.index[:len(index)] == index, (
                    "Path '{ridx}' must be a sub-path of '{idx}'.".format(
                        ridx=rorp.index, idx=index))
                rorp.index = rorp.index[len(index):]
                yield rorp

        return get_iter()

    # @API(MirrorStruct.get_diffs, 200, 200)
    @classmethod
    def get_diffs(cls, target_iter):
        """Given rorp iter of target files, return diffs

        Here the target_iter doesn't contain any actual data, just
        attribute listings.  Thus any diffs we generate will be
        snapshots.

        """
        mir_iter = cls.subtract_indices(cls.mirror_base.index,
                                        cls.get_mirror_rorp_iter())
        collated = rorpiter.Collate2Iters(mir_iter, target_iter)
        return cls._get_diffs_from_collated(collated)

    @classmethod
    def _get_rest_time(cls, restore_to_time):
        """Return older time, if restore_to_time is in between two inc times

        There is a slightly tricky reason for doing this: The rest of the
        code just ignores increments that are older than restore_to_time.
        But sometimes we want to consider the very next increment older
        than rest time, because rest_time will be between two increments,
        and what was actually on the mirror side will correspond to the
        older one.

        So if restore_to_time is inbetween two increments, return the
        older one.

        """
        inctimes = cls.get_increment_times()
        older_times = [time for time in inctimes if time <= restore_to_time]
        if older_times:
            return max(older_times)
        else:  # restore time older than oldest increment, just return that
            return min(inctimes)

    @classmethod
    def _get_rorp_iter_from_rf(cls, rf):
        """Recursively yield mirror rorps from rf"""
        rorp = rf.get_attribs()
        yield rorp
        if rorp.isdir():
            for sub_rf in rf.yield_sub_rfs():
                for attribs in cls._get_rorp_iter_from_rf(sub_rf):
                    yield attribs

    @classmethod
    def _get_diffs_from_collated(cls, collated):
        """Get diff iterator from collated"""
        for mir_rorp, target_rorp in collated:
            if Globals.preserve_hardlinks and mir_rorp:
                Hardlink.add_rorp(mir_rorp, target_rorp)
            if (not target_rorp or not mir_rorp or not mir_rorp == target_rorp
                    or (Globals.preserve_hardlinks
                        and not Hardlink.rorp_eq(mir_rorp, target_rorp))):
                diff = cls._get_diff(mir_rorp, target_rorp)
            else:
                diff = None
            if Globals.preserve_hardlinks and mir_rorp:
                Hardlink.del_rorp(mir_rorp)
            if diff:
                yield diff

    @classmethod
    def _get_diff(cls, mir_rorp, target_rorp):
        """Get a diff for mir_rorp at time"""
        if not mir_rorp:
            mir_rorp = rpath.RORPath(target_rorp.index)
        elif Globals.preserve_hardlinks and Hardlink.is_linked(mir_rorp):
            mir_rorp.flaglinked(Hardlink.get_link_index(mir_rorp))
        elif mir_rorp.isreg():
            expanded_index = cls.mirror_base.index + mir_rorp.index
            file_fp = cls.rf_cache.get_fp(expanded_index, mir_rorp)
            mir_rorp.setfile(hash.FileWrapper(file_fp))
        mir_rorp.set_attached_filetype('snapshot')
        return mir_rorp


# @API(TargetStruct, 200, 200)
class TargetStruct:
    """Hold functions to be run on the target side when restoring"""
    _select = None

    # @API(TargetStruct.set_target_select, 200, 200)
    @classmethod
    def set_target_select(cls, target, select_opts, *filelists):
        """Return a selection object iterating the rorpaths in target"""
        if not select_opts:
            return  # nothing to do...
        cls._select = selection.Select(target)
        cls._select.parse_selection_args(select_opts, filelists)

    # @API(TargetStruct.get_initial_iter, 200, 200)
    @classmethod
    def get_initial_iter(cls, target):
        """Return selector previously set with set_initial_iter"""
        if cls._select:
            return cls._select.get_select_iter()
        else:
            return selection.Select(target).get_select_iter()

    # @API(TargetStruct.patch, 200, 200)
    @classmethod
    def patch(cls, target, diff_iter):
        """Patch target with the diffs from the mirror side

        This function and the associated ITRB is similar to the
        patching code in backup.py, but they have different error
        correction requirements, so it seemed easier to just repeat it
        all in this module.

        """
        ITR = rorpiter.IterTreeReducer(PatchITRB, [target])
        for diff in rorpiter.FillInIter(diff_iter, target):
            log.Log("Processing changed file {cf}".format(cf=diff), log.INFO)
            ITR(diff.index, diff)
        ITR.finish_processing()
        target.setdata()


class CachedRF:
    """Store RestoreFile objects until they are needed

    The code above would like to pretend it has random access to RFs,
    making one for a particular index at will.  However, in general
    this involves listing and filtering a directory, which can get
    expensive.

    Thus, when a CachedRF retrieves an RestoreFile, it creates all the
    RFs of that directory at the same time, and doesn't have to
    recalculate.  It assumes the indices will be in order, so the
    cache is deleted if a later index is requested.

    """

    def __init__(self, root_rf):
        """Initialize CachedRF, self.rf_list variable"""
        self.root_rf = root_rf
        self.rf_list = []  # list should filled in index order
        if Globals.process_uid != 0:
            self.perm_changer = PermissionChanger(root_rf.mirror_rp)

    def get_fp(self, index, mir_rorp):
        """Return the file object (for reading) of given index"""
        rf = longname.update_rf(
            self._get_rf(index, mir_rorp), mir_rorp, self.root_rf.mirror_rp,
            RestoreFile)
        if not rf:
            log.Log(
                "Unable to retrieve data for file {fi}! The cause is "
                "probably data loss from the backup repository".format(
                    fi=(index and "/".join(index) or '.')), log.WARNING)
            return io.BytesIO()
        return rf.get_restore_fp()

    def close(self):
        """Finish remaining rps in PermissionChanger"""
        if Globals.process_uid != 0:
            self.perm_changer.finish()

    def _get_rf(self, index, mir_rorp=None):
        """Get a RestoreFile for given index, or None"""
        while 1:
            if not self.rf_list:
                if not self._add_rfs(index, mir_rorp):
                    return None
            rf = self.rf_list[0]
            if rf.index == index:
                if Globals.process_uid != 0:
                    self.perm_changer(index, mir_rorp)
                return rf
            elif rf.index > index:
                # Try to add earlier indices.  But if first is
                # already from same directory, or we can't find any
                # from that directory, then we know it can't be added.
                if (index[:-1] == rf.index[:-1]
                        or not self._add_rfs(index, mir_rorp)):
                    return None
            else:
                del self.rf_list[0]

    def _add_rfs(self, index, mir_rorp=None):
        """Given index, add the rfs in that same directory

        Returns false if no rfs are available, which usually indicates
        an error.

        """
        if not index:
            return self.root_rf
        if mir_rorp.has_alt_mirror_name():
            return  # longname alias separate
        parent_index = index[:-1]
        if Globals.process_uid != 0:
            self.perm_changer(parent_index)
        temp_rf = RestoreFile(
            self.root_rf.mirror_rp.new_index(parent_index),
            self.root_rf.inc_rp.new_index(parent_index), [])
        new_rfs = list(temp_rf.yield_sub_rfs())
        if not new_rfs:
            return 0
        self.rf_list[0:0] = new_rfs
        return 1

    def _debug_list_rfs_in_cache(self, index):
        """Used for debugging, return indices of cache rfs for printing"""
        s1 = "-------- Cached RF for %s -------" % (index, )
        s2 = " ".join([str(rf.index) for rf in self.rf_list])
        s3 = "--------------------------"
        return "\n".join((s1, s2, s3))


class RestoreFile:
    """Hold data about a single mirror file and its related increments

    self.relevant_incs will be set to a list of increments that matter
    for restoring a regular file.  If the patches are to mirror_rp, it
    will be the first element in self.relevant.incs

    """

    def __init__(self, mirror_rp, inc_rp, inc_list):
        self.index = mirror_rp.index
        self.mirror_rp = mirror_rp
        self.inc_rp, self.inc_list = inc_rp, inc_list
        self.set_relevant_incs()

    def __str__(self):
        return "Index: %s, Mirror: %s, Increment: %s\nIncList: %s\nIncRel: %s" % (
            self.index, self.mirror_rp, self.inc_rp,
            list(map(str, self.inc_list)), list(map(str, self.relevant_incs)))

    def set_relevant_incs(self):
        """Set self.relevant_incs to increments that matter for restoring

        relevant_incs is sorted newest first.  If mirror_rp matters,
        it will be (first) in relevant_incs.

        """
        self.mirror_rp.inc_type = b'snapshot'
        self.mirror_rp.inc_compressed = 0
        if (not self.inc_list
                or MirrorStruct._rest_time >= MirrorStruct._mirror_time):
            self.relevant_incs = [self.mirror_rp]
            return

        newer_incs = self.get_newer_incs()
        i = 0
        while (i < len(newer_incs)):
            # Only diff type increments require later versions
            if newer_incs[i].getinctype() != b"diff":
                break
            i = i + 1
        self.relevant_incs = newer_incs[:i + 1]
        if (not self.relevant_incs
                or self.relevant_incs[-1].getinctype() == b"diff"):
            self.relevant_incs.append(self.mirror_rp)
        self.relevant_incs.reverse()  # return in reversed order

    def get_newer_incs(self):
        """Return list of newer incs sorted by time (increasing)

        Also discard increments older than rest_time (rest_time we are
        assuming is the exact time rdiff-backup was run, so no need to
        consider the next oldest increment or any of that)

        """
        incpairs = []
        for inc in self.inc_list:
            time = inc.getinctime()
            if time >= MirrorStruct._rest_time:
                incpairs.append((time, inc))
        incpairs.sort()
        return [pair[1] for pair in incpairs]

    def get_attribs(self):
        """Return RORP with restored attributes, but no data

        This should only be necessary if the metadata file is lost for
        some reason.  Otherwise the file provides all data.  The size
        will be wrong here, because the attribs may be taken from
        diff.

        """
        last_inc = self.relevant_incs[-1]
        if last_inc.getinctype() == b'missing':
            return rpath.RORPath(self.index)

        rorp = last_inc.getRORPath()
        rorp.index = self.index
        if last_inc.getinctype() == b'dir':
            rorp.data['type'] = 'dir'
        return rorp

    def get_restore_fp(self):
        """Return file object of restored data"""

        def get_fp():
            current_fp = self._get_first_fp()
            for inc_diff in self.relevant_incs[1:]:
                log.Log("Applying patch file {pf}".format(pf=inc_diff),
                        log.DEBUG)
                assert inc_diff.getinctype() == b'diff', (
                    "Path '{irp!r}' must be of type 'diff'.".format(
                        irp=inc_diff))
                delta_fp = inc_diff.open("rb", inc_diff.isinccompressed())
                try:
                    new_fp = tempfile.TemporaryFile()
                    Rdiff.write_patched_fp(current_fp, delta_fp, new_fp)
                    new_fp.seek(0)
                except OSError:
                    tmpdir = tempfile.gettempdir()
                    log.Log("Error while writing to temporary directory "
                            "{td}".format(td=tmpdir), log.ERROR)
                    raise
                current_fp = new_fp
            return current_fp

        def error_handler(exc):
            log.Log("Failed reading file {fi}, substituting empty file.".format(
                fi=self.mirror_rp), log.WARNING)
            return io.BytesIO(b'')

        if not self.relevant_incs[-1].isreg():
            log.Log("""Could not restore file {rf}!

A regular file was indicated by the metadata, but could not be
constructed from existing increments because last increment had type {it}.
Instead of the actual file's data, an empty length file will be created.
This error is probably caused by data loss in the
rdiff-backup destination directory, or a bug in rdiff-backup""".format(
                rf=self.mirror_rp,
                it=self.relevant_incs[-1].lstat()), log.WARNING)
            return io.BytesIO()
        return robust.check_common_error(error_handler, get_fp)

    def yield_sub_rfs(self):
        """Return RestoreFiles under current RestoreFile (which is dir)"""
        if not self.mirror_rp.isdir() and not self.inc_rp.isdir():
            return
        if self.mirror_rp.isdir():
            mirror_iter = self._yield_mirrorrps(self.mirror_rp)
        else:
            mirror_iter = iter([])
        if self.inc_rp.isdir():
            inc_pair_iter = self.yield_inc_complexes(self.inc_rp)
        else:
            inc_pair_iter = iter([])
        collated = rorpiter.Collate2Iters(mirror_iter, inc_pair_iter)

        for mirror_rp, inc_pair in collated:
            if not inc_pair:
                inc_rp = self.inc_rp.new_index(mirror_rp.index)
                inc_list = []
            else:
                inc_rp, inc_list = inc_pair
            if not mirror_rp:
                mirror_rp = self.mirror_rp.new_index_empty(inc_rp.index)
            yield self.__class__(mirror_rp, inc_rp, inc_list)

    def yield_inc_complexes(self, inc_rpath):
        """Yield (sub_inc_rpath, inc_list) IndexedTuples from given inc_rpath

        Finds pairs under directory inc_rpath.  sub_inc_rpath will just be
        the prefix rp, while the rps in inc_list should actually exist.

        """
        if not inc_rpath.isdir():
            return

        def get_inc_pairs():
            """Return unsorted list of (basename, inc_filenames) pairs"""
            inc_dict = {}  # dictionary of basenames:inc_filenames
            dirlist = robust.listrp(inc_rpath)

            def add_to_dict(filename):
                """Add filename to the inc tuple dictionary"""
                rp = inc_rpath.append(filename)
                if rp.isincfile() and rp.getinctype() != b'data':
                    basename = rp.getincbase_bname()
                    inc_filename_list = inc_dict.setdefault(basename, [])
                    inc_filename_list.append(filename)
                elif rp.isdir():
                    inc_dict.setdefault(filename, [])

            for filename in dirlist:
                add_to_dict(filename)
            return list(inc_dict.items())

        def inc_filenames2incrps(filenames):
            """Map list of filenames into increment rps"""
            inc_list = []
            for filename in filenames:
                rp = inc_rpath.append(filename)
                assert rp.isincfile(), (
                    "Path '{mrp}' must be an increment file.".format(mrp=rp))
                inc_list.append(rp)
            return inc_list

        items = get_inc_pairs()
        items.sort()  # Sorting on basis of basename now
        for (basename, inc_filenames) in items:
            sub_inc_rpath = inc_rpath.append(basename)
            yield rorpiter.IndexedTuple(
                sub_inc_rpath.index,
                (sub_inc_rpath, inc_filenames2incrps(inc_filenames)))

    def _get_first_fp(self):
        """Return first file object from relevant inc list"""
        first_inc = self.relevant_incs[0]
        assert first_inc.getinctype() == b'snapshot', (
            "Path '{srp}' must be of type 'snapshot'.".format(
                srp=first_inc))
        if not first_inc.isinccompressed():
            return first_inc.open("rb")

        try:
            # current_fp must be a real (uncompressed) file
            current_fp = tempfile.TemporaryFile()
            fp = first_inc.open("rb", compress=1)
            rpath.copyfileobj(fp, current_fp)
            fp.close()
            current_fp.seek(0)
        except OSError:
            tmpdir = tempfile.gettempdir()
            log.Log("Error while writing to temporary directory "
                    "{td}".format(td=tmpdir), log.ERROR)
            raise
        return current_fp

    def _yield_mirrorrps(self, mirrorrp):
        """Yield mirrorrps underneath given mirrorrp"""
        assert mirrorrp.isdir(), (
            "Mirror path '{mrp}' must be a directory.".format(mrp=mirrorrp))
        for filename in robust.listrp(mirrorrp):
            rp = mirrorrp.append(filename)
            if rp.index != (b'rdiff-backup-data', ):
                yield rp

    def _debug_relevant_incs_string(self):
        """Return printable string of relevant incs, used for debugging"""
        inc_header = ["---- Relevant incs for %s" % ("/".join(self.index), )]
        inc_header.extend([
            "{itp} {ils} {irp}".format(
                itp=inc.getinctype(), ils=inc.lstat(), irp=inc)
            for inc in self.relevant_incs
        ])
        inc_header.append("--------------------------------")
        return "\n".join(inc_header)


class PatchITRB(rorpiter.ITRBranch):
    """Patch an rpath with the given diff iters (use with IterTreeReducer)

    The main complication here involves directories.  We have to
    finish processing the directory after what's in the directory, as
    the directory may have inappropriate permissions to alter the
    contents or the dir's mtime could change as we change the
    contents.

    This code was originally taken from backup.py.  However, because
    of different error correction requirements, it is repeated here.

    """

    def __init__(self, basis_root_rp):
        """Set basis_root_rp, the base of the tree to be incremented"""
        assert basis_root_rp.conn is Globals.local_connection, (
            "Function shall be called only locally.")
        self.basis_root_rp = basis_root_rp
        self.dir_replacement, self.dir_update = None, None
        self.cached_rp = None

    def can_fast_process(self, index, diff_rorp):
        """True if diff_rorp and mirror are not directories"""
        rp = self._get_rp_from_root(index)
        return not diff_rorp.isdir() and not rp.isdir()

    def fast_process_file(self, index, diff_rorp):
        """Patch base_rp with diff_rorp (case where neither is directory)"""
        rp = self._get_rp_from_root(index)
        tf = rp.get_temp_rpath(sibling=True)
        self._patch_to_temp(rp, diff_rorp, tf)
        rpath.rename(tf, rp)

    def start_process_directory(self, index, diff_rorp):
        """Start processing directory - record information for later"""
        base_rp = self.base_rp = self._get_rp_from_root(index)
        assert diff_rorp.isdir() or base_rp.isdir() or not base_rp.index, (
            "Either difference '{drp}' or base '{brp}' path must be a "
            "directory or the index of the base be empty.".format(
                drp=diff_rorp, brp=base_rp))
        if diff_rorp.isdir():
            self._prepare_dir(diff_rorp, base_rp)
        else:
            self._set_dir_replacement(diff_rorp, base_rp)

    def end_process_directory(self):
        """Finish processing directory"""
        if self.dir_update:
            assert self.base_rp.isdir(), (
                "Base path '{brp}' must be a directory.".format(
                    brp=self.base_rp))
            rpath.copy_attribs(self.dir_update, self.base_rp)
        else:
            assert self.dir_replacement, (
                "Replacement directory must be defined.")
            self.base_rp.rmdir()
            if self.dir_replacement.lstat():
                rpath.rename(self.dir_replacement, self.base_rp)

    def _get_rp_from_root(self, index):
        """Return RPath by adding index to self.basis_root_rp"""
        if not self.cached_rp or self.cached_rp.index != index:
            self.cached_rp = self.basis_root_rp.new_index(index)
        return self.cached_rp

    def _patch_to_temp(self, basis_rp, diff_rorp, new):
        """Patch basis_rp, writing output in new, which doesn't exist yet"""
        if diff_rorp.isflaglinked():
            Hardlink.link_rp(diff_rorp, new, self.basis_root_rp)
            return
        if diff_rorp.get_attached_filetype() == 'snapshot':
            copy_report = rpath.copy(diff_rorp, new)
        else:
            assert diff_rorp.get_attached_filetype() == 'diff', (
                "File '{drp}' must be of type '{dtype}'.".format(
                    drp=diff_rorp, dtype='diff'))
            copy_report = Rdiff.patch_local(basis_rp, diff_rorp, new)
        self._check_hash(copy_report, diff_rorp)
        if new.lstat():
            rpath.copy_attribs(diff_rorp, new)

    def _check_hash(self, copy_report, diff_rorp):
        """Check the hash in the copy_report with hash in diff_rorp"""
        if not diff_rorp.isreg():
            return
        if not diff_rorp.has_sha1():
            log.Log("Hash for file {fi} missing, cannot check".format(
                fi=diff_rorp), log.WARNING)
        elif copy_report.sha1_digest == diff_rorp.get_sha1():
            log.Log("Hash {ha} of file {fi} verified".format(
                ha=diff_rorp.get_sha1(), fi=diff_rorp), log.DEBUG)
        else:
            log.Log("Calculated hash {ch} of file {fi} "
                    "doesn't match recorded hash {rh}".format(
                        ch=copy_report.sha1_digest, fi=diff_rorp,
                        rh=diff_rorp.get_sha1()), log.WARNING)

    def _prepare_dir(self, diff_rorp, base_rp):
        """Prepare base_rp to turn into a directory"""
        self.dir_update = diff_rorp.getRORPath()  # make copy in case changes
        if not base_rp.isdir():
            if base_rp.lstat():
                base_rp.delete()
            base_rp.mkdir()
        base_rp.chmod(0o700)

    def _set_dir_replacement(self, diff_rorp, base_rp):
        """Set self.dir_replacement, which holds data until done with dir

        This is used when base_rp is a dir, and diff_rorp is not.

        """
        assert diff_rorp.get_attached_filetype() == 'snapshot', (
            "File '{drp!r}' must be of type '{dtype}'.".format(
                drp=diff_rorp, dtype='snapshot'))
        self.dir_replacement = base_rp.get_temp_rpath(sibling=True)
        rpath.copy_with_attribs(diff_rorp, self.dir_replacement)
        if base_rp.isdir():
            base_rp.chmod(0o700)


class PermissionChanger:
    """Change the permission of mirror files and directories

    The problem is that mirror files and directories may need their
    permissions changed in order to be read and listed, and then
    changed back when we are done.  This class hooks into the CachedRF
    object to know when an rp is needed.

    """

    def __init__(self, root_rp):
        self.root_rp = root_rp
        self.current_index = ()
        # Below is a list of (index, rp, old_perm) triples in reverse
        # order that need clearing
        self.open_index_list = []

    def __call__(self, index, mir_rorp=None):
        """Given rpath, change permissions up to and including index"""
        if mir_rorp and mir_rorp.has_alt_mirror_name():
            return
        old_index = self.current_index
        self.current_index = index
        if not index or index <= old_index:
            return
        self._restore_old(index)
        self._add_chmod_new(old_index, index)

    def finish(self):
        """Restore any remaining rps"""
        for index, rp, perms in self.open_index_list:
            rp.chmod(perms)

    def _restore_old(self, index):
        """Restore permissions for indices we are done with"""
        while self.open_index_list:
            old_index, old_rp, old_perms = self.open_index_list[0]
            if index[:len(old_index)] > old_index:
                old_rp.chmod(old_perms)
            else:
                break
            del self.open_index_list[0]

    def _add_chmod_new(self, old_index, index):
        """Change permissions of directories between old_index and index"""
        for rp in self._get_new_rp_list(old_index, index):
            if ((rp.isreg() and not rp.readable())
                    or (rp.isdir() and not (rp.executable() and rp.readable()))):
                old_perms = rp.getperms()
                self.open_index_list.insert(0, (rp.index, rp, old_perms))
                if rp.isreg():
                    rp.chmod(0o400 | old_perms)
                else:
                    rp.chmod(0o700 | old_perms)

    def _get_new_rp_list(self, old_index, index):
        """Return list of new rp's between old_index and index

        Do this lazily so that the permissions on the outer
        directories are fixed before we need the inner dirs.

        """
        for i in range(len(index) - 1, -1, -1):
            if old_index[:i] == index[:i]:
                common_prefix_len = i
                break  # latest with i==0 does the break happen

        for total_len in range(common_prefix_len + 1, len(index) + 1):
            yield self.root_rp.new_index(index[:total_len])


def Restore(mirror_rp, inc_rpath, target, restore_to_time):
    """Recursively restore mirror and inc_rpath to target at restore_to_time
    in epoch format"""

    # Store references to classes over the connection
    MirrorS = mirror_rp.conn.restore.MirrorStruct
    TargetS = target.conn.restore.TargetStruct

    MirrorS.set_mirror_and_rest_times(restore_to_time)
    MirrorS.initialize_rf_cache(mirror_rp, inc_rpath)
    target_iter = TargetS.get_initial_iter(target)
    diff_iter = MirrorS.get_diffs(target_iter)
    TargetS.patch(target, diff_iter)
    MirrorS.close_rf_cache()


# @API(ListChangedSince, 200, 200)
def ListChangedSince(mirror_rp, inc_rp, restore_to_time):
    """List the changed files under mirror_rp since rest time

    Notice the output is an iterator of RORPs.  We do this because we
    want to give the remote connection the data in buffered
    increments, and this is done automatically for rorp iterators.
    Encode the lines in the first element of the rorp's index.

    """
    assert mirror_rp.conn is Globals.local_connection, "Run locally only"
    MirrorStruct.set_mirror_and_rest_times(restore_to_time)
    MirrorStruct.initialize_rf_cache(mirror_rp, inc_rp)

    old_iter = MirrorStruct.get_mirror_rorp_iter(MirrorStruct._rest_time, 1)
    cur_iter = MirrorStruct.get_mirror_rorp_iter(MirrorStruct._mirror_time, 1)
    collated = rorpiter.Collate2Iters(old_iter, cur_iter)
    for old_rorp, cur_rorp in collated:
        if not old_rorp:
            change = "new"
        elif not cur_rorp:
            change = "deleted"
        elif old_rorp == cur_rorp:
            continue
        else:
            change = "changed"
        path_desc = (old_rorp and str(old_rorp) or str(cur_rorp))
        yield rpath.RORPath(("%-7s %s" % (change, path_desc), ))
    MirrorStruct.close_rf_cache()


# @API(ListAtTime, 200, 200)
def ListAtTime(mirror_rp, inc_rp, time):
    """List the files in archive at the given time

    Output is a RORP Iterator with info in index.  See ListChangedSince.

    """
    assert mirror_rp.conn is Globals.local_connection, "Run locally only"
    MirrorStruct.set_mirror_and_rest_times(time)
    MirrorStruct.initialize_rf_cache(mirror_rp, inc_rp)
    old_iter = MirrorStruct.get_mirror_rorp_iter()
    for rorp in old_iter:
        yield rorp


from . import (  # noqa: E402
    Globals, Rdiff, Hardlink, selection, rpath,
    log, robust, hash, longname
)
