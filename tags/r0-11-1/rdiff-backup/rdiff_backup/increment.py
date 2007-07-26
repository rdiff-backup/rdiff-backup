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

import Globals, Time, rpath, Rdiff, log, statistics


def Increment(new, mirror, incpref):
	"""Main file incrementing function, returns inc file created

	new is the file on the active partition,
	mirror is the mirrored file from the last backup,
	incpref is the prefix of the increment file.

	This function basically moves the information about the mirror
	file to incpref.

	"""
	if not (new and new.lstat() or mirror.lstat()):
		return None # Files deleted in meantime, do nothing

	log.Log("Incrementing mirror file " + mirror.path, 5)
	if ((new and new.isdir()) or mirror.isdir()) and not incpref.isdir():
		incpref.mkdir()

	if not mirror.lstat(): incrp = makemissing(incpref)
	elif mirror.isdir(): incrp = makedir(mirror, incpref)
	elif new.isreg() and mirror.isreg():
		incrp = makediff(new, mirror, incpref)
	else: incrp = makesnapshot(mirror, incpref)
	statistics.process_increment(incrp)
	return incrp

def makemissing(incpref):
	"""Signify that mirror file was missing"""
	incrp = get_inc_ext(incpref, "missing")
	incrp.touch()
	return incrp

def iscompressed(mirror):
	"""Return true if mirror's increments should be compressed"""
	return (Globals.compression and
			not Globals.no_compression_regexp.match(mirror.path))

def makesnapshot(mirror, incpref):
	"""Copy mirror to incfile, since new is quite different"""
	compress = iscompressed(mirror)
	if compress: snapshotrp = get_inc_ext(incpref, "snapshot.gz")
	else: snapshotrp = get_inc_ext(incpref, "snapshot")
	rpath.copy_with_attribs(mirror, snapshotrp, compress)
	return snapshotrp

def makediff(new, mirror, incpref):
	"""Make incfile which is a diff new -> mirror"""
	compress = iscompressed(mirror)
	if compress: diff = get_inc_ext(incpref, "diff.gz")
	else:  diff = get_inc_ext(incpref, "diff")

	Rdiff.write_delta(new, mirror, diff, compress)
	rpath.copy_attribs(mirror, diff)
	return diff

def makedir(mirrordir, incpref):
	"""Make file indicating directory mirrordir has changed"""
	dirsign = get_inc_ext(incpref, "dir")
	dirsign.touch()
	rpath.copy_attribs(mirrordir, dirsign)	
	return dirsign

def get_inc(rp, time, typestr):
	"""Return increment like rp but with time and typestr suffixes"""
	addtostr = lambda s: "%s.%s.%s" % (s, Time.timetostring(time), typestr)
	if rp.index:
		incrp = rp.__class__(rp.conn, rp.base, rp.index[:-1] +
							 (addtostr(rp.index[-1]),))
	else: incrp = rp.__class__(rp.conn, addtostr(rp.base), rp.index)
	return incrp

def get_inc_ext(rp, typestr, inctime = None):
	"""Return increment with specified type and time t

	If the file exists, then probably a previous backup has been
	aborted.  We then keep asking FindTime to get a time later
	than the one that already has an inc file.

	"""
	if inctime is None: inctime = Time.prevtime
	while 1:
		incrp = get_inc(rp, inctime, typestr)
		if not incrp.lstat(): break
		else:
			inctime += 1
			log.Log("Warning, increment %s already exists" % (incrp.path,), 2)
	return incrp
