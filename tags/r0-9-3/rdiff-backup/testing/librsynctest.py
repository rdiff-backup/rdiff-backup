import unittest, random
from commontest import *
import librsync

def MakeRandomFile(path):
	"""Writes a random file of length between 10000 and 100000"""
	fp = open(path, "w")
	randseq = []
	for i in xrange(random.randrange(5000, 30000)):
		randseq.append(chr(random.randrange(256)))
	fp.write("".join(randseq))
	fp.close()


class LibrsyncTest(unittest.TestCase):
	"""Test various librsync wrapper functions"""
	basis = RPath(Globals.local_connection, "testfiles/basis")
	new = RPath(Globals.local_connection, "testfiles/new")
	new2 = RPath(Globals.local_connection, "testfiles/new2")
	sig = RPath(Globals.local_connection, "testfiles/signature")
	delta = RPath(Globals.local_connection, "testfiles/delta")
	def testSigFile(self):
		"""Make sure SigFile generates same data as rdiff"""
		for i in range(5):
			MakeRandomFile(self.basis.path)
			self.sig.delete()
			assert not os.system("rdiff signature %s %s" %
								 (self.basis.path, self.sig.path))
			fp = self.sig.open("rb")
			rdiff_sig = fp.read()
			fp.close()

			sf = librsync.SigFile(self.basis.open("rb"))
			librsync_sig = sf.read()
			sf.close()

			assert rdiff_sig == librsync_sig, \
				   (len(rdiff_sig), len(librsync_sig))

	def OldtestDelta(self):
		"""Test delta generation against Rdiff"""
		MakeRandomFile(self.basis.path)
		assert not os.system("rdiff signature %s %s" %
							 (self.basis.path, self.sig.path))
		for i in range(5):
			MakeRandomFile(self.new.path)
			assert not os.system("rdiff delta %s %s %s" %
						  (self.sig.path, self.new.path, self.delta.path))
			fp = self.delta.open("rb")
			rdiff_delta = fp.read()
			fp.close()

			df = librsync.DeltaFile(self.sig.open("rb"), self.new.open("rb"))
			librsync_delta = df.read()
			df.close()

			print len(rdiff_delta), len(librsync_delta)
			print repr(rdiff_delta[:100])
			print repr(librsync_delta[:100])
			assert rdiff_delta == librsync_delta

	def testDelta(self):
		"""Test delta generation by making sure rdiff can process output

		There appears to be some undeterminism so we can't just
		byte-compare the deltas produced by rdiff and DeltaFile.

		"""
		MakeRandomFile(self.basis.path)
		assert not os.system("rdiff signature %s %s" %
							 (self.basis.path, self.sig.path))
		for i in range(5):
			MakeRandomFile(self.new.path)
			df = librsync.DeltaFile(self.sig.open("rb"), self.new.open("rb"))
			librsync_delta = df.read()
			df.close()
			fp = self.delta.open("wb")
			fp.write(librsync_delta)
			fp.close()

			assert not os.system("rdiff patch %s %s %s" %
								 (self.basis.path, self.delta.path,
								  self.new2.path))
			new_fp = self.new.open("rb")
			new = new_fp.read()
			new_fp.close()

			new2_fp = self.new2.open("rb")
			new2 = new2_fp.read()
			new2_fp.close()

			assert new == new2, (len(new), len(new2))

	def testPatch(self):
		"""Test patching against Rdiff"""
		MakeRandomFile(self.basis.path)
		assert not os.system("rdiff signature %s %s" %
							 (self.basis.path, self.sig.path))
		for i in range(5):
			MakeRandomFile(self.new.path)
			assert not os.system("rdiff delta %s %s %s" %
						  (self.sig.path, self.new.path, self.delta.path))
			fp = self.new.open("rb")
			real_new = fp.read()
			fp.close()

			pf = librsync.PatchedFile(self.basis.open("rb"),
									  self.delta.open("rb"))
			librsync_new = pf.read()
			pf.close()

			assert real_new == librsync_new, \
				   (len(real_new), len(librsync_new))
			


if __name__ == "__main__": unittest.main()
			
