import traceback
execfile("statistics.py")

#######################################################################
#
# increment - Provides Inc class, which writes increment files
#
# This code is what writes files ending in .diff, .snapshot, etc.
#

class Inc:
	"""Class containing increment functions"""
	# This is a hack.  _inc_file holds the dsrp of the latest
	# increment file created, to be used in IncrementITR for
	# statistics purposes.  It should be given directly to the ITR
	# object but there didn't seem to be a good way to pass it out.
	_inc_file = None

	def Increment_action(new, mirror, incpref):
		"""Main file incrementing function, returns RobustAction

		new is the file on the active partition,
		mirror is the mirrored file from the last backup,
		incpref is the prefix of the increment file.

		This function basically moves the information about the mirror
		file to incpref.

		The returned RobustAction when executed should return the name
		of the incfile, or None if none was created.

		"""
		if not (new and new.lstat() or mirror.lstat()):
			return Robust.null_action # Files deleted in meantime, do nothing

		Log("Incrementing mirror file " + mirror.path, 5)
		if ((new and new.isdir()) or mirror.isdir()) and not incpref.isdir():
			incpref.mkdir()

		if not mirror.lstat(): return Inc.makemissing_action(incpref)
		elif mirror.isdir(): return Inc.makedir_action(mirror, incpref)
		elif new.isreg() and mirror.isreg():
			return Inc.makediff_action(new, mirror, incpref)
		else: return Inc.makesnapshot_action(mirror, incpref)

	def Increment(new, mirror, incpref):
		return Inc.Increment_action(new, mirror, incpref).execute()

	def makemissing_action(incpref):
		"""Signify that mirror file was missing"""
		def final(init_val):
			incrp = Inc.get_inc_ext(incpref, "missing")
			incrp.touch()
			return incrp
		return RobustAction(None, final, None)
		
	def makesnapshot_action(mirror, incpref):
		"""Copy mirror to incfile, since new is quite different"""
		if (mirror.isreg() and Globals.compression and
			not Globals.no_compression_regexp.match(mirror.path)):
			snapshotrp = Inc.get_inc_ext(incpref, "snapshot.gz")
			return Robust.copy_with_attribs_action(mirror, snapshotrp, 1)
		else:
			snapshotrp = Inc.get_inc_ext(incpref, "snapshot")
			return Robust.copy_with_attribs_action(mirror, snapshotrp, None)

	def makediff_action(new, mirror, incpref):
		"""Make incfile which is a diff new -> mirror"""
		if (Globals.compression and
			not Globals.no_compression_regexp.match(mirror.path)):
			diff = Inc.get_inc_ext(incpref, "diff.gz")
			compress = 1
		else: 
			diff = Inc.get_inc_ext(incpref, "diff")
			compress = None
			
		diff_tf = TempFileManager.new(diff)
		sig_tf = TempFileManager.new(mirror, None)
		def init():
			Rdiff.write_delta(new, mirror, diff_tf, compress, sig_tf)
			RPath.copy_attribs(mirror, diff_tf)
			return diff
		return Robust.make_tf_robustaction(init, (diff_tf, sig_tf),
										   (diff, None))

	def makedir_action(mirrordir, incpref):
		"""Make file indicating directory mirrordir has changed"""
		dirsign = Inc.get_inc_ext(incpref, "dir")
		tf = TempFileManager.new(dirsign)
		def init():
			tf.touch()
			RPath.copy_attribs(mirrordir, tf)
			return dirsign
		return Robust.make_tf_robustaction(init, tf, dirsign)

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
			inctime = Resume.FindTime(rp.index, inctime)
			incrp = Inc.get_inc(rp, inctime, typestr)
			if not incrp.lstat(): break
		Inc._inc_file = incrp
		return incrp

MakeStatic(Inc)


class IncrementITR(ErrorITR, StatsITR):
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

	Remember this object needs to be pickable.
	
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
		StatsITR.__init__(self, inc_rpath)

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
			tf = TempFileManager.new(dsrp)
			def init():
				RPathStatic.copy_with_attribs(diff_rorp, tf)
				tf.set_attached_filetype(diff_rorp.get_attached_filetype())
			def error(exc, ran_init, init_val): tf.delete()
			RobustAction(init, None, error).execute()
			self.directory_replacement = tf

	def init_non_dir(self, dsrp, diff_rorp, incpref):
		"""Process a non directory file (initial pass)"""
		if not diff_rorp: return # no diff, so no change necessary
		if diff_rorp.isreg() and (dsrp.isreg() or diff_rorp.isflaglinked()):
			# Write updated mirror to temp file so we can compute
			# reverse diff locally
			mirror_tf = TempFileManager.new(dsrp)
			def init_thunk():
				if diff_rorp.isflaglinked():
					Hardlink.link_rp(diff_rorp, mirror_tf, dsrp)
				else: Rdiff.patch_with_attribs_action(dsrp, diff_rorp,
													  mirror_tf).execute()
				self.incrp = Inc.Increment_action(mirror_tf, dsrp,
												  incpref).execute()
			def final(init_val): mirror_tf.rename(dsrp)
			def error(exc, ran_init, init_val): mirror_tf.delete()
			RobustAction(init_thunk, final, error).execute()
		else: self.incrp = Robust.chain(
			Inc.Increment_action(diff_rorp, dsrp, incpref),
			RORPIter.patchonce_action(None, dsrp, diff_rorp)).execute()[0]

		self.changed = 1

	def end_process(self):
		"""Do final work when leaving a tree (directory)"""
		diff_rorp, dsrp, incpref = self.diff_rorp, self.dsrp, self.incpref
		if self.mirror_isdirectory and (diff_rorp or self.changed):
			if self.directory_replacement:
				tf = self.directory_replacement
				self.incrp = Robust.chain(
					Inc.Increment_action(tf, dsrp, incpref),
					RORPIter.patchonce_action(None, dsrp, tf)).execute()[0]
				tf.delete()
			else:
				self.incrp = Inc.Increment(diff_rorp, dsrp, incpref)
				if diff_rorp:
					RORPIter.patchonce_action(None, dsrp, diff_rorp).execute()

		self.end_stats(diff_rorp, dsrp, self.incrp)
		if self.mirror_isdirectory or dsrp.isdir():
			Stats.write_dir_stats_line(self, dsrp.index)

	def branch_process(self, subinstance):
		"""Update statistics, and the has_changed flag if change in branch"""
		if subinstance.changed: self.changed = 1	
		self.add_file_stats(subinstance)


class MirrorITR(ErrorITR, StatsITR):
	"""Like IncrementITR, but only patch mirror directory, don't increment"""
	# This is always None since no increments will be created
	incrp = None
	def __init__(self, inc_rpath):
		"""Set inc_rpath, an rpath of the base of the inc tree"""
		self.inc_rpath = inc_rpath
		StatsITR.__init__(self, inc_rpath)

	def start_process(self, index, diff_rorp, mirror_dsrp):
		"""Initialize statistics, do actual writing to mirror"""
		self.start_stats(mirror_dsrp)
		if diff_rorp and not diff_rorp.isplaceholder():
			RORPIter.patchonce_action(None, mirror_dsrp, diff_rorp).execute()

		self.incpref = self.inc_rpath.new_index(index)
		self.diff_rorp, self.mirror_dsrp = diff_rorp, mirror_dsrp

	def end_process(self):
		"""Update statistics when leaving"""
		self.end_stats(self.diff_rorp, self.mirror_dsrp)
		if self.mirror_dsrp.isdir():
			Stats.write_dir_stats_line(self, self.mirror_dsrp.index)

	def branch_process(self, subinstance):
		"""Update statistics with subdirectory results"""
		self.add_file_stats(subinstance)
