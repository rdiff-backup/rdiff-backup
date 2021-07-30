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
    Globals, hash, iterfile, Rdiff, robust, rorpiter, rpath, selection
)

# ### COPIED FROM BACKUP ####


# @API(ShadowReadDir, 201)
class ShadowReadDir:
    """
    Shadow read directory for the local directory representation
    """
    _select = None  # will be set to source Select iterator

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

    @classmethod
    def get_select(cls):
        """
        Return source select iterator, set by set_select
        """
        return cls._select

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
