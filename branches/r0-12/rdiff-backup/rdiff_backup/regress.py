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

"""Code for reverting the rdiff-backup directory to prev state

This module is used after an aborted session, and the rdiff-backup
destination directory may be in-between states.  In this situation we
need to bring back the directory as it was after the last successful
backup.  The basic strategy is to restore all the attributes from the
metadata file (which we assume is intact) and delete the extra
increments.  For regular files we examine the mirror file and use the
increment file to get the old data if the mirror file is out of date.

Currently this does not recover hard links.  This may make the
regressed directory take up more disk space, but hard links can still
be recovered.

"""

from __future__ import generators
import Globals, restore, log, rorpiter, TempFile, metadata, rpath, C, \
	   Time, backup, robust

# regress_time should be set to the time we want to regress back to
# (usually the time of the last successful backup)
regress_time = None

# This should be set to the latest unsuccessful backup time
unsuccessful_backup_time = None


class RegressException(Exception):
	"""Raised on any exception in regress process"""
	pass


def Regress(mirror_rp):
	"""Bring mirror and inc directory back to regress_to_time

	Also affects the rdiff-backup-data directory, so Globals.rbdir
	should be set.  Regress should only work one step at a time
	(i.e. don't "regress" through two separate backup sets.  This
	function should be run locally to the rdiff-backup-data directory.

	"""
	inc_rpath = Globals.rbdir.append_path("increments")
	assert mirror_rp.index == () and inc_rpath.index == ()
	assert mirror_rp.isdir() and inc_rpath.isdir()
	assert mirror_rp.conn is inc_rpath.conn is Globals.local_connection
	set_regress_time()
	set_restore_times()
	ITR = rorpiter.IterTreeReducer(RegressITRB, [])
	for rf in iterate_meta_rfs(mirror_rp, inc_rpath): ITR(rf.index, rf)
	ITR.Finish()
	remove_rbdir_increments()

def set_regress_time():
	"""Set global regress_time to previous sucessful backup

	If there are two current_mirror increments, then the last one
	corresponds to a backup session that failed.

	"""
	global regress_time, unsuccessful_backup_time
	curmir_incs = restore.get_inclist(Globals.rbdir.append("current_mirror"))
	assert len(curmir_incs) == 2, \
		   "Found %s current_mirror flags, expected 2" % len(curmir_incs)
	inctimes = [inc.getinctime() for inc in curmir_incs]
	inctimes.sort()
	regress_time = inctimes[0]
	unsuccessful_backup_time = inctimes[-1]
	log.Log("Regressing to " + Time.timetopretty(regress_time), 4)

def set_restore_times():
	"""Set _rest_time and _mirror_time in the restore module

	_rest_time (restore time) corresponds to the last successful
	backup time.  _mirror_time is the unsuccessful backup time.

	"""
	restore._mirror_time = unsuccessful_backup_time
	restore._rest_time = regress_time

def remove_rbdir_increments():
	"""Delete the increments in the rdiff-backup-data directory"""
	old_current_mirror = None
	for filename in Globals.rbdir.listdir():
		rp = Globals.rbdir.append(filename)
		if rp.isincfile() and rp.getinctime() == unsuccessful_backup_time:
			if rp.getincbase_str() == "current_mirror": old_current_mirror = rp
			else:
				log.Log("Removing rdiff-backup-data increment " + rp.path, 5)
				rp.delete()
	if old_current_mirror:
		C.sync() # Sync first, since we are marking dest dir as good now
		old_current_mirror.delete()

def iterate_raw_rfs(mirror_rp, inc_rp):
	"""Iterate all RegressFile objects in mirror/inc directory"""
	root_rf = RegressFile(mirror_rp, inc_rp, restore.get_inclist(inc_rp))
	def helper(rf):
		yield rf
		if rf.mirror_rp.isdir() or rf.inc_rp.isdir():
			for sub_rf in rf.yield_sub_rfs():
				for sub_sub_rf in helper(sub_rf):
					yield sub_sub_rf
	return helper(root_rf)

def yield_metadata():
	"""Iterate rorps from metadata file, if any are available"""
	metadata_iter = metadata.GetMetadata_at_time(Globals.rbdir, regress_time)
	if metadata_iter: return metadata_iter
	log.Log.FatalError("No metadata for time %s found, cannot regress"
					   % Time.timetopretty(regress_time))

def iterate_meta_rfs(mirror_rp, inc_rp):
	"""Yield RegressFile objects with extra metadata information added

	Each RegressFile will have an extra object variable .metadata_rorp
	which will contain the metadata attributes of the mirror file at
	regress_time.

	"""
	raw_rfs = iterate_raw_rfs(mirror_rp, inc_rp)
	collated = rorpiter.Collate2Iters(raw_rfs, yield_metadata())
	for raw_rf, metadata_rorp in collated:
		if raw_rf:
			raw_rf.set_metadata_rorp(metadata_rorp)
			yield raw_rf
		else:
			log.Log("Warning, metadata file has entry for %s,\n"
					"but there are no associated files." %
					(metadata_rorp.get_indexpath(),), 2)
			yield RegressFile(mirror_rp.new_index(metadata_rorp.index),
							  inc_rp.new_index(metadata_rorp.index), ())


class RegressFile(restore.RestoreFile):
	"""Like RestoreFile but with metadata

	Hold mirror_rp and related incs, but also put metadata info for
	the mirror file at regress time in self.metadata_rorp.
	self.metadata_rorp is not set in this class.

	"""
	def __init__(self, mirror_rp, inc_rp, inc_list):
		restore.RestoreFile.__init__(self, mirror_rp, inc_rp, inc_list)
		self.set_regress_inc()
		
	def set_metadata_rorp(self, metadata_rorp):
		"""Set self.metadata_rorp, creating empty if given None"""
		if metadata_rorp: self.metadata_rorp = metadata_rorp
		else: self.metadata_rorp = rpath.RORPath(self.index)

	def isdir(self):
		"""Return true if regress needs before/after processing"""
		return ((self.metadata_rorp and self.metadata_rorp.isdir()) or
				(self.mirror_rp and self.mirror_rp.isdir()))

	def set_regress_inc(self):
		"""Set self.regress_inc to increment to be removed (or None)"""
		newer_incs = self.get_newer_incs()
		assert len(newer_incs) <= 1, "Too many recent increments"
		if newer_incs: self.regress_inc = newer_incs[0] # first is mirror_rp
		else: self.regress_inc = None


class RegressITRB(rorpiter.ITRBranch):
	"""Turn back state of dest directory (use with IterTreeReducer)

	The arguments to the ITR will be RegressFiles.  There are two main
	assumptions this procedure makes (besides those mentioned above):

	1.  The mirror_rp and the metadata_rorp equal_loose correctly iff
	    they contain the same data.  If this is the case, then the inc
	    file is unnecessary and we can delete it.

	2.  If the don't match, then applying the inc file will
	    successfully get us back to the previous state.

	Since the metadata file is required, the two above really only
	matter for regular files.

	"""
	def __init__(self):
		"""Just initialize some variables to None"""
		self.rf = None # will hold RegressFile applying to a directory

	def can_fast_process(self, index, rf):
		"""True if none of the rps is a directory"""
		return not rf.mirror_rp.isdir() and not rf.metadata_rorp.isdir()

	def fast_process(self, index, rf):
		"""Process when nothing is a directory"""
		if not rf.metadata_rorp.equal_loose(rf.mirror_rp):
			log.Log("Regressing file %s" %
					(rf.metadata_rorp.get_indexpath()), 5)
			if rf.metadata_rorp.isreg(): self.restore_orig_regfile(rf)
			else:
				if rf.mirror_rp.lstat(): rf.mirror_rp.delete()
				if rf.metadata_rorp.isspecial():
					robust.check_common_error(None, rpath.copy_with_attribs,
											  (rf.metadata_rorp, rf.mirror_rp))
				else: rpath.copy_with_attribs(rf.metadata_rorp, rf.mirror_rp)
		if rf.regress_inc:
			log.Log("Deleting increment " + rf.regress_inc.path, 5)
			rf.regress_inc.delete()

	def restore_orig_regfile(self, rf):
		"""Restore original regular file

		This is the trickiest case for avoiding information loss,
		because we don't want to delete the increment before the
		mirror is fully written.

		"""
		assert rf.metadata_rorp.isreg()
		if rf.mirror_rp.isreg():
			tf = TempFile.new(rf.mirror_rp)
			tf.write_from_fileobj(rf.get_restore_fp())
			rpath.copy_attribs(rf.metadata_rorp, tf)
			tf.fsync_with_dir() # make sure tf fully written before move
			rpath.rename(tf, rf.mirror_rp) # move is atomic
		else:
			if rf.mirror_rp.lstat(): rf.mirror_rp.delete()
			rf.mirror_rp.write_from_fileobj(rf.get_restore_fp())
			rpath.copy_attribs(rf.metadata_rorp, rf.mirror_rp)
		rf.mirror_rp.fsync_with_dir() # require move before inc delete

	def start_process(self, index, rf):
		"""Start processing directory"""
		if rf.metadata_rorp.isdir():
			# make sure mirror is a readable dir
			if not rf.mirror_rp.isdir():
				if rf.mirror_rp.lstat(): rf.mirror_rp.delete()
				rf.mirror_rp.mkdir()
			if Globals.change_permissions and not rf.mirror_rp.hasfullperms():
				rf.mirror_rp.chmod(0700)
		self.rf = rf

	def end_process(self):
		"""Finish processing a directory"""
		rf = self.rf
		if rf.metadata_rorp.isdir():
			if rf.mirror_rp.isdir():
				rf.mirror_rp.setdata()
				if not rf.metadata_rorp.equal_loose(rf.mirror_rp):
					log.Log("Regressing attributes of " + rf.mirror_rp.path, 5)
					rpath.copy_attribs(rf.metadata_rorp, rf.mirror_rp)
			else:
				rf.mirror_rp.delete()
				log.Log("Regressing file " + rf.mirror_rp.path, 5)
				rpath.copy_with_attribs(rf.metadata_rorp, rf.mirror_rp)
		else: # replacing a dir with some other kind of file
			assert rf.mirror_rp.isdir()
			log.Log("Replacing directory " + rf.mirror_rp.path, 5)
			if rf.metadata_rorp.isreg(): self.restore_orig_regfile(rf)
			else:
				rf.mirror_rp.delete()
				rpath.copy_with_attribs(rf.metadata_rorp, rf.mirror_rp)
		if rf.regress_inc:
			log.Log("Deleting increment " + rf.regress_inc.path, 5)
			rf.regress_inc.delete()
