# Copyright 2002, 2003 Ben Escoto
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
"""High level functions for mirroring and mirror+incrementing"""

import errno
from . import Globals, metadata, rorpiter, TempFile, Hardlink, robust, \
    increment, rpath, log, selection, Time, Rdiff, statistics, iterfile, \
    hash, longname


def Mirror(src_rpath, dest_rpath):
    """Turn dest_rpath into a copy of src_rpath"""
    log.Log(
        "Starting mirror %s to %s" % (src_rpath.get_safepath(),
                                      dest_rpath.get_safepath()), 4)
    SourceS = src_rpath.conn.backup.SourceStruct
    DestS = dest_rpath.conn.backup.DestinationStruct

    source_rpiter = SourceS.get_source_select()
    DestS.set_rorp_cache(dest_rpath, source_rpiter, 0)
    dest_sigiter = DestS.get_sigs(dest_rpath)
    source_diffiter = SourceS.get_diffs(dest_sigiter)
    DestS.patch(dest_rpath, source_diffiter)


def Mirror_and_increment(src_rpath, dest_rpath, inc_rpath):
    """Mirror + put increments in tree based at inc_rpath"""
    log.Log(
        "Starting increment operation %s to %s" % (src_rpath.get_safepath(),
                                                   dest_rpath.get_safepath()),
        4)
    SourceS = src_rpath.conn.backup.SourceStruct
    DestS = dest_rpath.conn.backup.DestinationStruct

    source_rpiter = SourceS.get_source_select()
    DestS.set_rorp_cache(dest_rpath, source_rpiter, 1)
    dest_sigiter = DestS.get_sigs(dest_rpath)
    source_diffiter = SourceS.get_diffs(dest_sigiter)
    DestS.patch_and_increment(dest_rpath, source_diffiter, inc_rpath)


class SourceStruct:
    """Hold info used on source side when backing up"""
    _source_select = None  # will be set to source Select iterator

    @classmethod
    def set_source_select(cls, rpath, tuplelist, *filelists):
        """Initialize select object using tuplelist

        Note that each list in filelists must each be passed as
        separate arguments, so each is recognized as a file by the
        connection.  Otherwise we will get an error because a list
        containing files can't be pickled.

        Also, cls._source_select needs to be cached so get_diffs below
        can retrieve the necessary rps.

        """
        sel = selection.Select(rpath)
        sel.ParseArgs(tuplelist, filelists)
        sel_iter = sel.set_iter()
        cache_size = Globals.pipeline_max_length * 3  # to and from+leeway
        cls._source_select = rorpiter.CacheIndexable(sel_iter, cache_size)
        Globals.set('select_mirror', sel_iter)

    @classmethod
    def get_source_select(cls):
        """Return source select iterator, set by set_source_select"""
        return cls._source_select

    @classmethod
    def get_diffs(cls, dest_sigiter):
        """Return diffs of any files with signature in dest_sigiter"""
        source_rps = cls._source_select
        error_handler = robust.get_error_handler("ListError")

        def attach_snapshot(diff_rorp, src_rp):
            """Attach file of snapshot to diff_rorp, w/ error checking"""
            fileobj = robust.check_common_error(
                error_handler, rpath.RPath.open, (src_rp, "rb"))
            if fileobj:
                diff_rorp.setfile(hash.FileWrapper(fileobj))
            else:
                diff_rorp.zero()
            diff_rorp.set_attached_filetype('snapshot')

        def attach_diff(diff_rorp, src_rp, dest_sig):
            """Attach file of diff to diff_rorp, w/ error checking"""
            fileobj = robust.check_common_error(
                error_handler, Rdiff.get_delta_sigrp_hash, (dest_sig, src_rp))
            if fileobj:
                diff_rorp.setfile(fileobj)
                diff_rorp.set_attached_filetype('diff')
            else:
                diff_rorp.zero()
                diff_rorp.set_attached_filetype('snapshot')

        for dest_sig in dest_sigiter:
            if dest_sig is iterfile.MiscIterFlushRepeat:
                yield iterfile.MiscIterFlush  # Flush buffer when get_sigs does
                continue
            src_rp = (source_rps.get(dest_sig.index)
                      or rpath.RORPath(dest_sig.index))
            diff_rorp = src_rp.getRORPath()
            if dest_sig.isflaglinked():
                diff_rorp.flaglinked(dest_sig.get_link_flag())
            elif src_rp.isreg():
                reset_perms = False
                if (Globals.process_uid != 0 and not src_rp.readable()
                        and src_rp.isowner()):
                    reset_perms = True
                    src_rp.chmod(0o400 | src_rp.getperms())

                if dest_sig.isreg():
                    attach_diff(diff_rorp, src_rp, dest_sig)
                else:
                    attach_snapshot(diff_rorp, src_rp)

                if reset_perms:
                    src_rp.chmod(src_rp.getperms() & ~0o400)
            else:
                dest_sig.close_if_necessary()
                diff_rorp.set_attached_filetype('snapshot')
            yield diff_rorp


class DestinationStruct:
    """Hold info used by destination side when backing up"""

    @classmethod
    def get_dest_select(cls, rpath, use_metadata=1):
        """

        Return destination select rorpath iterator

        If metadata file doesn't exist, select all files on
        destination except rdiff-backup-data directory.

        """

        def get_iter_from_fs():
            """Get the combined iterator from the filesystem"""
            sel = selection.Select(rpath)
            sel.parse_rbdir_exclude()
            return sel.set_iter()

        metadata.SetManager()
        if use_metadata:
            rorp_iter = metadata.ManagerObj.GetAtTime(Time.prevtime)
            if rorp_iter:
                return rorp_iter
        return get_iter_from_fs()

    @classmethod
    def set_rorp_cache(cls, baserp, source_iter, for_increment):
        """

        Initialize cls.CCPP, the destination rorp cache

        for_increment should be true if we are mirror+incrementing,
        false if we are just mirroring.

        """
        dest_iter = cls.get_dest_select(baserp, for_increment)
        collated = rorpiter.Collate2Iters(source_iter, dest_iter)
        cls.CCPP = CacheCollatedPostProcess(
            collated, Globals.pipeline_max_length * 4, baserp)
        # pipeline len adds some leeway over just*3 (to and from and back)

    @classmethod
    def get_sigs(cls, dest_base_rpath):
        """Yield signatures of any changed destination files

        If we are backing up across a pipe, we must flush the pipeline
        every so often so it doesn't get congested on destination end.

        """
        flush_threshold = Globals.pipeline_max_length - 2
        num_rorps_seen = 0
        for src_rorp, dest_rorp in cls.CCPP:
            if (Globals.backup_reader is not Globals.backup_writer):
                num_rorps_seen += 1
                if (num_rorps_seen > flush_threshold):
                    num_rorps_seen = 0
                    yield iterfile.MiscIterFlushRepeat
            if not (src_rorp and dest_rorp and src_rorp == dest_rorp
                    and (not Globals.preserve_hardlinks
                         or Hardlink.rorp_eq(src_rorp, dest_rorp))):

                index = src_rorp and src_rorp.index or dest_rorp.index
                sig = cls.get_one_sig(dest_base_rpath, index, src_rorp,
                                      dest_rorp)
                if sig:
                    cls.CCPP.flag_changed(index)
                    yield sig

    @classmethod
    def get_one_sig(cls, dest_base_rpath, index, src_rorp, dest_rorp):
        """Return a signature given source and destination rorps"""
        if (Globals.preserve_hardlinks and src_rorp
                and Hardlink.islinked(src_rorp)):
            dest_sig = rpath.RORPath(index)
            dest_sig.flaglinked(Hardlink.get_link_index(src_rorp))
        elif dest_rorp:
            dest_sig = dest_rorp.getRORPath()
            if dest_rorp.isreg():
                dest_rp = longname.get_mirror_rp(dest_base_rpath, dest_rorp)
                sig_fp = cls.get_one_sig_fp(dest_rp)
                if sig_fp is None:
                    return None
                dest_sig.setfile(sig_fp)
        else:
            dest_sig = rpath.RORPath(index)
        return dest_sig

    @classmethod
    def get_one_sig_fp(cls, dest_rp):
        """Return a signature fp of given index, corresponding to reg file"""
        if not dest_rp.isreg():
            log.ErrorLog.write_if_open(
                "UpdateError", dest_rp,
                "File changed from regular file before signature")
            return None
        if (Globals.process_uid != 0 and not dest_rp.readable()
                and dest_rp.isowner()):
            # This branch can happen with root source and non-root
            # destination.  Permissions are changed permanently, which
            # should propagate to the diffs
            dest_rp.chmod(0o400 | dest_rp.getperms())
        try:
            return Rdiff.get_signature(dest_rp)
        except IOError as e:
            if (e.errno == errno.EPERM or e.errno == errno.EACCES):
                try:
                    # Try chmod'ing anyway -- This can work on NFS and AFS
                    # depending on the setup. We keep the if() statement
                    # above for performance reasons.
                    dest_rp.chmod(0o400 | dest_rp.getperms())
                    return Rdiff.get_signature(dest_rp)
                except (IOError, OSError):
                    log.Log.FatalError(
                        "Could not open %s for reading. Check "
                        "permissions on file." % (dest_rp.path, ))
            else:
                raise

    @classmethod
    def patch(cls, dest_rpath, source_diffiter, start_index=()):
        """Patch dest_rpath with an rorpiter of diffs"""
        ITR = rorpiter.IterTreeReducer(PatchITRB, [dest_rpath, cls.CCPP])
        for diff in rorpiter.FillInIter(source_diffiter, dest_rpath):
            log.Log("Processing changed file %s" % diff.get_safeindexpath(), 5)
            ITR(diff.index, diff)
        ITR.Finish()
        cls.CCPP.close()
        dest_rpath.setdata()

    @classmethod
    def patch_and_increment(cls, dest_rpath, source_diffiter, inc_rpath):
        """Patch dest_rpath with rorpiter of diffs and write increments"""
        ITR = rorpiter.IterTreeReducer(IncrementITRB,
                                       [dest_rpath, inc_rpath, cls.CCPP])
        for diff in rorpiter.FillInIter(source_diffiter, dest_rpath):
            log.Log("Processing changed file %s" % diff.get_safeindexpath(), 5)
            ITR(diff.index, diff)
        ITR.Finish()
        cls.CCPP.close()
        dest_rpath.setdata()


class CacheCollatedPostProcess:
    """

    Cache a collated iter of (source_rorp, dest_rorp) pairs

    This is necessary for three reasons:

    1.  The patch function may need the original source_rorp or
        dest_rp information, which is not present in the diff it
        receives.

    2.  The metadata must match what is stored in the destination
        directory.  If there is an error, either we do not update the
        dest directory for that file and the old metadata is used, or
        the file is deleted on the other end..  Thus we cannot write
        any metadata until we know the file has been processed
        correctly.

    3.  We may lack permissions on certain destination directories.
        The permissions of these directories need to be relaxed before
        we enter them to computer signatures, and then reset after we
        are done patching everything inside them.

    4.  We need some place to put hashes (like SHA1) after computing
        them and before writing them to the metadata.

    The class caches older source_rorps and dest_rps so the patch
    function can retrieve them if necessary.  The patch function can
    also update the processed correctly flag.  When an item falls out
    of the cache, we assume it has been processed, and write the
    metadata for it.

    """

    def __init__(self, collated_iter, cache_size, dest_root_rp):
        """Initialize new CCWP."""
        self.iter = collated_iter  # generates (source_rorp, dest_rorp) pairs
        self.cache_size = cache_size
        self.dest_root_rp = dest_root_rp

        self.statfileobj = statistics.init_statfileobj()
        if Globals.file_statistics:
            statistics.FileStats.init()
        self.metawriter = metadata.ManagerObj.GetWriter()

        # the following should map indices to lists
        # [source_rorp, dest_rorp, changed_flag, success_flag, increment]

        # changed_flag should be true if the rorps are different, and

        # success_flag should be 1 if dest_rorp has been successfully
        # updated to source_rorp, and 2 if the destination file is
        # deleted entirely.  They both default to false (0).

        # increment holds the RPath of the increment file if one
        # exists.  It is used to record file statistics.

        self.cache_dict = {}
        self.cache_indices = []

        # Contains a list of pairs (destination_rps, permissions) to
        # be used to reset the permissions of certain directories
        # after we're finished with them
        self.dir_perms_list = []

        # Contains list of (index, (source_rorp, diff_rorp)) pairs for
        # the parent directories of the last item in the cache.
        self.parent_list = []

    def __iter__(self):
        return self

    def __next__(self):
        """Return next (source_rorp, dest_rorp) pair.  StopIteration passed"""
        source_rorp, dest_rorp = next(self.iter)
        self.pre_process(source_rorp, dest_rorp)
        index = source_rorp and source_rorp.index or dest_rorp.index
        self.cache_dict[index] = [source_rorp, dest_rorp, 0, 0, None]
        self.cache_indices.append(index)

        if len(self.cache_indices) > self.cache_size:
            self.shorten_cache()
        return source_rorp, dest_rorp

    def pre_process(self, source_rorp, dest_rorp):
        """Do initial processing on source_rorp and dest_rorp

        It will not be clear whether source_rorp and dest_rorp have
        errors at this point, so don't do anything which assumes they
        will be backed up correctly.

        """
        if Globals.preserve_hardlinks and source_rorp:
            Hardlink.add_rorp(source_rorp, dest_rorp)
        if (dest_rorp and dest_rorp.isdir() and Globals.process_uid != 0
                and dest_rorp.getperms() % 0o1000 < 0o700):
            self.unreadable_dir_init(source_rorp, dest_rorp)

    def unreadable_dir_init(self, source_rorp, dest_rorp):
        """Initialize an unreadable dir.

        Make it readable, and if necessary, store the old permissions
        in self.dir_perms_list so the old perms can be restored.

        """
        dest_rp = self.dest_root_rp.new_index(dest_rorp.index)
        dest_rp.chmod(0o700 | dest_rorp.getperms())
        if source_rorp and source_rorp.isdir():
            self.dir_perms_list.append((dest_rp, source_rorp.getperms()))

    def shorten_cache(self):
        """Remove one element from cache, possibly adding it to metadata"""
        first_index = self.cache_indices[0]
        del self.cache_indices[0]
        try:
            (old_source_rorp, old_dest_rorp, changed_flag, success_flag,
             inc) = self.cache_dict[first_index]
        except KeyError:  # probably caused by error in file system (dup)
            log.Log(
                "Warning index %s missing from CCPP cache" % (first_index, ),
                2)
            return
        del self.cache_dict[first_index]
        self.post_process(old_source_rorp, old_dest_rorp, changed_flag,
                          success_flag, inc)
        if self.dir_perms_list:
            self.reset_dir_perms(first_index)
        self.update_parent_list(first_index, old_source_rorp, old_dest_rorp)

    def update_parent_list(self, index, src_rorp, dest_rorp):
        """Update the parent cache with the recently expired main cache entry

        This method keeps parent directories in the secondary parent
        cache until all their children have expired from the main
        cache.  This is necessary because we may realize we need a
        parent directory's information after we have processed many
        subfiles.

        """
        if not (src_rorp and src_rorp.isdir()
                or dest_rorp and dest_rorp.isdir()):
            return  # neither is directory
        if not self.parent_list:
            assert index == (), index
        else:
            last_parent_index = self.parent_list[-1][0]
            lp_index, li = len(last_parent_index), len(index)
            if li > lp_index:  # descended into previous parent
                assert li == lp_index + 1, (index, last_parent_index)
            else:  # In new directory
                assert last_parent_index[:li - 1] == index[:-1], index
                self.parent_list = self.parent_list[:li]
        self.parent_list.append((index, (src_rorp, dest_rorp)))

    def post_process(self, source_rorp, dest_rorp, changed, success, inc):
        """Post process source_rorp and dest_rorp.

        The point of this is to write statistics and metadata.

        changed will be true if the files have changed.  success will
        be true if the files have been successfully updated (this is
        always false for un-changed files).

        """
        if Globals.preserve_hardlinks and source_rorp:
            Hardlink.del_rorp(source_rorp)

        if not changed or success:
            if source_rorp:
                self.statfileobj.add_source_file(source_rorp)
            if dest_rorp:
                self.statfileobj.add_dest_file(dest_rorp)
        if success == 0:
            metadata_rorp = dest_rorp
        elif success == 1:
            metadata_rorp = source_rorp
        else:
            metadata_rorp = None  # in case deleted because of ListError
        if success == 1 or success == 2:
            self.statfileobj.add_changed(source_rorp, dest_rorp)

        if metadata_rorp and metadata_rorp.lstat():
            self.metawriter.write_object(metadata_rorp)
        if Globals.file_statistics:
            statistics.FileStats.update(source_rorp, dest_rorp, changed, inc)

    def reset_dir_perms(self, current_index):
        """Reset the permissions of directories when we have left them"""
        dir_rp, perms = self.dir_perms_list[-1]
        dir_index = dir_rp.index
        if (current_index > dir_index
                and current_index[:len(dir_index)] != dir_index):
            dir_rp.chmod(perms)  # out of directory, reset perms now

    def in_cache(self, index):
        """Return true if given index is cached"""
        return index in self.cache_dict

    def flag_success(self, index):
        """Signal that the file with given index was updated successfully"""
        self.cache_dict[index][3] = 1

    def flag_deleted(self, index):
        """Signal that the destination file was deleted"""
        self.cache_dict[index][3] = 2

    def flag_changed(self, index):
        """Signal that the file with given index has changed"""
        self.cache_dict[index][2] = 1

    def set_inc(self, index, inc):
        """Set the increment of the current file"""
        self.cache_dict[index][4] = inc

    def get_parent_rorps(self, index):
        """Retrieve (src_rorp, dest_rorp) pair from parent cache"""
        for parent_index, pair in self.parent_list:
            if parent_index == index:
                return pair
        raise KeyError(index)

    def get_rorps(self, index):
        """Retrieve (source_rorp, dest_rorp) from cache"""
        try:
            return self.cache_dict[index][:2]
        except KeyError:
            return self.get_parent_rorps(index)

    def get_source_rorp(self, index):
        """Retrieve source_rorp with given index from cache"""
        assert index >= self.cache_indices[0], \
            ("CCPP index out of order: %s %s" %
                (repr(index), repr(self.cache_indices[0])))
        try:
            return self.cache_dict[index][0]
        except KeyError:
            return self.get_parent_rorps(index)[0]

    def get_mirror_rorp(self, index):
        """Retrieve mirror_rorp with given index from cache"""
        try:
            return self.cache_dict[index][1]
        except KeyError:
            return self.get_parent_rorps(index)[1]

    def update_hash(self, index, sha1sum):
        """Update the source rorp's SHA1 hash"""
        self.get_source_rorp(index).set_sha1(sha1sum)

    def update_hardlink_hash(self, diff_rorp):
        """Tag associated source_rorp with same hash diff_rorp points to"""
        sha1sum = Hardlink.get_sha1(diff_rorp)
        if not sha1sum:
            return
        source_rorp = self.get_source_rorp(diff_rorp.index)
        source_rorp.set_sha1(sha1sum)

    def close(self):
        """Process the remaining elements in the cache"""
        while self.cache_indices:
            self.shorten_cache()
        while self.dir_perms_list:
            dir_rp, perms = self.dir_perms_list.pop()
            dir_rp.chmod(perms)
        self.metawriter.close()
        metadata.ManagerObj.ConvertMetaToDiff()


class PatchITRB(rorpiter.ITRBranch):
    """Patch an rpath with the given diff iters (use with IterTreeReducer)

    The main complication here involves directories.  We have to
    finish processing the directory after what's in the directory, as
    the directory may have inappropriate permissions to alter the
    contents or the dir's mtime could change as we change the
    contents.

    """

    def __init__(self, basis_root_rp, CCPP):
        """Set basis_root_rp, the base of the tree to be incremented"""
        self.basis_root_rp = basis_root_rp
        assert basis_root_rp.conn is Globals.local_connection
        self.statfileobj = (statistics.get_active_statfileobj()
                            or statistics.StatFileObj())
        self.dir_replacement, self.dir_update = None, None
        self.CCPP = CCPP
        self.error_handler = robust.get_error_handler("UpdateError")

    def can_fast_process(self, index, diff_rorp):
        """True if diff_rorp and mirror are not directories"""
        mirror_rorp = self.CCPP.get_mirror_rorp(index)
        return not (diff_rorp.isdir() or (mirror_rorp and mirror_rorp.isdir()))

    def fast_process(self, index, diff_rorp):
        """Patch base_rp with diff_rorp (case where neither is directory)"""
        mirror_rp, discard = longname.get_mirror_inc_rps(
            self.CCPP.get_rorps(index), self.basis_root_rp)
        assert not mirror_rp.isdir(), mirror_rp
        tf = TempFile.new(mirror_rp)
        if self.patch_to_temp(mirror_rp, diff_rorp, tf):
            if tf.lstat():
                if robust.check_common_error(self.error_handler, rpath.rename,
                                             (tf, mirror_rp)) is None:
                    self.CCPP.flag_success(index)
                else:
                    tf.delete()
            elif mirror_rp and mirror_rp.lstat():
                mirror_rp.delete()
                self.CCPP.flag_deleted(index)
        else:
            tf.setdata()
            if tf.lstat():
                tf.delete()

    def patch_to_temp(self, basis_rp, diff_rorp, new):
        """Patch basis_rp, writing output in new, which doesn't exist yet

        Returns true if able to write new as desired, false if
        UpdateError or similar gets in the way.

        """
        if diff_rorp.isflaglinked():
            self.patch_hardlink_to_temp(diff_rorp, new)
        elif diff_rorp.get_attached_filetype() == 'snapshot':
            result = self.patch_snapshot_to_temp(diff_rorp, new)
            if not result:
                return 0
            elif result == 2:
                return 1  # SpecialFile
        elif not self.patch_diff_to_temp(basis_rp, diff_rorp, new):
            return 0
        if new.lstat() and not diff_rorp.isflaglinked():
            rpath.copy_attribs(diff_rorp, new)
        return self.matches_cached_rorp(diff_rorp, new)

    def patch_hardlink_to_temp(self, diff_rorp, new):
        """Hardlink diff_rorp to temp, update hash if necessary"""
        Hardlink.link_rp(diff_rorp, new, self.basis_root_rp)
        self.CCPP.update_hardlink_hash(diff_rorp)

    def patch_snapshot_to_temp(self, diff_rorp, new):
        """Write diff_rorp to new, return true if successful

        Returns 1 if normal success, 2 if special file is written,
        whether or not it is successful.  This is because special
        files either fail with a SpecialFileError, or don't need to be
        compared.

        """
        if diff_rorp.isspecial():
            self.write_special(diff_rorp, new)
            rpath.copy_attribs(diff_rorp, new)
            return 2

        report = robust.check_common_error(self.error_handler, rpath.copy,
                                           (diff_rorp, new))
        if isinstance(report, hash.Report):
            self.CCPP.update_hash(diff_rorp.index, report.sha1_digest)
            return 1
        return report != 0  # if == 0, error_handler caught something

    def patch_diff_to_temp(self, basis_rp, diff_rorp, new):
        """Apply diff_rorp to basis_rp, write output in new"""
        assert diff_rorp.get_attached_filetype() == 'diff'
        report = robust.check_common_error(
            self.error_handler, Rdiff.patch_local, (basis_rp, diff_rorp, new))
        if isinstance(report, hash.Report):
            self.CCPP.update_hash(diff_rorp.index, report.sha1_digest)
            return 1
        return report != 0  # if report == 0, error

    def matches_cached_rorp(self, diff_rorp, new_rp):
        """Return true if new_rp matches cached src rorp

        This is a final check to make sure the temp file just written
        matches the stats which we got earlier.  If it doesn't it
        could confuse the regress operation.  This is only necessary
        for regular files.

        """
        if not new_rp.isreg():
            return 1
        cached_rorp = self.CCPP.get_source_rorp(diff_rorp.index)
        if cached_rorp and cached_rorp.equal_loose(new_rp):
            return 1
        log.ErrorLog.write_if_open(
            "UpdateError", diff_rorp, "Updated mirror "
            "temp file '%s' does not match source" % new_rp.get_safepath())
        return 0

    def write_special(self, diff_rorp, new):
        """Write diff_rorp (which holds special file) to new"""
        eh = robust.get_error_handler("SpecialFileError")
        if robust.check_common_error(eh, rpath.copy, (diff_rorp, new)) == 0:
            new.setdata()
            if new.lstat():
                new.delete()
            new.touch()

    def start_process(self, index, diff_rorp):
        """Start processing directory - record information for later"""
        self.base_rp, discard = longname.get_mirror_inc_rps(
            self.CCPP.get_rorps(index), self.basis_root_rp)
        if diff_rorp.isdir():
            self.prepare_dir(diff_rorp, self.base_rp)
        elif self.set_dir_replacement(diff_rorp, self.base_rp):
            if diff_rorp.lstat():
                self.CCPP.flag_success(index)
            else:
                self.CCPP.flag_deleted(index)

    def set_dir_replacement(self, diff_rorp, base_rp):
        """Set self.dir_replacement, which holds data until done with dir

        This is used when base_rp is a dir, and diff_rorp is not.
        Returns 1 for success or 0 for failure

        """
        assert diff_rorp.get_attached_filetype() == 'snapshot'
        self.dir_replacement = TempFile.new(base_rp)
        if not self.patch_to_temp(None, diff_rorp, self.dir_replacement):
            if self.dir_replacement.lstat():
                self.dir_replacement.delete()
            # Was an error, so now restore original directory
            rpath.copy_with_attribs(
                self.CCPP.get_mirror_rorp(diff_rorp.index),
                self.dir_replacement)
            return 0
        else:
            return 1

    def prepare_dir(self, diff_rorp, base_rp):
        """Prepare base_rp to be a directory"""
        self.dir_update = diff_rorp.getRORPath()  # make copy in case changes
        if not base_rp.isdir():
            if base_rp.lstat():
                self.base_rp.delete()
            base_rp.setdata()
            base_rp.mkdir()
            self.CCPP.flag_success(diff_rorp.index)
        else:  # maybe no change, so query CCPP before tagging success
            if self.CCPP.in_cache(diff_rorp.index):
                self.CCPP.flag_success(diff_rorp.index)

    def end_process(self):
        """Finish processing directory"""
        if self.dir_update:
            assert self.base_rp.isdir()
            rpath.copy_attribs(self.dir_update, self.base_rp)

            if (Globals.process_uid != 0
                    and self.dir_update.getperms() % 0o1000 < 0o700):
                # Directory was unreadable at start -- keep it readable
                # until the end of the backup process.
                self.base_rp.chmod(0o700 | self.dir_update.getperms())
        elif self.dir_replacement:
            self.base_rp.rmdir()
            if self.dir_replacement.lstat():
                rpath.rename(self.dir_replacement, self.base_rp)


class IncrementITRB(PatchITRB):
    """Patch an rpath with the given diff iters and write increments

    Like PatchITRB, but this time also write increments.

    """

    def __init__(self, basis_root_rp, inc_root_rp, rorp_cache):
        self.inc_root_rp = inc_root_rp
        PatchITRB.__init__(self, basis_root_rp, rorp_cache)

    def fast_process(self, index, diff_rorp):
        """Patch base_rp with diff_rorp and write increment (neither is dir)"""
        mirror_rp, inc_prefix = longname.get_mirror_inc_rps(
            self.CCPP.get_rorps(index), self.basis_root_rp, self.inc_root_rp)
        tf = TempFile.new(mirror_rp)
        if self.patch_to_temp(mirror_rp, diff_rorp, tf):
            inc = robust.check_common_error(self.error_handler,
                                            increment.Increment,
                                            (tf, mirror_rp, inc_prefix))
            if inc is not None and not isinstance(inc, int):
                self.CCPP.set_inc(index, inc)
                if inc.isreg():
                    inc.fsync_with_dir()  # Write inc before rp changed
                if tf.lstat():
                    if robust.check_common_error(self.error_handler,
                                                 rpath.rename,
                                                 (tf, mirror_rp)) is None:
                        self.CCPP.flag_success(index)
                    else:
                        tf.delete()
                elif mirror_rp.lstat():
                    mirror_rp.delete()
                    self.CCPP.flag_deleted(index)
                return  # normal return, otherwise error occurred
        tf.setdata()
        if tf.lstat():
            tf.delete()

    def start_process(self, index, diff_rorp):
        """Start processing directory"""
        self.base_rp, inc_prefix = longname.get_mirror_inc_rps(
            self.CCPP.get_rorps(index), self.basis_root_rp, self.inc_root_rp)
        self.base_rp.setdata()
        assert diff_rorp.isdir() or self.base_rp.isdir(), \
            ("Either %s or %s must be a directory" % (repr(diff_rorp.get_safeindexpath()),
             repr(self.base_rp.get_safepath())))
        if diff_rorp.isdir():
            inc = increment.Increment(diff_rorp, self.base_rp, inc_prefix)
            if inc and inc.isreg():
                inc.fsync_with_dir()  # must write inc before rp changed
            self.base_rp.setdata()  # in case written by increment above
            self.prepare_dir(diff_rorp, self.base_rp)
        elif self.set_dir_replacement(diff_rorp, self.base_rp):
            inc = increment.Increment(self.dir_replacement, self.base_rp,
                                      inc_prefix)
            if inc:
                self.CCPP.set_inc(index, inc)
                self.CCPP.flag_success(index)
