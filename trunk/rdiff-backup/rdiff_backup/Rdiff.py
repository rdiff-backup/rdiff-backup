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

"""Invoke rdiff utility to make signatures, deltas, or patch

All these operations should be done in a relatively safe manner using
RobustAction and the like.

"""

import os, librsync
from log import Log
import robust, TempFile, Globals


def get_signature(rp):
	"""Take signature of rpin file and return in file object"""
	Log("Getting signature of %s" % rp.path, 7)
	return librsync.SigFile(rp.open("rb"))

def get_delta_sigfileobj(sig_fileobj, rp_new):
	"""Like get_delta but signature is in a file object"""
	Log("Getting delta of %s with signature stream" % (rp_new.path,), 7)
	return librsync.DeltaFile(sig_fileobj, rp_new.open("rb"))

def get_delta_sigrp(rp_signature, rp_new):
	"""Take signature rp and new rp, return delta file object"""
	Log("Getting delta of %s with signature %s" %
		(rp_new.path, rp_signature.get_indexpath()), 7)
	return librsync.DeltaFile(rp_signature.open("rb"), rp_new.open("rb"))

def write_delta_action(basis, new, delta, compress = None):
	"""Return action writing delta which brings basis to new

	If compress is true, the output of rdiff will be gzipped
	before written to delta.

	"""
	delta_tf = TempFile.new(delta)
	def init(): write_delta(basis, new, delta_tf, compress)
	return robust.make_tf_robustaction(init, delta_tf, delta)

def write_delta(basis, new, delta, compress = None):
	"""Write rdiff delta which brings basis to new"""
	Log("Writing delta %s from %s -> %s" %
		(basis.path, new.path, delta.path), 7)
	sigfile = librsync.SigFile(basis.open("rb"))
	deltafile = librsync.DeltaFile(sigfile, new.open("rb"))
	delta.write_from_fileobj(deltafile, compress)

def patch_action(rp_basis, rp_delta, rp_out = None, out_tf = None,
				 delta_compressed = None):
	"""Return RobustAction which patches rp_basis with rp_delta

	If rp_out is None, put output in rp_basis.  Will use TempFile
	out_tf it is specified.  If delta_compressed is true, the
	delta file will be decompressed before processing with rdiff.

	"""
	if not rp_out: rp_out = rp_basis
	if not out_tf: out_tf = TempFile.new(rp_out)
	def init():
		rp_basis.conn.Rdiff.patch_local(rp_basis, rp_delta,
										out_tf, delta_compressed)
		out_tf.setdata()
	return robust.make_tf_robustaction(init, out_tf, rp_out)

def patch_local(rp_basis, rp_delta, outrp, delta_compressed = None):
	"""Patch routine that must be run on rp_basis.conn

	This is because librsync may need to seek() around in rp_basis,
	and so needs a real file.  Other rpaths can be remote.

	"""
	assert rp_basis.conn is Globals.local_connection
	if delta_compressed: deltafile = rp_delta.open("rb", 1)
	else: deltafile = rp_delta.open("rb")

	sigfile = librsync.SigFile(rp_basis.open("rb"))
	patchfile = librsync.PatchedFile(rp_basis.open("rb"), deltafile)
	outrp.write_from_fileobj(patchfile)

def patch_with_attribs_action(rp_basis, rp_delta, rp_out = None):
	"""Like patch_action, but also transfers attributs from rp_delta"""
	if not rp_out: rp_out = rp_basis
	tf = TempFile.new(rp_out)
	return robust.chain_nested(patch_action(rp_basis, rp_delta, rp_out, tf),
							   robust.copy_attribs_action(rp_delta, tf))

def copy_action(rpin, rpout):
	"""Use rdiff to copy rpin to rpout, conserving bandwidth"""
	if not rpin.isreg() or not rpout.isreg() or rpin.conn is rpout.conn:
		# rdiff not applicable, fallback to regular copying
		return robust.copy_action(rpin, rpout)

	Log("Rdiff copying %s to %s" % (rpin.path, rpout.path), 6)		
	out_tf = TempFile.new(rpout)
	def init(): rpout.conn.Rdiff.copy_local(rpin, rpout, out_tf)
	return robust.make_tf_robustaction(init, out_tf, rpout)

def copy_local(rpin, rpout, rpnew):
	"""Write rpnew == rpin using rpout as basis.  rpout and rpnew local"""
	assert rpnew.conn is rpout.conn is Globals.local_connection
	sigfile = librsync.SigFile(rpout.open("rb"))
	deltafile = rpin.conn.librsync.DeltaFile(sigfile, rpin.open("rb"))
	rpnew.write_from_fileobj(librsync.PatchedFile(rpout.open("rb"), deltafile))
	


