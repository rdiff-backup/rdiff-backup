from __future__ import generators
from manage import *
from rpath import *

#######################################################################
#
# filelist - Some routines that help with operations over files listed
#            in standard input instead of over whole directories.
#

class FilelistError(Exception): pass

class Filelist:
	"""Many of these methods have analogs in highlevel.py"""
	def File2Iter(fp, baserp):
		"""Convert file obj with one pathname per line into rpiter

		Closes fp when done.  Given files are added to baserp.

		"""
		while 1:
			line = fp.readline()
			if not line: break
			if line[-1] == "\n": line = line[:-1] # strip trailing newline
			if not line: continue # skip blank lines
			elif line[0] == "/": raise FilelistError(
				"Read in absolute file name %s." % line)
			yield baserp.append(line)
		assert not fp.close(), "Error closing filelist fp"

	def Mirror(src_rpath, dest_rpath, rpiter):
		"""Copy files in fileiter from src_rpath to dest_rpath"""
		sigiter = dest_rpath.conn.Filelist.get_sigs(dest_rpath, rpiter)
		diffiter = Filelist.get_diffs(src_rpath, sigiter)
		dest_rpath.conn.Filelist.patch(dest_rpath, diffiter)
		dest_rpath.setdata()

	def Mirror_and_increment(src_rpath, dest_rpath, inc_rpath):
		"""Mirror + put increment in tree based at inc_rpath"""
		sigiter = dest_rpath.conn.Filelist.get_sigs(dest_rpath, rpiter)
		diffiter = Filelist.get_diffs(src_rpath, sigiter)
		dest_rpath.conn.Filelist.patch_and_increment(dest_rpath, diffiter,
													 inc_rpath)
		dest_rpath.setdata()

	def get_sigs(dest_rpbase, rpiter):
		"""Get signatures of file analogs in rpiter

		This is meant to be run on the destination side.  Only the
		extention part of the rps in rpiter will be used; the base is
		ignored.

		"""
		def dest_iter(src_iter):
			for src_rp in src_iter: yield dest_rpbase.new_index(src_rp.index)
		return RORPIter.Signatures(dest_iter())

	def get_diffs(src_rpbase, sigiter):
		"""Get diffs based on sigiter and files in src_rpbase

		This should be run on the local side.

		"""
		for sig_rorp in sigiter:
			new_rp = src_rpbase.new_index(sig_rorp.index)
			yield RORPIter.diffonce(sig_rorp, new_rp)

	def patch(dest_rpbase, diffiter):
		"""Process diffs in diffiter and update files in dest_rbpase.

		Run remotely.

		"""
		for diff_rorp in diffiter:
			basisrp = dest_rpbase.new_index(diff_rorp.index)
			if basisrp.lstat(): Filelist.make_subdirs(basisrp)
			Log("Processing %s" % basisrp.path, 7)
			RORPIter.patchonce(dest_rpbase, basisrp, diff_rorp)

	def patch_and_increment(dest_rpbase, diffiter, inc_rpbase):
		"""Apply diffs in diffiter to dest_rpbase, and increment to inc_rpbase

		Also to be run remotely.

		"""
		for diff_rorp in diffiter:
			basisrp = dest_rpbase.new_index(diff_rorp.index)
			if diff_rorp.lstat(): Filelist.make_subdirs(basisrp)
			Log("Processing %s" % basisrp.path, 7)
			# XXX This isn't done yet...

	def make_subdirs(rpath):
		"""Make sure that all the directories under the rpath exist

		This function doesn't try to get the permissions right on the
		underlying directories, just do the minimum to make sure the
		file can be created.

		"""
		dirname = rpath.dirsplit()[0]
		if dirname == '.' or dirname == '': return
		dir_rp = RPath(rpath.conn, dirname)
		Filelist.make_subdirs(dir_rp)
		if not dir_rp.lstat(): dir_rp.mkdir()


MakeStatic(Filelist)
