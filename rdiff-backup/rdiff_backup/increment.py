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

"""Provides functions and *ITR classes, for writing increment files"""

import traceback
from log import Log
import Globals, Time, MiscStats, rorpiter, TempFile, robust, \
	   statistics, rpath, static, lazy, Rdiff, Hardlink


def Increment_action(new, mirror, incpref):
	"""Main file incrementing function, returns robust.Action

	new is the file on the active partition,
	mirror is the mirrored file from the last backup,
	incpref is the prefix of the increment file.

	This function basically moves the information about the mirror
	file to incpref.

	The returned robust.Action when executed should return the name
	of the incfile, or None if none was created.

	"""
	if not (new and new.lstat() or mirror.lstat()):
		return robust.null_action # Files deleted in meantime, do nothing

	Log("Incrementing mirror file " + mirror.path, 5)
	if ((new and new.isdir()) or mirror.isdir()) and not incpref.isdir():
		incpref.mkdir()

	if not mirror.lstat(): return makemissing_action(incpref)
	elif mirror.isdir(): return makedir_action(mirror, incpref)
	elif new.isreg() and mirror.isreg():
		return makediff_action(new, mirror, incpref)
	else: return makesnapshot_action(mirror, incpref)

def Increment(new, mirror, incpref):
	return Increment_action(new, mirror, incpref).execute()

def makemissing_action(incpref):
	"""Signify that mirror file was missing"""
	def final(init_val):
		incrp = get_inc_ext(incpref, "missing")
		incrp.touch()
		return incrp
	return robust.Action(None, final, None)

def makesnapshot_action(mirror, incpref):
	"""Copy mirror to incfile, since new is quite different"""
	if (mirror.isreg() and Globals.compression and
		not Globals.no_compression_regexp.match(mirror.path)):
		snapshotrp = get_inc_ext(incpref, "snapshot.gz")
		return robust.copy_with_attribs_action(mirror, snapshotrp, 1)
	else:
		snapshotrp = get_inc_ext(incpref, "snapshot")
		return robust.copy_with_attribs_action(mirror, snapshotrp, None)

def makediff_action(new, mirror, incpref):
	"""Make incfile which is a diff new -> mirror"""
	if (Globals.compression and
		not Globals.no_compression_regexp.match(mirror.path)):
		diff = get_inc_ext(incpref, "diff.gz")
		compress = 1
	else: 
		diff = get_inc_ext(incpref, "diff")
		compress = None

	diff_tf = TempFile.new(diff)
	def init():
		Rdiff.write_delta(new, mirror, diff_tf, compress)
		rpath.copy_attribs(mirror, diff_tf)
		return diff
	return robust.make_tf_robustaction(init, diff_tf, diff)

def makedir_action(mirrordir, incpref):
	"""Make file indicating directory mirrordir has changed"""
	dirsign = get_inc_ext(incpref, "dir")
	tf = TempFile.new(dirsign)
	def init():
		tf.touch()
		rpath.copy_attribs(mirrordir, tf)
		return dirsign
	return robust.make_tf_robustaction(init, tf, dirsign)

def get_inc(rp, time, typestr):
	"""Return increment like rp but with time and typestr suffixes"""
	addtostr = lambda s: "%s.%s.%s" % (s, Time.timetostring(time), typestr)
	if rp.index:
		incrp = rp.__class__(rp.conn, rp.base, rp.index[:-1] +
							 (addtostr(rp.index[-1]),))
	else: incrp = rp.__class__(rp.conn, addtostr(rp.base), rp.index)
	if Globals.quoting_enabled: incrp.quote_path()
	return incrp

def get_inc_ext(rp, typestr):
	"""Return increment with specified type and correct time

	If the file exists, then probably a previous backup has been
	aborted.  We then keep asking FindTime to get a time later
	than the one that already has an inc file.

	"""
	inctime = 0
	while 1:
		#inctime = robust.Resume.FindTime(rp.index, inctime)
		inctime = Time.prevtime
		incrp = get_inc(rp, inctime, typestr)
		if not incrp.lstat(): break
		else:
			assert 0, "Inc file already present"
	return incrp


class IncrementITRB(statistics.ITRB):
	"""Patch and increment mirror directory

	This has to be an ITR because directories that have files in them
	changed are flagged with an increment marker.  There are four
	possibilities as to the order:

	1.  Normal file -> Normal file:  right away
	2.  Directory -> Directory:  wait until files in the directory
	    are processed, as we won't know whether to add a marker
		until the end.
	3.  Normal file -> Directory:  right away, so later files will
	    have a directory to go into.
	4.  Directory -> Normal file:  Wait until the end, so we can
	    process all the files in the directory.	

	"""
	# Iff true, mirror file was a directory
	mirror_isdirectory = None
	# If set, what the directory on the mirror side will be replaced with
	directory_replacement = None
	# True iff there has been some change at this level or lower (used
	# for marking directories to be flagged)
	changed = None
	# Holds the RPath of the created increment file, if any
	incrp = None

	def __init__(self, inc_rpath):
		"""Set inc_rpath, an rpath of the base of the tree"""
		self.inc_rpath = inc_rpath
		statistics.ITRB.__init__(self)

	def start_process(self, index, diff_rorp, dsrp):
		"""Initial processing of file

		diff_rorp is the RORPath of the diff from the remote side, and
		dsrp is the local file to be incremented

		"""
		self.start_stats(dsrp)
		incpref = self.inc_rpath.new_index(index)
		if Globals.quoting_enabled: incpref.quote_path()
		if dsrp.isdir():
			self.init_dir(dsrp, diff_rorp, incpref)
			self.mirror_isdirectory = 1
		else: self.init_non_dir(dsrp, diff_rorp, incpref)
		self.setvals(diff_rorp, dsrp, incpref)
		
	def override_changed(self):
		"""Set changed flag to true

		This is used only at the top level of a backup, to make sure
		that a marker is created recording every backup session.

		"""
		self.changed = 1

	def setvals(self, diff_rorp, dsrp, incpref):
		"""Record given values in state dict since in directory

		We don't do these earlier in case of a problem inside the
		init_* functions.  Index isn't given because it is done by the
		superclass.

		"""
		self.diff_rorp = diff_rorp
		self.dsrp = dsrp
		self.incpref = incpref

	def init_dir(self, dsrp, diff_rorp, incpref):
		"""Process a directory (initial pass)

		If the directory is changing into a normal file, we need to
		save the normal file data in a temp file, and then create the
		real file once we are done with everything inside the
		directory.

		"""
		if not (incpref.lstat() and incpref.isdir()): incpref.mkdir()
		if diff_rorp and diff_rorp.isreg() and diff_rorp.file:
			tf = TempFile.new(dsrp)
			def init():
				rpath.copy_with_attribs(diff_rorp, tf)
				tf.set_attached_filetype(diff_rorp.get_attached_filetype())
			def error(exc, ran_init, init_val): tf.delete()
			robust.Action(init, None, error).execute()
			self.directory_replacement = tf

	def init_non_dir(self, dsrp, diff_rorp, incpref):
		"""Process a non directory file (initial pass)"""
		if not diff_rorp: return # no diff, so no change necessary
		if diff_rorp.isreg() and (dsrp.isreg() or diff_rorp.isflaglinked()):
			# Write updated mirror to temp file so we can compute
			# reverse diff locally
			mirror_tf = TempFile.new(dsrp)
			old_dsrp_tf = TempFile.new(dsrp)
			def init_thunk():
				if diff_rorp.isflaglinked():
					Hardlink.link_rp(diff_rorp, mirror_tf, dsrp)
				else: Rdiff.patch_with_attribs_action(dsrp, diff_rorp,
													  mirror_tf).execute()
				self.incrp = Increment_action(mirror_tf, dsrp,
												  incpref).execute()
				if dsrp.lstat(): rpath.rename(dsrp, old_dsrp_tf)
				mirror_tf.rename(dsrp)

			def final(init_val): old_dsrp_tf.delete()
			def error(exc, ran_init, init_val):
				if ran_init: old_dsrp_tf.delete() # everything is fine
				else: # restore to previous state
					if old_dsrp_tf.lstat(): old_dsrp_tf.rename(dsrp)
					if self.incrp: self.incrp.delete()
					mirror_tf.delete()

			robust.Action(init_thunk, final, error).execute()
		else: self.incrp = robust.chain(
			Increment_action(diff_rorp, dsrp, incpref),
			rorpiter.patchonce_action(None, dsrp, diff_rorp)).execute()[0]

		self.changed = 1

	def end_process(self):
		"""Do final work when leaving a tree (directory)"""
		diff_rorp, dsrp, incpref = self.diff_rorp, self.dsrp, self.incpref
		if (self.mirror_isdirectory and (diff_rorp or self.changed)
			or self.directory_replacement):
			if self.directory_replacement:
				tf = self.directory_replacement
				self.incrp = robust.chain(
					Increment_action(tf, dsrp, incpref),
					rorpiter.patchonce_action(None, dsrp, tf)).execute()[0]
				tf.delete()
			else:
				self.incrp = Increment(diff_rorp, dsrp, incpref)
				if diff_rorp:
					rorpiter.patchonce_action(None, dsrp, diff_rorp).execute()

		self.end_stats(diff_rorp, dsrp, self.incrp)
		if self.mirror_isdirectory or dsrp.isdir():
			MiscStats.write_dir_stats_line(self, dsrp.index)

	def can_fast_process(self, index, diff_rorp, dsrp):
		"""True if there is no change in file and is just a leaf"""
		return not diff_rorp and dsrp.isreg()

	def fast_process(self, index, diff_rorp, dsrp):
		"""Just update statistics"""
		statistics.ITRB.fast_process(self, dsrp)

	def branch_process(self, branch):
		"""Update statistics, and the has_changed flag if change in branch"""
		if Globals.sleep_ratio is not None: Time.sleep(Globals.sleep_ratio)
		if branch.changed: self.changed = 1	
		self.add_file_stats(branch)


class MirrorITRB(statistics.ITRB):
	"""Like IncrementITR, but only patch mirror directory, don't increment"""
	# This is always None since no increments will be created
	incrp = None
	def __init__(self, inc_rpath):
		"""Set inc_rpath, an rpath of the base of the inc tree"""
		self.inc_rpath = inc_rpath
		statistics.ITRB.__init__(self)

	def start_process(self, index, diff_rorp, mirror_dsrp):
		"""Initialize statistics and do actual writing to mirror"""
		self.start_stats(mirror_dsrp)
		if (diff_rorp and diff_rorp.isdir() or
			not diff_rorp and mirror_dsrp.isdir()):
			# mirror_dsrp will end up as directory, update attribs later
			if not diff_rorp: diff_rorp = mirror_dsrp.get_rorpath()
			if not mirror_dsrp.isdir():
				mirror_dsrp.delete()
				mirror_dsrp.mkdir()
		elif diff_rorp and not diff_rorp.isplaceholder():
			rorpiter.patchonce_action(None, mirror_dsrp, diff_rorp).execute()

		self.incpref = self.inc_rpath.new_index(index)
		self.diff_rorp, self.mirror_dsrp = diff_rorp, mirror_dsrp

	def end_process(self):
		"""Update statistics when leaving"""
		self.end_stats(self.diff_rorp, self.mirror_dsrp)
		if self.mirror_dsrp.isdir():
			rpath.copy_attribs(self.diff_rorp, self.mirror_dsrp)
			MiscStats.write_dir_stats_line(self, self.mirror_dsrp.index)

	def can_fast_process(self, index, diff_rorp, mirror_dsrp):
		"""True if there is no change in file and it is just a leaf"""
		return not diff_rorp and mirror_dsrp.isreg()

	def fast_process(self, index, diff_rorp, mirror_dsrp):
		"""Just update statistics"""
		statistics.ITRB.fast_process(self, mirror_dsrp)

	def branch_process(self, branch):
		"""Update statistics with subdirectory results"""
		if Globals.sleep_ratio is not None: Time.sleep(Globals.sleep_ratio)
		self.add_file_stats(branch)



