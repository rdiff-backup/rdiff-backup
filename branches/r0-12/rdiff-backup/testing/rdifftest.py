import unittest, random
from commontest import *
from rdiff_backup import Globals, Rdiff, selection, log, rpath

Log.setverbosity(6)

def MakeRandomFile(path):
	"""Writes a random file of length between 10000 and 100000"""
	fp = open(path, "w")
	randseq = []
	for i in xrange(random.randrange(5000, 30000)):
		randseq.append(chr(random.randrange(256)))
	fp.write("".join(randseq))
	fp.close()


class RdiffTest(unittest.TestCase):
	"""Test rdiff"""
	lc = Globals.local_connection
	basis = rpath.RPath(lc, "testfiles/basis")
	new = rpath.RPath(lc, "testfiles/new")
	output = rpath.RPath(lc, "testfiles/output")
	delta = rpath.RPath(lc, "testfiles/delta")
	signature = rpath.RPath(lc, "testfiles/signature")

	def testRdiffSig(self):
		"""Test making rdiff signatures"""
		sig = rpath.RPath(self.lc,
						  "testfiles/various_file_types/regular_file.sig")
		sigfp = sig.open("r")
		rfsig = Rdiff.get_signature(RPath(self.lc, "testfiles/various_file_types/regular_file"))
		assert rpath.cmpfileobj(sigfp, rfsig)
		sigfp.close()
		rfsig.close()

	def testRdiffDeltaPatch(self):
		"""Test making deltas and patching files"""
		rplist = [self.basis, self.new, self.delta,
				  self.signature, self.output]
		for rp in rplist:
			if rp.lstat(): rp.delete()
			
		for i in range(2):
			MakeRandomFile(self.basis.path)
			MakeRandomFile(self.new.path)
			map(rpath.RPath.setdata, [self.basis, self.new])
			assert self.basis.lstat() and self.new.lstat()
			self.signature.write_from_fileobj(Rdiff.get_signature(self.basis))
			assert self.signature.lstat()
			self.delta.write_from_fileobj(Rdiff.get_delta_sigrp(self.signature,
																self.new))
			assert self.delta.lstat()
			Rdiff.patch_local(self.basis, self.delta, self.output)
			assert rpath.cmp(self.new, self.output)
			map(rpath.RPath.delete, rplist)

	def testRdiffDeltaPatchGzip(self):
		"""Same as above by try gzipping patches"""
		rplist = [self.basis, self.new, self.delta,
				  self.signature, self.output]
		for rp in rplist:
			if rp.lstat(): rp.delete()
			
		MakeRandomFile(self.basis.path)
		MakeRandomFile(self.new.path)
		map(rpath.RPath.setdata, [self.basis, self.new])
		assert self.basis.lstat() and self.new.lstat()
		self.signature.write_from_fileobj(Rdiff.get_signature(self.basis))
		assert self.signature.lstat()
		self.delta.write_from_fileobj(Rdiff.get_delta_sigrp(self.signature,
															self.new))
		assert self.delta.lstat()
		os.system("gzip " + self.delta.path)
		os.system("mv %s %s" % (self.delta.path + ".gz", self.delta.path))
		self.delta.setdata()

		Rdiff.patch_local(self.basis, self.delta, self.output,
						  delta_compressed = 1)
		assert rpath.cmp(self.new, self.output)
		map(rpath.RPath.delete, rplist)

	def testWriteDelta(self):
		"""Test write delta feature of rdiff"""
		if self.delta.lstat(): self.delta.delete()
		rplist = [self.basis, self.new, self.delta, self.output]
		MakeRandomFile(self.basis.path)
		MakeRandomFile(self.new.path)
		map(rpath.RPath.setdata, [self.basis, self.new])
		assert self.basis.lstat() and self.new.lstat()

		Rdiff.write_delta(self.basis, self.new, self.delta)
		assert self.delta.lstat()
		Rdiff.patch_local(self.basis, self.delta, self.output)
		assert rpath.cmp(self.new, self.output)
		map(rpath.RPath.delete, rplist)		

	def testWriteDeltaGzip(self):
		"""Same as above but delta is written gzipped"""
		rplist = [self.basis, self.new, self.delta, self.output]
		MakeRandomFile(self.basis.path)
		MakeRandomFile(self.new.path)
		map(rpath.RPath.setdata, [self.basis, self.new])
		assert self.basis.lstat() and self.new.lstat()
		delta_gz = rpath.RPath(self.delta.conn, self.delta.path + ".gz")
		if delta_gz.lstat(): delta_gz.delete()

		Rdiff.write_delta(self.basis, self.new, delta_gz, 1)
		assert delta_gz.lstat()
		os.system("gunzip " + delta_gz.path)
		delta_gz.setdata()
		self.delta.setdata()
		Rdiff.patch_local(self.basis, self.delta, self.output)
		assert rpath.cmp(self.new, self.output)
		map(rpath.RPath.delete, rplist)		

	def testRdiffRename(self):
		"""Rdiff replacing original file with patch outfile"""
		rplist = [self.basis, self.new, self.delta, self.signature]
		for rp in rplist:
			if rp.lstat(): rp.delete()

		MakeRandomFile(self.basis.path)
		MakeRandomFile(self.new.path)
		map(rpath.RPath.setdata, [self.basis, self.new])
		assert self.basis.lstat() and self.new.lstat()
		self.signature.write_from_fileobj(Rdiff.get_signature(self.basis))
		assert self.signature.lstat()
		self.delta.write_from_fileobj(Rdiff.get_delta_sigrp(self.signature,
															self.new))
		assert self.delta.lstat()
		Rdiff.patch_local(self.basis, self.delta)
		assert rpath.cmp(self.basis, self.new)
		map(rpath.RPath.delete, rplist)

	def testCopy(self):
		"""Using rdiff to copy two files"""
		rplist = [self.basis, self.new]
		for rp in rplist:
			if rp.lstat(): rp.delete()

		MakeRandomFile(self.basis.path)
		MakeRandomFile(self.new.path)
		map(rpath.RPath.setdata, rplist)
		Rdiff.copy_local(self.basis, self.new)
		assert rpath.cmp(self.basis, self.new)
		map(rpath.RPath.delete, rplist)


if __name__ == '__main__':
	unittest.main()
