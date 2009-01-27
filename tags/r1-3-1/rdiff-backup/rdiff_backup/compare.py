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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
# USA

"""Perform various kinds of comparisons.

For instance, full-file compare, compare by hash, and metadata-only
compare.  This uses elements of the backup and restore modules.

"""

from __future__ import generators
import Globals, restore, rorpiter, log, backup, static, rpath, hash, robust

def Compare(src_rp, mirror_rp, inc_rp, compare_time):
	"""Compares metadata in src_rp dir with metadata in mirror_rp at time"""
	repo_side = mirror_rp.conn.compare.RepoSide
	data_side = src_rp.conn.compare.DataSide

	repo_iter = repo_side.init_and_get_iter(mirror_rp, inc_rp, compare_time)
	return_val = print_reports(data_side.compare_fast(repo_iter))
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
	return_val = print_reports(data_side.compare_hash(repo_iter))
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
	attached_repo_iter = repo_side.attach_files(src_iter, mirror_rp,
												inc_rp, compare_time)
	report_iter = data_side.compare_full(src_rp, attached_repo_iter)
	return_val = print_reports(report_iter)
	repo_side.close_rf_cache()
	return return_val

def Verify(mirror_rp, inc_rp, verify_time):
	"""Compute SHA1 sums of repository files and check against metadata"""
	assert mirror_rp.conn is Globals.local_connection
	repo_iter = RepoSide.init_and_get_iter(mirror_rp, inc_rp, verify_time)
	base_index = RepoSide.mirror_base.index

	bad_files = 0
	for repo_rorp in repo_iter:
		if not repo_rorp.isreg(): continue
		if not repo_rorp.has_sha1():
			log.Log("Warning: Cannot find SHA1 digest for file %s,\n"
					"perhaps because this feature was added in v1.1.1"
					% (repo_rorp.get_indexpath(),), 2)
			continue
		fp = RepoSide.rf_cache.get_fp(base_index + repo_rorp.index, repo_rorp)
		computed_hash = hash.compute_sha1_fp(fp)
		if computed_hash == repo_rorp.get_sha1():
			log.Log("Verified SHA1 digest of " + repo_rorp.get_indexpath(), 5)
		else:
			bad_files += 1
			log.Log("Warning: Computed SHA1 digest of %s\n   %s\n"
					"doesn't match recorded digest of\n   %s\n"
					"Your backup repository may be corrupted!" %
					(repo_rorp.get_indexpath(), computed_hash,
					 repo_rorp.get_sha1()), 2)
	RepoSide.close_rf_cache()
	if not bad_files: log.Log("Every file verified successfully.", 3)
	return bad_files

def print_reports(report_iter):
	"""Given an iter of CompareReport objects, print them to screen"""
	assert not Globals.server
	changed_files_found = 0
	for report in report_iter:
		changed_files_found = 1
		indexpath = report.index and "/".join(report.index) or "."
		print "%s: %s" % (report.reason, indexpath)

	if not changed_files_found:
		log.Log("No changes found.  Directory matches archive data.", 3)
	return changed_files_found

def get_basic_report(src_rp, repo_rorp, comp_data_func = None):
	"""Compare src_rp and repo_rorp, return CompareReport

	comp_data_func should be a function that accepts (src_rp,
	repo_rorp) as arguments, and return 1 if they have the same data,
	0 otherwise.  If comp_data_func is false, don't compare file data,
	only metadata.

	"""
	if src_rp: index = src_rp.index
	else: index = repo_rorp.index
	if not repo_rorp or not repo_rorp.lstat():
		return CompareReport(index, "new")
	elif not src_rp or not src_rp.lstat():
		return CompareReport(index, "deleted")
	elif comp_data_func and src_rp.isreg() and repo_rorp.isreg():
		if src_rp == repo_rorp: meta_changed = 0
		else: meta_changed = 1
		data_changed = comp_data_func(src_rp, repo_rorp)

		if not meta_changed and not data_changed: return None
		if meta_changed: meta_string = "metadata changed, "
		else: meta_string = "metadata the same, "
		if data_changed: data_string = "data changed"
		else: data_string = "data the same"
		return CompareReport(index, meta_string + data_string)
	elif src_rp == repo_rorp: return None
	else: return CompareReport(index, "changed")

def log_success(src_rorp, mir_rorp = None):
	"""Log that src_rorp and mir_rorp compare successfully"""
	path = src_rorp and src_rorp.get_indexpath() or mir_rorp.get_indexpath()
	log.Log("Successful compare: %s" % (path,), 5)


class RepoSide(restore.MirrorStruct):
	"""On the repository side, comparing is like restoring"""
	def init_and_get_iter(cls, mirror_rp, inc_rp, compare_time):
		"""Return rorp iter at given compare time"""
		cls.set_mirror_and_rest_times(compare_time)
		cls.initialize_rf_cache(mirror_rp, inc_rp)
		return cls.subtract_indicies(cls.mirror_base.index,
									 cls.get_mirror_rorp_iter())

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
					log_success(src_rorp, mir_rorp)
					continue # They must be equal, nothing else to check
				if (src_rorp.isreg() and mir_rorp.isreg() and
					src_rorp.getsize() == mir_rorp.getsize()):
					fp = cls.rf_cache.get_fp(base_index + index, mir_rorp)
					mir_rorp.setfile(fp)
					mir_rorp.set_attached_filetype('snapshot')

			if mir_rorp: yield mir_rorp
			else: yield rpath.RORPath(index) # indicate deleted mir_rorp

static.MakeClass(RepoSide)


class DataSide(backup.SourceStruct):
	"""On the side that has the current data, compare is like backing up"""
	def compare_fast(cls, repo_iter):
		"""Compare rorps (metadata only) quickly, return report iter"""
		src_iter = cls.get_source_select()
		for src_rorp, mir_rorp in rorpiter.Collate2Iters(src_iter, repo_iter):
			report = get_basic_report(src_rorp, mir_rorp)
			if report: yield report
			else: log_success(src_rorp, mir_rorp)

	def compare_hash(cls, repo_iter):
		"""Like above, but also compare sha1 sums of any regular files"""
		def hashes_changed(src_rp, mir_rorp):
			"""Return 0 if their data hashes same, 1 otherwise"""
			if not mir_rorp.has_sha1():
				log.Log("Warning: Metadata file has no digest for %s, "
						"unable to compare." % (mir_rorp.get_indexpath(),), 2)
				return 0
			elif (src_rp.getsize() == mir_rorp.getsize() and
				  hash.compute_sha1(src_rp) == mir_rorp.get_sha1()):
				return 0
			return 1

		src_iter = cls.get_source_select()
		for src_rp, mir_rorp in rorpiter.Collate2Iters(src_iter, repo_iter):
			report = get_basic_report(src_rp, mir_rorp, hashes_changed)
			if report: yield report
			else: log_success(src_rp, mir_rorp)

	def compare_full(cls, src_root, repo_iter):
		"""Given repo iter with full data attached, return report iter"""
		def error_handler(exc, src_rp, repo_rorp):
			log.Log("Error reading file %s" % (src_rp.path,), 2)
			return 0 # They aren't the same if we get an error

		def data_changed(src_rp, repo_rorp):
			"""Return 0 if full compare of data matches, 1 otherwise"""
			if src_rp.getsize() != repo_rorp.getsize(): return 1
			return not robust.check_common_error(error_handler,
				 rpath.cmp, (src_rp, repo_rorp))

		for repo_rorp in repo_iter:
			src_rp = src_root.new_index(repo_rorp.index)
			report = get_basic_report(src_rp, repo_rorp, data_changed)
			if report: yield report
			else: log_success(repo_rorp)
			
static.MakeClass(DataSide)


class CompareReport:
	"""When two files don't match, this tells you how they don't match

	This is necessary because the system that is doing the actual
	comparing may not be the one printing out the reports.  For speed
	the compare information can be pipelined back to the client
	connection as an iter of CompareReports.

	"""
	# self.file is added so that CompareReports can masquerate as
	# RORPaths when in an iterator, and thus get pipelined.
	file = None

	def __init__(self, index, reason):
		self.index = index
		self.reason = reason
