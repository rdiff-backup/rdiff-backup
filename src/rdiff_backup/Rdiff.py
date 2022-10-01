# Copyright 2002 2005 Ben Escoto
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
"""Invoke rdiff utility to make signatures, deltas, or patch"""

from rdiff_backup import Globals, log, rpath, hash, librsync


def get_signature(rp, blocksize=None):
    """Take signature of rpin file and return in file object"""
    if not blocksize:
        blocksize = _find_blocksize(rp.getsize())
    log.Log("Getting signature of file {fi} with blocksize {bs}".format(
        fi=rp, bs=blocksize), log.DEBUG)
    return librsync.SigFile(rp.open("rb"), blocksize)


def get_delta_sigrp_hash(rp_signature, rp_new):
    """Like above but also calculate hash of new as close() value"""
    log.Log("Getting delta (with hash) of file {fi} with signature {si}".format(
        fi=rp_new, si=rp_signature), log.DEBUG)
    try:
        return librsync.DeltaFile(
            rp_signature.open("rb"), hash.FileWrapper(rp_new.open("rb")))
    except OSError:
        rp_signature.close_if_necessary()
        raise


def write_delta(basis, new, delta, compress=None):
    """Write rdiff delta which brings basis to new"""
    log.Log("Writing delta {de} from basis {ba} to new {ne}".format(
        ba=basis, ne=new, de=delta), log.DEBUG)
    deltafile = librsync.DeltaFile(get_signature(basis), new.open("rb"))
    delta.write_from_fileobj(deltafile, compress)


def write_patched_fp(basis_fp, delta_fp, out_fp):
    """Write patched file to out_fp given input fps.  Closes input files"""
    rpath.copyfileobj(librsync.PatchedFile(basis_fp, delta_fp), out_fp)
    basis_fp.close()
    delta_fp.close()


def patch_local(rp_basis, rp_delta, outrp=None, delta_compressed=None):
    """
    Patch routine that must be run locally, writes to outrp

    This should be run local to rp_basis because it needs to be a real
    file (librsync may need to seek around in it).  If outrp is None,
    patch rp_basis instead.

    The return value is the close value of the delta, so it can be
    used to produce hashes.
    """
    assert rp_basis.conn is Globals.local_connection, (
        "This function must run locally and not over '{conn}'.".format(
            conn=rp_basis.conn))
    if delta_compressed:
        deltafile = rp_delta.open("rb", 1)
    else:
        deltafile = rp_delta.open("rb")
    patchfile = librsync.PatchedFile(rp_basis.open("rb"), deltafile)
    if outrp:
        return outrp.write_from_fileobj(patchfile)
    else:
        return _write_via_tempfile(patchfile, rp_basis)


def _find_blocksize(file_len):
    """
    Return a reasonable block size to use on files of length file_len

    If the block size is too big, deltas will be bigger than is
    necessary.  If the block size is too small, making deltas and
    patching can take a really long time.
    """
    if file_len < 10240:
        return 64  # set minimum of 64 bytes
    else:
        # Use square root, rounding to nearest 16
        # somewhat faster than int(pow(file_len, 0.5) / 16) * 16
        return (file_len >> (file_len.bit_length() // 2 + 4)) << 4


def _write_via_tempfile(fp, rp):
    """Write fileobj fp to rp by writing to tempfile and renaming"""
    tf = rp.get_temp_rpath(sibling=True)
    retval = tf.write_from_fileobj(fp)
    rpath.rename(tf, rp)
    return retval
