#!/usr/bin/env python

"""Demonstrate a memory leak in pysync/librsync"""

import os, _librsync
from librsync import *

os.chdir("/tmp")

# Write 2 1 byte files
afile = open("a", "wb")
afile.write("a")
afile.close()

efile = open("e", "wb")
efile.write("e")
efile.close()

def copy(infileobj, outpath):
	outfile = open(outpath, "wb")
	while 1:
		buf = infileobj.read(32768)
		if not buf: break
		outfile.write(buf)
	assert not outfile.close()
	assert not infileobj.close()

def test_cycle():
	for i in xrange(100000):
		sm = _librsync.new_sigmaker()
		sm.cycle("a")

def main_test():
	for i in xrange(100000):
		# Write signature file
		afile = open("a", "rb")
		copy(SigFile(afile), "sig")

		# Write delta file
		efile = open("e", "r")
		sigfile = open("sig", "rb")
		copy(DeltaFile(sigfile, efile), "delta")

		# Write patched file
		afile = open("e", "rb")
		deltafile = open("delta", "rb")
		copy(PatchedFile(afile, deltafile), "a.out")

main_test()
