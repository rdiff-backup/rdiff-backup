execfile("filename_mapping.py")

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

		This function basically moves mirror -> incpref.

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
		Inc.Increment_action(new, mirror, incpref).execute()

	def makemissing_action(incpref):
		"""Signify that mirror file was missing"""
		return RobustAction(lambda: None,
							Inc.get_inc_ext(incpref, "missing").touch,
							lambda exp: None)
		
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
			return Robust.chain([Rdiff.write_delta_action(new, mirror,
														  diff, 1),
								 Robust.copy_attribs_action(mirror, diff)])
		else: 
			diff = Inc.get_inc_ext(incpref, "diff")
			return Robust.chain([Rdiff.write_delta_action(new, mirror,
														  diff, None),
								 Robust.copy_attribs_action(mirror, diff)])

	def makedir_action(mirrordir, incpref):
		"""Make file indicating directory mirrordir has changed"""
		dirsign = Inc.get_inc_ext(incpref, "dir")
		def final():
			dirsign.touch()
			RPath.copy_attribs(mirrordir, dirsign)
		return RobustAction(lambda: None, final, dirsign.delete)

	def get_inc_ext(rp, typestr):
		"""Return RPath/DSRPath like rp but with inc/time extension

		If the file exists, then probably a previous backup has been
		aborted.  We then keep asking FindTime to get a time later
		than the one that already has an inc file.

		"""
		def get_newinc(timestr):
			"""Get new increment rp with given time suffix"""
			addtostr = lambda s: "%s.%s.%s" % (s, timestr, typestr)
			if rp.index:
				incrp = rp.__class__(rp.conn, rp.base, rp.index[:-1] +
									 (addtostr(rp.index[-1]),))
			else: incrp = rp.__class__(rp.conn, addtostr(rp.base), rp.index)
			if Globals.quoting_enabled: incrp.quote_path()
			return incrp
			
		inctime = 0
		while 1:
			inctime = Resume.FindTime(rp.index, inctime)
			incrp = get_newinc(Time.timetostring(inctime))
			if not incrp.lstat(): break
		Inc._inc_file = incrp
		return incrp

MakeStatic(Inc)


class IncrementITR(IterTreeReducer):
	"""Patch and increment iterator of increment triples

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
	directory, directory_replacement = None, None
	changed = None

	def __init__(self, inc_rpath):
		"""Set inc_rpath, an rpath of the base of the tree"""
		self.inc_rpath = inc_rpath
		IterTreeReducer.__init__(self, inc_rpath)

	def start_process(self, index, diff_rorp, dsrp):
		"""Initial processing of file

		diff_rorp is the RORPath of the diff from the remote side, and
		dsrp is the local file to be incremented

		"""
		self.init_statistics(diff_rorp, dsrp)
		incpref = self.inc_rpath.new_index(index)
		if Globals.quoting_enabled: incpref.quote_path()
		if dsrp.isdir():
			self.init_dir(dsrp, diff_rorp, incpref)
			self.setvals(diff_rorp, dsrp, incpref)
		else: self.init_non_dir(dsrp, diff_rorp, incpref)

	def init_statistics(self, diff_rorp, dsrp):
		"""Set initial values for various statistics

		These refer to the old mirror or to new increment files.  Note
		that changed_file_size could be bigger than total_file_size.
		The other statistic, increment_file_size, is set later when we
		have that information.

		"""
		if dsrp.lstat():
			self.total_files = 1
			self.total_file_size = dsrp.getsize()
		else: self.total_files = self.total_file_size = 0
		if diff_rorp:
			self.changed_files = 1
			if dsrp.lstat(): self.changed_file_size = dsrp.getsize()
			else: self.changed_file_size = 0
		else: self.changed_files = self.changed_file_size = 0
		self.increment_file_size = 0

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
		self.directory = 1
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
			RPathStatic.copy_with_attribs(diff_rorp, tf)
			tf.set_attached_filetype(diff_rorp.get_attached_filetype())
			self.directory_replacement = tf

	def init_non_dir(self, dsrp, diff_rorp, incpref):
		"""Process a non directory file (initial pass)"""
		if not diff_rorp: return # no diff, so no change necessary
		if diff_rorp.isreg() and (dsrp.isreg() or diff_rorp.isflaglinked()):
			tf = TempFileManager.new(dsrp)
			def init_thunk():
				if diff_rorp.isflaglinked():
					Hardlink.link_rp(diff_rorp, tf, dsrp)
				else: Rdiff.patch_with_attribs_action(dsrp, diff_rorp,
													  tf).execute()
				Inc.Increment_action(tf, dsrp, incpref).execute()
			Robust.make_tf_robustaction(init_thunk, (tf,), (dsrp,)).execute()
		else:
			Robust.chain([Inc.Increment_action(diff_rorp, dsrp, incpref),
						  RORPIter.patchonce_action(None, dsrp, diff_rorp)]
						 ).execute()

		self.increment_file_size += ((Inc._inc_file and Inc._inc_file.lstat()
									  and Inc._inc_file.getsize()) or 0)
		self.changed = 1

	def end_process(self):
		"""Do final work when leaving a tree (directory)"""
		if not self.directory: return
		diff_rorp, dsrp, incpref = self.diff_rorp, self.dsrp, self.incpref
		if not diff_rorp and not self.changed: return

		if self.directory_replacement:
			tf = self.directory_replacement
			Inc.Increment(tf, dsrp, incpref)
			RORPIter.patchonce_action(None, dsrp, tf).execute()
			tf.delete()
		else:
			Inc.Increment(diff_rorp, dsrp, incpref)
			if diff_rorp:
				RORPIter.patchonce_action(None, dsrp, diff_rorp).execute()

		self.increment_file_size += ((Inc._inc_file and Inc._inc_file.lstat()
									  and Inc._inc_file.getsize()) or 0)
		self.write_statistics()

	def write_statistics(self):
		"""Write the accumulated totals into file in inc directory"""
		if not self.incpref.isdir(): return # only write for directories
		statrp = Inc.get_inc_ext(self.incpref.append("directory_statistics"),
								 "data")
		tf = TempFileManager.new(statrp)
		def init_thunk():
			fp = tf.open("w")
			fp.write("TotalFiles %d\n" % self.total_files)
			fp.write("TotalFileSize %d\n" % self.total_file_size)
			fp.write("ChangedFiles %d\n" % self.changed_files)
			fp.write("ChangedFileSize %d\n" % self.changed_file_size)
			fp.write("IncrementFileSize %d\n" % self.increment_file_size)
			fp.close()
		Robust.make_tf_robustaction(init_thunk, (tf,), (statrp,)).execute()

	def branch_process(self, subinstance):
		"""Update statistics, and the has_changed flag if change in branch"""
		if subinstance.changed: self.changed = 1	

		self.total_files += subinstance.total_files
		self.total_file_size += subinstance.total_file_size
		self.changed_files += subinstance.changed_files
		self.changed_file_size += subinstance.changed_file_size
		self.increment_file_size += subinstance.increment_file_size
