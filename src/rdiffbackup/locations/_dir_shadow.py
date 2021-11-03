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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA

"""
A shadow directory is called like this because like a shadow it does
what the local representation of the directory is telling it to do, but
it has no real life of itself, i.e. it has only class methods and can't
be instantiated.
"""

from rdiff_backup import (
    Globals, Hardlink, hash, iterfile, log,
    Rdiff, robust, rorpiter, rpath, selection
)

# ### COPIED FROM BACKUP ####


# @API(ShadowReadDir, 201)
class ShadowReadDir:
    """
    Shadow read directory for the local directory representation
    """
    _select = None  # will be set to source Select iterator

    # @API(ShadowReadDir.set_select, 201)
    @classmethod
    def set_select(cls, rp, tuplelist, *filelists):
        """
        Initialize select object using tuplelist

        Note that each list in filelists must each be passed as
        separate arguments, so each is recognized as a file by the
        connection.  Otherwise we will get an error because a list
        containing files can't be pickled.

        Also, cls._select needs to be cached so get_diffs below
        can retrieve the necessary rps.
        """
        sel = selection.Select(rp)
        sel.parse_selection_args(tuplelist, filelists)
        sel_iter = sel.set_iter()
        cache_size = Globals.pipeline_max_length * 3  # to and from+leeway
        cls._select = rorpiter.CacheIndexable(sel_iter, cache_size)
        Globals.set('select_mirror', sel_iter)

    # @API(ShadowReadDir.get_select, 201)
    @classmethod
    def get_select(cls):
        """
        Return source select iterator, set by set_select
        """
        return cls._select

    # @API(ShadowReadDir.get_diffs, 201)
    @classmethod
    def get_diffs(cls, dest_sigiter):
        """
        Return diffs of any files with signature in dest_sigiter
        """
        source_rps = cls._select
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


# @API(ShadowWriteDir, 201)
class ShadowWriteDir:
    """Hold functions to be run on the target side when restoring"""
    _select = None

    # @API(ShadowWriteDir.set_select, 201)
    @classmethod
    def set_select(cls, target, select_opts, *filelists):
        """Return a selection object iterating the rorpaths in target"""
        if not select_opts:
            return  # nothing to do...
        cls._select = selection.Select(target)
        cls._select.parse_selection_args(select_opts, filelists)

    # @API(ShadowWriteDir.get_initial_iter, 201)
    @classmethod
    def get_initial_iter(cls, target):
        """Return selector previously set with set_initial_iter"""
        if cls._select:
            return cls._select.set_iter()
        else:
            return selection.Select(target).set_iter()

    # @API(ShadowWriteDir.patch, 201)
    @classmethod
    def patch(cls, target, diff_iter):
        """
        Patch target with the diffs from the mirror side

        This function and the associated ITRB is similar to the
        patching code in backup.py, but they have different error
        correction requirements, so it seemed easier to just repeat it
        all in this module.
        """
        ITR = rorpiter.IterTreeReducer(_DirPatchITRB, [target])
        for diff in rorpiter.FillInIter(diff_iter, target):
            log.Log("Processing changed file {cf}".format(cf=diff), log.INFO)
            ITR(diff.index, diff)
        ITR.finish_processing()
        target.setdata()


class _DirPatchITRB(rorpiter.ITRBranch):
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
