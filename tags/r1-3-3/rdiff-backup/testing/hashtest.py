import unittest, StringIO
from rdiff_backup import hash
from commontest import *

class HashTest(unittest.TestCase):
	"""Test the hash module"""
	s1 = "Hello, world!"
	s1_hash = "943a702d06f34599aee1f8da8ef9f7296031d699"
	s2 = "The quick brown dog jumped over the lazy fox"
	s2_hash = "eab21fb1a18b408909bae552b847f6b13f370f62"
	s3 = "foobar"
	s3_hash = "8843d7f92416211de9ebb963ff4ce28125932878"

	root_rp = rpath.RPath(Globals.local_connection, "testfiles")

	def test_basic(self):
		"""Compare sha1sum of a few strings"""
		sfile = StringIO.StringIO(self.s1)
		fw = hash.FileWrapper(sfile)
		assert fw.read() == self.s1
		report = fw.close()
		assert report.sha1_digest == self.s1_hash, report.sha1_digest

		sfile2 = StringIO.StringIO(self.s1)
		fw2 = hash.FileWrapper(sfile2)
		assert fw2.read(5) == self.s1[:5]
		assert fw2.read() == self.s1[5:]
		report2 = fw2.close()
		assert report2.sha1_digest == self.s1_hash, report2.sha1_digest

	def make_dirs(self):
		"""Make two input directories"""
		d1 = self.root_rp.append("hashtest1")
		re_init_dir(d1)
		d2 = self.root_rp.append("hashtest2")
		re_init_dir(d2)

		d1f1 = d1.append("file1")
		d1f1.write_string(self.s1)
		d1f1l = d1.append("file1_linked")
		d1f1l.hardlink(d1f1.path)

		d1f2 = d1.append("file2")
		d1f2.write_string(self.s2)
		d1f2l = d1.append("file2_linked")
		d1f2l.hardlink(d1f2.path)

		d1_hashlist = [None, self.s1_hash, self.s1_hash,
					   self.s2_hash, self.s2_hash]

		d2f1 = d2.append("file1")
		rpath.copy_with_attribs(d1f1, d2f1)
		d2f1l = d2.append("file1_linked")
		d2f1l.write_string(self.s3)

		d1f2 = d2.append("file2")
		d1f2.mkdir()

		d2_hashlist = [None, self.s1_hash, self.s3_hash, None]

		return (d1, d1_hashlist, d2, d2_hashlist)

	def extract_hashs(self, metadata_rp):
		"""Return list of hashes in the metadata_rp"""
		result = []
		comp = metadata_rp.isinccompressed()
		extractor = metadata.RorpExtractor(metadata_rp.open("r", comp))
		for rorp in extractor.iterate():
			if rorp.has_sha1(): result.append(rorp.get_sha1())
			else: result.append(None)
		return result

	def test_session(self):
		"""Run actual sessions and make sure proper hashes recorded

		There are a few code paths here we need to test:  creating
		ordinary files, updating ordinary files with diffs, hard
		linking, and keeping files the same.

		"""
		in_rp1, hashlist1, in_rp2, hashlist2 = self.make_dirs()
		Myrm("testfiles/output")

		rdiff_backup(1, 1, in_rp1.path, "testfiles/output", 10000, "-v3")
		meta_prefix = rpath.RPath(Globals.local_connection,
					  "testfiles/output/rdiff-backup-data/mirror_metadata")
		incs = restore.get_inclist(meta_prefix)
		assert len(incs) == 1
		metadata_rp = incs[0]
		hashlist = self.extract_hashs(metadata_rp)
		assert hashlist == hashlist1, (hashlist1, hashlist)

		rdiff_backup(1, 1, in_rp2.path, "testfiles/output", 20000, "-v3")
		incs = restore.get_inclist(meta_prefix)
		assert len(incs) == 2
		if incs[0].getinctype() == 'snapshot': inc = incs[0]
		else: inc = incs[1]
		hashlist = self.extract_hashs(inc)
		assert hashlist == hashlist2, (hashlist2, hashlist)

	def test_rorpiter_xfer(self):
		"""Test if hashes are transferred in files, rorpiter"""
		#log.Log.setverbosity(5)
		Globals.security_level = 'override'
		conn = SetConnections.init_connection('python ./server.py .')
		assert conn.reval("lambda x: x+1", 4) == 5 # connection sanity check

		fp = hash.FileWrapper(StringIO.StringIO(self.s1))
		conn.Globals.set('tmp_file', fp)
		fp_remote = conn.Globals.get('tmp_file')
		assert fp_remote.read() == self.s1
		assert fp_remote.close().sha1_digest == self.s1_hash

		# Tested xfer of file, now test xfer of files in rorpiter
		root = MakeOutputDir()
		rp1 = root.append('s1')
		rp1.write_string(self.s1)
		rp2 = root.append('s2')
		rp2.write_string(self.s2)
		rp1.setfile(hash.FileWrapper(rp1.open('rb')))
		rp2.setfile(hash.FileWrapper(rp2.open('rb')))
		rpiter = iter([rp1, rp2])

		conn.Globals.set('tmp_conn_iter', rpiter)
		remote_iter = conn.Globals.get('tmp_conn_iter')

		rorp1 = remote_iter.next()
		fp = rorp1.open('rb')
		assert fp.read() == self.s1, fp.read()
		ret_val = fp.close()
		assert isinstance(ret_val, hash.Report), ret_val
		assert ret_val.sha1_digest == self.s1_hash
		rorp2 = remote_iter.next()
		fp2 = rorp1.open('rb')
		assert fp2.close().sha1_digest == self.s2_hash

		conn.quit()


from rdiff_backup import rpath, regress, restore, metadata, log, Globals

if __name__ == "__main__": unittest.main()
