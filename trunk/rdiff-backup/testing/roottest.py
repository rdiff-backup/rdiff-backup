execfile("../src/setconnections.py")
import unittest, os

"""Root tests

This is mainly a copy of regressiontest.py, but contains the two tests
that are meant to be run as root.
"""

Globals.change_source_perms = 1
Globals.counter = 0
Log.setverbosity(4)

class Local:
	"""This is just a place to put increments relative to the local
	connection"""
	def get_local_rp(extension):
		return RPath(Globals.local_connection, "testfiles/" + extension)

	inc1rp = get_local_rp('increment1')
	inc2rp = get_local_rp('increment2')
	inc3rp = get_local_rp('increment3')
	inc4rp = get_local_rp('increment4')

	rpout = get_local_rp('output')
	rpout_inc = get_local_rp('output_inc')
	rpout1 = get_local_rp('restoretarget1')
	rpout2 = get_local_rp('restoretarget2')
	rpout3 = get_local_rp('restoretarget3')
	rpout4 = get_local_rp('restoretarget4')

	noperms = get_local_rp('noperms')
	noperms_out = get_local_rp('noperms_output')

	rootfiles = get_local_rp('root')
	rootfiles_out = get_local_rp('root_output')

	prefix = get_local_rp('.')


class PathSetter(unittest.TestCase):
	def get_prefix_and_conn(self, path, return_path):
		"""Return (prefix, connection) tuple"""
		if path:
			return (return_path,
					SetConnections.init_connection("./chdir-wrapper "+path))
		else: return ('./', Globals.local_connection)

	def get_src_rp(self, path):
		return RPath(self.src_conn, self.src_prefix + path)

	def get_dest_rp(self, path):
		return RPath(self.dest_conn, self.dest_prefix + path)


	def set_rbdir(self, rpout):
		"""Create rdiff-backup-data dir if not already, tell everyone"""
		self.rbdir = self.rpout.append('rdiff-backup-data')
		self.rpout.mkdir()
		self.rbdir.mkdir()
		SetConnections.UpdateGlobal('rbdir', self.rbdir)

		# Better safe than sorry - cover all possibilities
		Globals.add_regexp("testfiles/output/rdiff-backup-data", 1)
		Globals.add_regexp("./testfiles/output/rdiff-backup-data", 1)
		Globals.add_regexp("../testfiles/output/rdiff-backup-data", 1)
		Globals.add_regexp("../../testfiles/output/rdiff-backup-data", 1)
		
	def setPathnames(self, src_path, src_return, dest_path, dest_return):
		"""Start servers which will run in src_path and dest_path respectively

		If either is None, then no server will be run and local
		process will handle that end.  src_return and dest_return are
		the prefix back to the original rdiff-backup directory.  So
		for instance is src_path is "test2/tmp", then src_return will
		be '../'.

		"""
		# Clear old data that may rely on deleted connections
		Globals.isbackup_writer = None
		Globals.isbackup_reader = None
		Globals.rbdir = None

		print "Setting up connection"
		self.src_prefix, self.src_conn = \
						 self.get_prefix_and_conn(src_path, src_return)
		self.dest_prefix, self.dest_conn = \
						  self.get_prefix_and_conn(dest_path, dest_return)
		SetConnections.BackupInitConnections(self.src_conn, self.dest_conn)

		os.system("./myrm testfiles/output* testfiles/restoretarget* "
				  "testfiles/noperms_output testfiles/root_output "
				  "testfiles/unreadable_out")
		self.inc1rp = self.get_src_rp("testfiles/increment1")
		self.inc2rp = self.get_src_rp('testfiles/increment2')
		self.inc3rp = self.get_src_rp('testfiles/increment3')
		self.inc4rp = self.get_src_rp('testfiles/increment4')

		self.rpout_inc = self.get_dest_rp('testfiles/output_inc')
		self.rpout1 = self.get_dest_rp('testfiles/restoretarget1')
		self.rpout2 = self.get_dest_rp('testfiles/restoretarget2')
		self.rpout3 = self.get_dest_rp('testfiles/restoretarget3')
		self.rpout4 = self.get_dest_rp('testfiles/restoretarget4')

		self.rpout = self.get_dest_rp('testfiles/output')
		self.set_rbdir(self.rpout)

		self.noperms = self.get_src_rp('testfiles/noperms')
		self.noperms_out = self.get_dest_rp('testfiles/noperms_output')

		self.rootfiles = self.get_src_rp('testfiles/root')
		self.rootfiles_out = self.get_dest_rp('testfiles/root_output')

		self.one_unreadable = self.get_src_rp('testfiles/one_unreadable')
		self.one_unreadable_out = self.get_dest_rp('testfiles/unreadable_out')

	def tearDown(self):
		print "Taking down connections"
		SetConnections.CloseConnections()
		os.system("./myrm testfiles/output* testfiles/restoretarget* "
				  "testfiles/noperms_output testfiles/root_output "
				  "testfiles/unreadable_out")


class MirrorTest(PathSetter):
	"""Test some mirroring functions"""
	def refresh(self, *rps):
		for rp in rps: rp.setdata()

	def testRootLocal(self):
		"""Test mirroring a directory with dev files and different owners"""
		self.setPathnames(None, None, None, None)
		Time.setcurtime()		
		SaveState.init_filenames(None)
		Globals.change_ownership = 1
		self.refresh(self.rootfiles, self.rootfiles_out,
				Local.rootfiles, Local.rootfiles_out) # add uid/gid info
		HighLevel.Mirror(self.rootfiles, self.rootfiles_out)
		assert CompareRecursive(Local.rootfiles, Local.rootfiles_out)
		Globals.change_ownership = None
		self.refresh(self.rootfiles, self.rootfiles_out,
				Local.rootfiles, Local.rootfiles_out) # remove that info

	def testRootRemote(self):
		"""Mirroring root files both ends remote"""
		self.setPathnames('test1', '../', 'test2/tmp', '../../')
		Time.setcurtime()		
		SaveState.init_filenames(None)
		for conn in Globals.connections:
			conn.Globals.set('change_ownership', 1)
		self.refresh(self.rootfiles, self.rootfiles_out,
				Local.rootfiles, Local.rootfiles_out) # add uid/gid info
		HighLevel.Mirror(self.rootfiles, self.rootfiles_out)
		assert CompareRecursive(Local.rootfiles, Local.rootfiles_out)
		for coon in Globals.connections:
			conn.Globals.set('change_ownership', None)
		self.refresh(self.rootfiles, self.rootfiles_out,
				Local.rootfiles, Local.rootfiles_out) # remove that info

	def deleteoutput(self):
		os.system("./myrm testfiles/output*")
		self.reset_rps()


if __name__ == "__main__": unittest.main()
