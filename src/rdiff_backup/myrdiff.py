#!/usr/bin/env python3
"""Like rdiff, but written in python and uses librsync module.

Useful for benchmarking and testing of librsync and _librsync.

"""

import sys
import rdiff_backup.librsync

blocksize = 32768


def makesig(inpath, outpath):
    """Write a signature of inpath at outpath"""
    sf = librsync.SigFile(open(inpath, "rb"))
    fout = open(outpath, "wb")
    while 1:
        buf = sf.read(blocksize)
        if not buf: break
        fout.write(buf)
    assert not sf.close()
    assert not fout.close()


def makedelta(sigpath, newpath, deltapath):
    """Write delta at deltapath using signature at sigpath"""
    df = librsync.DeltaFile(open(sigpath, "rb"), open(newpath, "rb"))
    fout = open(deltapath, "wb")
    while 1:
        buf = df.read(blocksize)
        if not buf: break
        fout.write(buf)
    assert not df.close()
    assert not fout.close()


def makepatch(basis_path, delta_path, new_path):
    """Write new given basis and delta"""
    pf = librsync.PatchedFile(open(basis_path, "rb"), open(delta_path, "rb"))
    fout = open(new_path, "wb")
    while 1:
        buf = pf.read(blocksize)
        if not buf: break
        fout.write(buf)
    assert not pf.close()
    assert not fout.close()


if sys.argv[1] == "signature":
    makesig(sys.argv[2], sys.argv[3])
elif sys.argv[1] == "delta":
    makedelta(sys.argv[2], sys.argv[3], sys.argv[4])
elif sys.argv[1] == "patch":
    makepatch(sys.argv[2], sys.argv[3], sys.argv[4])
else:
    assert 0, "Bad mode argument %s" % (sys.argv[1], )
