import unittest, os, cStringIO, time
from rdiff_backup import rpath, connection, Globals, selection, lazy
from rdiff_backup.metadata import *

tempdir = rpath.RPath(Globals.local_connection, "testfiles/output")

class MetadataTest(unittest.TestCase):
	def make_temp(self):
		"""Make temp directory testfiles/output"""
		global tempdir
		if tempdir.lstat(): tempdir.delete()
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
		def write_rorp_iter_to_file(rorp_iter, file):
			for rorp in rorp_iter: file.write(RORP2Record(rorp))

		l = self.get_rpaths()
		fp = cStringIO.StringIO()
		write_rorp_iter_to_file(iter(l), fp)
		fp.seek(0)
		cstring = fp.read()
		fp.seek(0)
		outlist = list(RorpExtractor(fp).iterate())
		assert len(l) == len(outlist), (len(l), len(outlist))
		for i in range(len(l)):
			if not l[i].equal_verbose(outlist[i]):
				#print cstring
				assert 0, (i, str(l[i]), str(outlist[i]))
		fp.close()

	def write_metadata_to_temp(self):
		"""If necessary, write metadata of bigdir to file metadata.gz"""
		global tempdir
		temprp = tempdir.append("mirror_metadata.2005-11-03T14:51:06-06:00.snapshot.gz")
		if temprp.lstat(): return temprp

		self.make_temp()
		rootrp = rpath.RPath(Globals.local_connection, "testfiles/bigdir")
		rpath_iter = selection.Select(rootrp).set_iter()

		start_time = time.time()
		mf = MetadataFile(temprp, 'w')
		for rp in rpath_iter: mf.write_object(rp)
		mf.close()
		print "Writing metadata took %s seconds" % (time.time() - start_time)
		return temprp

	def testSpeed(self):
		"""Test testIterator on 10000 files"""
		temprp = self.write_metadata_to_temp()
		mf = MetadataFile(temprp, 'r')
		
		start_time = time.time(); i = 0
		for rorp in mf.get_objects(): i += 1
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
		mf = MetadataFile(temprp, 'r')
		start_time = time.time(); i = 0
		for rorp in mf.get_objects(("subdir3", "subdir10")): i += 1
		print "Reading %s metadata entries took %s seconds." % \
			  (i, time.time() - start_time)
		assert i == 51

	def test_write(self):
		"""Test writing to metadata file, then reading back contents"""
		global tempdir
		temprp = tempdir.append("mirror_metadata.2005-11-03T12:51:06-06:00.snapshot.gz")
		if temprp.lstat(): temprp.delete()

		self.make_temp()
		rootrp = rpath.RPath(Globals.local_connection,
							 "testfiles/various_file_types")
		dirlisting = rootrp.listdir()
		dirlisting.sort()
		rps = map(rootrp.append, dirlisting)

		assert not temprp.lstat()
		write_mf = MetadataFile(temprp, 'w')
		for rp in rps: write_mf.write_object(rp)
		write_mf.close()
		assert temprp.lstat()

		reread_rps = list(MetadataFile(temprp, 'r').get_objects())
		assert len(reread_rps) == len(rps), (len(reread_rps), len(rps))
		for i in range(len(reread_rps)):
			assert reread_rps[i] == rps[i], i

	def test_patch(self):
		"""Test combining 3 iters of metadata rorps"""
		self.make_temp()
		os.system('cp -a testfiles/various_file_types/* ' + tempdir.path)

		rp1 = tempdir.append('regular_file')
		rp2 = tempdir.append('subdir')
		rp3 = rp2.append('subdir_file')
		rp4 = tempdir.append('test')

		rp1new = tempdir.append('regular_file')
		rp1new.chmod(0)
		zero = rpath.RORPath(('test',))

		current = [rp1, rp2, rp3]
		diff1 = [rp1, rp4]
		diff2 = [rp1new, rp2, zero]

		Globals.rbdir = tempdir
		output = PatchDiffMan().iterate_patched_meta(
			            [iter(current), iter(diff1), iter(diff2)])
		out1 = output.next()
		assert out1 is rp1new, out1
		out2 = output.next()
		assert out2 is rp2, out2
		out3 = output.next()
		assert out3 is rp3, out3
		self.assertRaises(StopIteration, output.next)

	def test_meta_patch_cycle(self):
		"""Create various metadata rorps, diff them, then compare"""
		def write_dir_to_meta(manager, rp, time):
			"""Record the metadata under rp to a mirror_metadata file"""
			metawriter = man.get_meta_writer('snapshot', time)
			for rorp in selection.Select(rp).set_iter():
				metawriter.write_object(rorp)
			metawriter.close()

		def compare(man, rootrp, time):
			assert lazy.Iter.equal(selection.Select(rootrp).set_iter(),
								   man.get_meta_at_time(time, None))


		self.make_temp()
		Globals.rbdir = tempdir
		man = PatchDiffMan()
		inc1 = rpath.RPath(Globals.local_connection, "testfiles/increment1")
		inc2 = rpath.RPath(Globals.local_connection, "testfiles/increment2")
		inc3 = rpath.RPath(Globals.local_connection, "testfiles/increment3")
		inc4 = rpath.RPath(Globals.local_connection, "testfiles/increment4")
		write_dir_to_meta(man, inc1, 10000)
		compare(man, inc1, 10000)
		write_dir_to_meta(man, inc2, 20000)
		compare(man, inc2, 20000)
		man.ConvertMetaToDiff()
		man = PatchDiffMan()
		write_dir_to_meta(man, inc3, 30000)
		compare(man, inc3, 30000)
		man.ConvertMetaToDiff()
		man = PatchDiffMan()
		man.max_diff_chain = 3
		write_dir_to_meta(man, inc4, 40000)
		compare(man, inc4, 40000)
		man.ConvertMetaToDiff()

		man = PatchDiffMan()
		l = man.sorted_prefix_inclist('mirror_metadata')
		assert l[0].getinctype() == 'snapshot'
		assert l[0].getinctime() == 40000
		assert l[1].getinctype() == 'snapshot'
		assert l[1].getinctime() == 30000
		assert l[2].getinctype() == 'diff'
		assert l[2].getinctime() == 20000
		assert l[3].getinctype() == 'diff'
		assert l[3].getinctime() == 10000

		compare(man, inc1, 10000)
		compare(man, inc2, 20000)
		compare(man, inc3, 30000)
		compare(man, inc4, 40000)
		

if __name__ == "__main__": unittest.main()
