import unittest

execfile("commontest.py")
rbexec("setconnections.py")


class RemoteMirrorTest(unittest.TestCase):
	"""Test mirroring"""
	def setUp(self):
		"""Start server"""
		Log.setverbosity(7)
		Globals.change_source_perms = 1
		self.conn = SetConnections.init_connection("./server.py")

		self.inrp = RPath(Globals.local_connection, "testfiles/various_file_types")
		self.outrp = RPath(self.conn, "testfiles/output")
		self.rbdir = RPath(self.conn, "testfiles/output/rdiff-backup-data")
		SetConnections.UpdateGlobal('rbdir', self.rbdir)
		self.inc1 = RPath(Globals.local_connection, "testfiles/increment1")
		self.inc2 = RPath(Globals.local_connection, "testfiles/increment2")
		self.inc3 = RPath(Globals.local_connection, "testfiles/increment3")
		self.inc4 = RPath(Globals.local_connection, "testfiles/increment4")

		SetConnections.BackupInitConnections(Globals.local_connection,
											 self.conn)
		SetConnections.UpdateGlobal('checkpoint_interval', 3)

	def testMirror(self):
		"""Testing simple mirror"""
		if self.outrp.lstat(): self.outrp.delete()
		HighLevel.Mirror(self.inrp, self.outrp, None)
		self.outrp.setdata()
		assert RPath.cmp_recursive(self.inrp, self.outrp)

	def testMirror2(self):
		"""Test mirror with larger data set"""
		if self.outrp.lstat(): self.outrp.delete()
		for rp in [self.inc1, self.inc2, self.inc3, self.inc4]:
			rp.setdata()
			print "----------------- Starting ", rp.path
			HighLevel.Mirror(rp, self.outrp, None)
			#if rp is self.inc2: assert 0
			assert RPath.cmp_recursive(rp, self.outrp)
			self.outrp.setdata()

	def testMirrorWithCheckpointing(self):
		"""Like testMirror but this time checkpoint"""
		if self.outrp.lstat(): self.outrp.delete()
		self.outrp.mkdir()
		self.rbdir.mkdir()
		Globals.add_regexp("testfiles/output/rdiff-backup-data", 1)
		Time.setcurtime()
		SaveState.init_filenames(None)
		HighLevel.Mirror(self.inrp, self.outrp, 1)
		self.outrp.setdata()
		assert RPath.cmp_recursive(self.inrp, self.outrp)

	def testMirrorWithCheckpointing2(self):
		"""Larger data set"""
		if self.outrp.lstat(): os.system(MiscDir+"/myrm %s" % self.outrp.path)
		self.outrp.setdata()
		self.outrp.mkdir()
		self.rbdir.mkdir()
		Globals.add_regexp("testfiles/output/rdiff-backup-data", 1)
		Time.setcurtime()
		SaveState.init_filenames(None)
		for rp in [self.inc1, self.inc2, self.inc3, self.inc4]:
			print "----------------- Starting ", rp.path
			HighLevel.Mirror(rp, self.outrp, 1)
			assert RPath.cmp_recursive(rp, self.outrp)

	def tearDown(self): SetConnections.CloseConnections()


if __name__ == "__main__": unittest.main()
