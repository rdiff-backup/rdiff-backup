import unittest, os, cStringIO, time
from rdiff_backup.metadata import *
from rdiff_backup import rpath, connection, Globals, selection

tempdir = rpath.RPath(Globals.local_connection, "testfiles/output")

class MetadataTest(unittest.TestCase):
	def make_temp(self):
		"""Make temp directory testfiles/output"""
		global tempdir
		tempdir.delete()
		tempdir.mkdir()

	def testQuote(self):
		"""Test quoting and unquoting"""
		filenames = ["foo", ".", "hello\nthere", "\\", "\\\\\\",
					 "h\no\t\x87\n", " "]
		for filename in filenames:
			quoted = quote_path(filename)
			assert not "\n" in quoted
			result = unquote_path(quoted)
			assert result == filename, (quoted, result, filename)

	def get_rpaths(self):
		"""Return list of rorps"""
		vft = rpath.RPath(Globals.local_connection,
						  "testfiles/various_file_types")
		rpaths = map(lambda x: vft.append(x), vft.listdir())
		extra_rpaths = map(lambda x: rpath.RPath(Globals.local_connection, x),
						   ['/bin/ls', '/dev/ttyS0', '/dev/hda', 'aoeuaou'])
		return [vft] + rpaths + extra_rpaths

	def testRORP2Record(self):
		"""Test turning RORPs into records and back again"""
		for rp in self.get_rpaths():
			record = RORP2Record(rp)
			#print record
			new_rorp = Record2RORP(record)
			assert new_rorp == rp, (new_rorp, rp, record)

	def testIterator(self):
		"""Test writing RORPs to file and iterating them back"""
		l = self.get_rpaths()
		fp = cStringIO.StringIO()
		write_rorp_iter_to_file(iter(l), fp)
		fp.seek(0)
		cstring = fp.read()
		fp.seek(0)
		outlist = list(rorp_extractor(fp).iterate())
		assert len(l) == len(outlist), (len(l), len(outlist))
		for i in range(len(l)):
			if not l[i].equal_verbose(outlist[i]):
				#print cstring
				assert 0, (i, str(l[i]), str(outlist[i]))
		fp.close()

	def write_metadata_to_temp(self):
		"""If necessary, write metadata of bigdir to file metadata.gz"""
		global tempdir
		temprp = tempdir.append("metadata.gz")
		if temprp.lstat(): return temprp

		self.make_temp()
		rootrp = rpath.RPath(Globals.local_connection, "testfiles/bigdir")
		rpath_iter = selection.Select(rootrp).set_iter()

		start_time = time.time()
		OpenMetadata(temprp)
		for rp in rpath_iter: WriteMetadata(rp)
		CloseMetadata()
		print "Writing metadata took %s seconds" % (time.time() - start_time)
		return temprp

	def testSpeed(self):
		"""Test testIterator on 10000 files"""
		temprp = self.write_metadata_to_temp()
		
		start_time = time.time(); i = 0
		for rorp in GetMetadata(temprp): i += 1
		print "Reading %s metadata entries took %s seconds." % \
			  (i, time.time() - start_time)

		start_time = time.time()
		blocksize = 32 * 1024
		tempfp = temprp.open("rb", compress = 1)
		while 1:
			buf = tempfp.read(blocksize)
			if not buf: break
		assert not tempfp.close()
		print "Simply decompressing metadata file took %s seconds" % \
			  (time.time() - start_time)

	def testIterate_restricted(self):
		"""Test getting rorps restricted to certain index

		In this case, get assume subdir (subdir3, subdir10) has 50
		files in it.

		"""
		temprp = self.write_metadata_to_temp()
		start_time = time.time(); i = 0
		for rorp in GetMetadata(temprp, ("subdir3", "subdir10")): i += 1
		print "Reading %s metadata entries took %s seconds." % \
			  (i, time.time() - start_time)
		assert i == 51


if __name__ == "__main__": unittest.main()
