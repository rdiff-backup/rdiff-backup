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
"""
Perform various kinds of comparisons.

For instance, full-file compare, compare by hash, and metadata-only
compare.  This uses elements of the backup and restore modules.
"""

import os
from rdiff_backup import (
    backup, Globals, Hardlink, hash, log, restore, robust, rorpiter, rpath
)


# @API(RepoSide, 200, 200)
class RepoSide(restore.MirrorStruct):
    """On the repository side, comparing is like restoring"""

    # @API(RepoSide.init_and_get_iter, 200, 200)
    @classmethod
    def init_and_get_iter(cls, mirror_rp, inc_rp, compare_time):
        """Return rorp iter at given compare time"""
        cls.set_mirror_and_rest_times(compare_time)
        cls.initialize_rf_cache(mirror_rp, inc_rp)
        return cls.subtract_indices(cls.mirror_base.index,
                                    cls.get_mirror_rorp_iter())

    # @API(RepoSide.attach_files, 200, 200)
    @classmethod
    def attach_files(cls, src_iter, mirror_rp, inc_rp, compare_time):
        """Attach data to all the files that need checking

        Return an iterator of repo rorps that includes all the files
        that may have changed, and has the fileobj set on all rorps
        that need it.

        """
        repo_iter = cls.init_and_get_iter(mirror_rp, inc_rp, compare_time)
        base_index = cls.mirror_base.index
        for src_rorp, mir_rorp in rorpiter.Collate2Iters(src_iter, repo_iter):
            index = src_rorp and src_rorp.index or mir_rorp.index
            if src_rorp and mir_rorp:
                if not src_rorp.isreg() and src_rorp == mir_rorp:
                    _log_success(src_rorp, mir_rorp)
                    continue  # They must be equal, nothing else to check
                if (src_rorp.isreg() and mir_rorp.isreg()
                        and src_rorp.getsize() == mir_rorp.getsize()):
                    fp = cls.rf_cache.get_fp(base_index + index, mir_rorp)
                    mir_rorp.setfile(fp)
                    mir_rorp.set_attached_filetype('snapshot')

            if mir_rorp:
                yield mir_rorp
            else:
                yield rpath.RORPath(index)  # indicate deleted mir_rorp


# @API(DataSide, 200, 200)
class DataSide(backup.SourceStruct):
    """On the side that has the current data, compare is like backing up"""

    # @API(DataSide.compare_fast, 200, 200)
    @classmethod
    def compare_fast(cls, repo_iter):
        """Compare rorps (metadata only) quickly, return report iter"""
        src_iter = cls.get_source_select()
        for src_rorp, mir_rorp in rorpiter.Collate2Iters(src_iter, repo_iter):
            report = _get_basic_report(src_rorp, mir_rorp)
            if report:
                yield report
            else:
                _log_success(src_rorp, mir_rorp)

    # @API(DataSide.compare_hash, 200, 200)
    @classmethod
    def compare_hash(cls, repo_iter):
        """Like above, but also compare sha1 sums of any regular files"""

        def hashes_changed(src_rp, mir_rorp):
            """Return 0 if their data hashes same, 1 otherwise"""
            verify_sha1 = Hardlink.get_hash(mir_rorp)
            if not verify_sha1:
                log.Log("Metadata file has no digest for mirror file {mf}, "
                        "unable to compare.".format(mf=mir_rorp), log.WARNING)
                return 0
            elif (src_rp.getsize() == mir_rorp.getsize()
                  and hash.compute_sha1(src_rp) == verify_sha1):
                return 0
            return 1

        src_iter = cls.get_source_select()
        for src_rp, mir_rorp in rorpiter.Collate2Iters(src_iter, repo_iter):
            report = _get_basic_report(src_rp, mir_rorp, hashes_changed)
            if report:
                yield report
            else:
                _log_success(src_rp, mir_rorp)

    # @API(DataSide.compare_full, 200, 200)
    @classmethod
    def compare_full(cls, src_root, repo_iter):
        """Given repo iter with full data attached, return report iter"""

        def error_handler(exc, src_rp, repo_rorp):
            log.Log("Error reading source file {sf}".format(sf=src_rp),
                    log.WARNING)
            return 0  # They aren't the same if we get an error

        def data_changed(src_rp, repo_rorp):
            """Return 0 if full compare of data matches, 1 otherwise"""
            if src_rp.getsize() != repo_rorp.getsize():
                return 1
            return not robust.check_common_error(error_handler, rpath.cmp,
                                                 (src_rp, repo_rorp))

        for repo_rorp in repo_iter:
            src_rp = src_root.new_index(repo_rorp.index)
            report = _get_basic_report(src_rp, repo_rorp, data_changed)
            if report:
                yield report
            else:
                _log_success(repo_rorp)


class CompareReport:
    """When two files don't match, this tells you how they don't match

    This is necessary because the system that is doing the actual
    comparing may not be the one printing out the reports.  For speed
    the compare information can be pipelined back to the client
    connection as an iter of CompareReports.

    """
    # self.file is added so that CompareReports can masquerade as
    # RORPaths when in an iterator, and thus get pipelined.
    file = None

    def __init__(self, index, reason):
        self.index = index
        self.reason = reason


def Compare(src_rp, mirror_rp, inc_rp, compare_time):
    """Compares metadata in src_rp dir with metadata in mirror_rp at time"""
    repo_side = mirror_rp.conn.compare.RepoSide
    data_side = src_rp.conn.compare.DataSide

    repo_iter = repo_side.init_and_get_iter(mirror_rp, inc_rp, compare_time)
    return_val = _print_reports(data_side.compare_fast(repo_iter))
    repo_side.close_rf_cache()
    return return_val


def Compare_hash(src_rp, mirror_rp, inc_rp, compare_time):
    """Compare files at src_rp with repo at compare_time

    Note metadata differences, but also check to see if file data is
    different.  If two regular files have the same size, hash the
    source and compare to the hash presumably already present in repo.

    """
    repo_side = mirror_rp.conn.compare.RepoSide
    data_side = src_rp.conn.compare.DataSide

    repo_iter = repo_side.init_and_get_iter(mirror_rp, inc_rp, compare_time)
    return_val = _print_reports(data_side.compare_hash(repo_iter))
    repo_side.close_rf_cache()
    return return_val


def Compare_full(src_rp, mirror_rp, inc_rp, compare_time):
    """Compare full data of files at src_rp with repo at compare_time

    Like Compare_hash, but do not rely on hashes, instead copy full
    data over.

    """
    repo_side = mirror_rp.conn.compare.RepoSide
    data_side = src_rp.conn.compare.DataSide

    src_iter = data_side.get_source_select()
    attached_repo_iter = repo_side.attach_files(src_iter, mirror_rp, inc_rp,
                                                compare_time)
    report_iter = data_side.compare_full(src_rp, attached_repo_iter)
    return_val = _print_reports(report_iter)
    repo_side.close_rf_cache()
    return return_val


# @API(Verify, 200, 200)
def Verify(mirror_rp, inc_rp, verify_time):
    """Compute SHA1 sums of repository files and check against metadata"""
    assert mirror_rp.conn is Globals.local_connection, (
        "Only verify mirror locally, not remotely over '{conn}'.".format(
            conn=mirror_rp.conn))
    repo_iter = RepoSide.init_and_get_iter(mirror_rp, inc_rp, verify_time)
    base_index = RepoSide.mirror_base.index

    bad_files = 0
    no_hash = 0
    for repo_rorp in repo_iter:
        if not repo_rorp.isreg():
            continue
        verify_sha1 = Hardlink.get_hash(repo_rorp)
        if not verify_sha1:
            log.Log("Cannot find SHA1 digest for file {fi}, "
                    "perhaps because this feature was added in v1.1.1".format(
                        fi=repo_rorp), log.WARNING)
            no_hash += 1
            continue
        fp = RepoSide.rf_cache.get_fp(base_index + repo_rorp.index, repo_rorp)
        computed_hash = hash.compute_sha1_fp(fp)
        if computed_hash == verify_sha1:
            log.Log("Verified SHA1 digest of file {fi}".format(fi=repo_rorp),
                    log.INFO)
        else:
            bad_files += 1
            log.Log("Computed SHA1 digest of file {fi} '{cd}' "
                    "doesn't match recorded digest of '{rd}'. "
                    "Your backup repository may be corrupted!".format(
                        fi=repo_rorp, cd=computed_hash, rd=verify_sha1),
                    log.WARNING)
    RepoSide.close_rf_cache()
    if bad_files:
        log.Log("Verification found {cf} potentially corrupted files".format(
            cf=bad_files), log.ERROR)
        return 2
    if no_hash:
        log.Log("Verification found {fi} files without hash, all others "
                "could be verified successfully".format(fi=no_hash), log.NOTE)
    else:
        log.Log("All files verified successfully", log.NOTE)
    return 0


def _print_reports(report_iter):
    """Given an iter of CompareReport objects, print them to screen"""
    assert not Globals.server, "This function shouldn't run as server."
    changed_files_found = 0
    for report in report_iter:
        changed_files_found = 1
        indexpath = report.index and b"/".join(report.index) or b"."
        print("%s: %s" % (report.reason, os.fsdecode(indexpath)))

    if not changed_files_found:
        log.Log("No changes found. Directory matches archive data.", log.NOTE)
    return changed_files_found


def _get_basic_report(src_rp, repo_rorp, comp_data_func=None):
    """Compare src_rp and repo_rorp, return CompareReport

    comp_data_func should be a function that accepts (src_rp,
    repo_rorp) as arguments, and return 1 if they have the same data,
    0 otherwise.  If comp_data_func is false, don't compare file data,
    only metadata.

    """
    if src_rp:
        index = src_rp.index
    else:
        index = repo_rorp.index
    if not repo_rorp or not repo_rorp.lstat():
        return CompareReport(index, "new")
    elif not src_rp or not src_rp.lstat():
        return CompareReport(index, "deleted")
    elif comp_data_func and src_rp.isreg() and repo_rorp.isreg():
        if src_rp == repo_rorp:
            meta_changed = 0
        else:
            meta_changed = 1
        data_changed = comp_data_func(src_rp, repo_rorp)

        if not meta_changed and not data_changed:
            return None
        if meta_changed:
            meta_string = "metadata changed, "
        else:
            meta_string = "metadata the same, "
        if data_changed:
            data_string = "data changed"
        else:
            data_string = "data the same"
        return CompareReport(index, meta_string + data_string)
    elif src_rp == repo_rorp:
        return None
    else:
        return CompareReport(index, "changed")


def _log_success(src_rorp, mir_rorp=None):
    """Log that src_rorp and mir_rorp compare successfully"""
    path = src_rorp and str(src_rorp) or str(mir_rorp)
    log.Log("Successfully compared path {pa}".format(pa=path), log.INFO)
