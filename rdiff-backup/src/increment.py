execfile("destructive_stepping.py")

#######################################################################
#
# increment - Provides Inc class, which writes increment files
#
# This code is what writes files ending in .diff, .snapshot, etc.
#

class Inc:
	"""Class containing increment functions"""
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
				return rp.__class__(rp.conn, rp.base, rp.index[:-1] +
									(addtostr(rp.index[-1]),))
			else: return rp.__class__(rp.conn, addtostr(rp.base), rp.index)

		inctime = 0
		while 1:
			inctime = Resume.FindTime(rp.index, inctime)
			incrp = get_newinc(Time.timetostring(inctime))
			if not incrp.lstat(): return incrp

	def make_patch_increment_ITR(inc_rpath, initial_state = None):
		"""Return IterTreeReducer that patches and increments

		This has to be an ITR because directories that have files in
		them changed are flagged with an increment marker.  There are
		four possibilities as to the order:

		1.  Normal file -> Normal file:  right away
		2.  Directory -> Directory:  wait until files in the directory
		    are processed, as we won't know whether to add a marker
		    until the end.
		3.  Normal file -> Directory:  right away, so later files will
		    have a directory to go into.
		4.  Directory -> Normal file:  Wait until the end, so we can
		    process all the files in the directory.

		"""
		def base_init(indexed_tuple):
			"""Patch if appropriate, return (a,b) tuple

			a is true if found directory and thus didn't take action
			
			if a is false, b is true if some changes were made

			if a is true, b is the rp of a temporary file used to hold
			the diff_rorp's data (for dir -> normal file change), and
			false if none was necessary.

			"""
			diff_rorp, dsrp = indexed_tuple
			incpref = inc_rpath.new_index(indexed_tuple.index)
			if dsrp.isdir(): return init_dir(dsrp, diff_rorp, incpref)
			else: return init_non_dir(dsrp, diff_rorp, incpref)

		def init_dir(dsrp, diff_rorp, incpref):
			"""Initial processing of a directory

			Make the corresponding directory right away, but wait
			until the end to write the replacement.  However, if the
			diff_rorp contains data, we must write it locally before
			continuing, or else that data will be lost in the stream.

			"""
			if not (incpref.lstat() and incpref.isdir()): incpref.mkdir()
			if diff_rorp and diff_rorp.isreg() and diff_rorp.file:
				tf = TempFileManager.new(dsrp)
				RPathStatic.copy_with_attribs(diff_rorp, tf)
				tf.set_attached_filetype(diff_rorp.get_attached_filetype())
				return (1, tf)
			else: return (1, None)

		def init_non_dir(dsrp, diff_rorp, incpref):
			"""Initial processing of non-directory

			If a reverse diff is called for it is generated by apply
			the forwards diff first on a temporary file.

			"""
			if diff_rorp:
				if diff_rorp.isreg() and (dsrp.isreg() or
										  diff_rorp.isflaglinked()):
					tf = TempFileManager.new(dsrp)
					def init_thunk():
						if diff_rorp.isflaglinked():
							Hardlink.link_rp(diff_rorp, tf, dsrp)
						else: Rdiff.patch_with_attribs_action(dsrp, diff_rorp,
															  tf).execute()
						Inc.Increment_action(tf, dsrp, incpref).execute()
					Robust.make_tf_robustaction(init_thunk, (tf,),
												(dsrp,)).execute()
				else:
					Robust.chain([Inc.Increment_action(diff_rorp, dsrp,
													   incpref),
								  RORPIter.patchonce_action(
						             None, dsrp, diff_rorp)]).execute()
				return (None, 1)
			return (None, None)

		def base_final(base_tuple, base_init_tuple, changed):
			"""Patch directory if not done, return true iff made change"""
			if base_init_tuple[0]: # was directory
				diff_rorp, dsrp = base_tuple
				if changed or diff_rorp:
					if base_init_tuple[1]: diff_rorp = base_init_tuple[1]
					Inc.Increment(diff_rorp, dsrp,
								  inc_rpath.new_index(base_tuple.index))
					if diff_rorp:
						RORPIter.patchonce_action(None, dsrp,
												  diff_rorp).execute()
						if isinstance(diff_rorp, TempFile): diff_rorp.delete()
					return 1
				return None
			else: # changed iff base_init_tuple says it was
				return base_init_tuple[1]

		return IterTreeReducer(base_init, lambda x,y: x or y, None,
							   base_final, initial_state)

MakeStatic(Inc)
