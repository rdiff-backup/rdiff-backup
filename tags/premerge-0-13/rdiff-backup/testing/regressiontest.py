import unittest, os
from commontest import *
from rdiff_backup import Globals, SetConnections, log, rpath, backup


"""Regression tests

This one must be run in the rdiff-backup directory, as it requres
chdir-wrapper, the various rdiff-backup files, and the directory
testfiles
"""

Globals.set('change_source_perms', 1)
Globals.counter = 0
log.Log.setverbosity(7)

def get_local_rp(extension):
	return rpath.RPath(Globals.local_connection, "testfiles/" + extension)

class Local:
	"""This is just a place to put increments relative to the local
	connection"""
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
	rootfiles2 = get_local_rp('root2')
	rootfiles21 = get_local_rp('root2.1')
	rootfiles_out = get_local_rp('root_output')
	rootfiles_out2 = get_local_rp('root_output2')

	prefix = get_local_rp('.')


class PathSetter(unittest.TestCase):
	def get_prefix_and_conn(self, path, return_path):
		"""Return (prefix, connection) tuple"""
		if path:
			return (return_path,
					SetConnections.init_connection("./chdir-wrapper "+path))
		else: return ('./', Globals.local_connection)

	def get_src_rp(self, path):
		return rpath.RPath(self.src_conn, self.src_prefix + path)

	def get_dest_rp(self, path):
		return rpath.RPath(self.dest_conn, self.dest_prefix + path)

	def set_rbdir(self, rpout):
		"""Create rdiff-backup-data dir if not already, tell everyone"""
		self.rbdir = self.rpout.append('rdiff-backup-data')
		self.rpout.mkdir()
		self.rbdir.mkdir()
		SetConnections.UpdateGlobal('rbdir', self.rbdir)

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

		assert not os.system("rm -rf testfiles/output* "
							 "testfiles/restoretarget* "
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
		self.rootfiles2 = self.get_src_rp('testfiles/root2')
		self.rootfiles21 = self.get_src_rp('testfiles/root2.1')
		self.rootfiles_out2 = self.get_dest_rp('testfiles/root_output2')
		
		self.one_unreadable = self.get_src_rp('testfiles/one_unreadable')
		self.one_unreadable_out = self.get_dest_rp('testfiles/unreadable_out')

	def tearDown(self):
		print "Taking down connections"
		SetConnections.CloseConnections()


class IncrementTest1(unittest.TestCase):
	dirlist = ["testfiles/increment1", "testfiles/increment2",
			   "testfiles/increment3", "testfiles/increment4"]
	gzip_dirlist = ["testfiles/gzips/inc1", "testfiles/gzips/inc2"]

	def testLocalGzipinc(self):
		"""Local test small archive which exercises gzip options"""
		BackupRestoreSeries(1, 1, self.gzip_dirlist)

	def testRemoteBothGzipinc(self):
		"""Remote test small archive which exercises gzip options"""
		BackupRestoreSeries(None, None, self.gzip_dirlist)

	def testLocalinc(self):
		"""Test self.incrementing, and then restoring, local"""
		BackupRestoreSeries(1, 1, self.dirlist)
		
	def test_remote_src(self):
		"""Increment/Restore when source directory is remote"""
		BackupRestoreSeries(None, 1, self.dirlist)
		
	def test_remote_dest(self):
		"""Increment/Restore when target directory is remote"""
		BackupRestoreSeries(1, None, self.dirlist)		
		
	def test_remote_both(self):
		"""Increment/Restore when both directories are remote"""
		BackupRestoreSeries(None, None, self.dirlist)

	def test_long_filenames_local(self):
		"""Test backing up a directory with lots of long filenames in it"""
		Myrm(Local.rpout.path)
		InternalBackup(1, 1, "testfiles/longfilenames1", Local.rpout.path, 100)
		InternalBackup(1, 1, "testfiles/longfilenames2", Local.rpout.path, 200)

	def test_quoted_hardlinks(self):
		"""Test backing up a directory with quoted hardlinks in it"""
		hldir = rpath.RPath(Globals.local_connection,
							"testfiles/quoted_hardlinks")
		if hldir.lstat():
			Myrm(hldir.path)
			hldir.setdata()
		hldir.mkdir()
		hl1 = hldir.append("HardLink1")
		hl1.touch()
		hl2 = hldir.append("HardLink2")
		hl2.hardlink(hl1.path)
		
		Myrm(Local.rpout.path)
		old_chars = Globals.chars_to_quote
		Globals.chars_to_quote = 'A-Z'
		InternalBackup(1, 1, hldir.path, Local.rpout.path, current_time = 1)
		InternalBackup(1, 1, "testfiles/empty", Local.rpout.path,
					   current_time = 10000)
		Globals.chars_to_quote = old_chars

	def test_long_socket(self):
		"""Test backing up a directory with long sockets in them

		For some reason many unicies don't allow sockets with long
		names to be made in the usual way.

		"""
		sockdir = rpath.RPath(Globals.local_connection, "testfiles/sockettest")
		if sockdir.lstat():
			Myrm(sockdir.path)
			sockdir.setdata()
		sockdir.mkdir()
		tmp_sock = sockdir.append("sock")
		tmp_sock.mksock()
		sock1 = sockdir.append("Long_socket_name---------------------------------------------------------------------------------------------------")
		self.assertRaises(rpath.SkipFileException, sock1.mksock)
		rpath.rename(tmp_sock, sock1)
		assert sock1.issock()
		sock2 = sockdir.append("Medium_socket_name--------------------------------------------------------------")
		sock2.mksock()

		Myrm(Local.rpout.path)
		InternalBackup(1, 1, sockdir.path, Local.rpout.path,
					   current_time = 1)
		InternalBackup(1, 1, "testfiles/empty", Local.rpout.path,
					   current_time = 10000)
		
	def testNoWrite(self):
		"""Test backup/restore on dirs without write permissions"""
		def write_string(rp, s = ""):
			"""Write string s to file"""
			fp = rp.open("wb")
			fp.write(s)
			assert not fp.close()

		def make_subdirs():
			"""Make testfiles/no_write_out and testfiles/no_write_out2"""
			nw_out1 = get_local_rp("no_write_out")
			nw_out1.mkdir()

			nw_out1_1 = get_local_rp("no_write_out/1")
			write_string(nw_out1_1)
			nw_out1_1.chmod(0)

			nw_out1_2 = get_local_rp("no_write_out/2")
			write_string(nw_out1_2, 'e')
			nw_out1_1.chmod(0400)

			nw1_sub = get_local_rp("no_write_out/subdir")
			nw1_sub.mkdir()

			nw_out1_sub1 = get_local_rp("no_write_out/subdir/1")
			write_string(nw_out1_sub1, 'f')
			nw1_sub.chmod(0500)
			nw_out1.chmod(0500)

			nw_out2 = get_local_rp("no_write_out2")
			nw_out2.mkdir()

			nw_out2_1 = get_local_rp("no_write_out2/1")
			write_string(nw_out2_1, 'g')

			nw_out2_2 = get_local_rp("no_write_out2/2")
			write_string(nw_out2_2, 'aeu')
			nw_out1.chmod(0500)

		Myrm("testfiles/no_write_out")
		Myrm("testfiles/no_write_out2")
		Myrm("testfiles/output")
		make_subdirs()
		BackupRestoreSeries(1, 1, ['testfiles/no_write_out',
								   'testfiles/no_write_out2',
								   'testfiles/empty'])


class MirrorTest(PathSetter):
	"""Test some mirroring functions"""
	def testLocalMirror(self):
		"""Test Local mirroring"""
		self.setPathnames(None, None, None, None)
		self.runtest()

	def testPartialLocalMirror(self):
		"""Test updating an existing directory"""
		self.setPathnames(None, None, None, None)
		self.run_partial_test()

	def testRemoteMirror(self):
		"""Mirroring when destination is remote"""
		self.setPathnames(None, None, 'test1', '../')
		self.runtest()

	def testPartialRemoteMirror(self):
		"""Partial mirroring when destination is remote"""
		self.setPathnames(None, None, 'test1', '../')
		self.run_partial_test()

	def testSourceRemoteMirror(self):
		"""Mirroring when source is remote"""
		self.setPathnames('test2', '../', None, None)
		self.runtest()

	def testPartialSourceRemoteMirror(self):
		"""Partial Mirroring when source is remote"""
		self.setPathnames('test2', '../', None, None)
		self.run_partial_test()

	def testBothRemoteMirror(self):
		"""Mirroring when both directories are remote"""
		self.setPathnames('test1', '../', 'test2/tmp', '../../')
		self.runtest()

	def testPartialBothRemoteMirror(self):
		"""Partial mirroring when both directories are remote"""
		self.setPathnames('test1', '../', 'test2/tmp', '../../')
		self.run_partial_test()

	def testPermSkipLocal(self):
		"""Test to see if rdiff-backup will skip unreadable files"""
		self.setPathnames(None, None, None, None)
		Time.setcurtime()
		self.Mirror(self.one_unreadable, self.one_unreadable_out)
		# Could add test, but for now just make sure it doesn't exit

	def testPermSkipRemote(self):
		"""Test skip of unreadable files remote"""
		self.setPathnames('test1', '../', 'test2/tmp', '../../')
		Time.setcurtime()
		self.Mirror(self.one_unreadable, self.one_unreadable_out)
		# Could add test, but for now just make sure it doesn't exit

	def refresh(self, *rps):
		for rp in rps: rp.setdata()

	def _testRootLocal(self):
		"""Test mirroring a directory with dev files and different owners"""
		self.setPathnames(None, None, None, None)
		Globals.change_ownership = 1
		self.refresh(self.rootfiles, self.rootfiles_out,
				Local.rootfiles, Local.rootfiles_out) # add uid/gid info
		backup.Mirror(self.rootfiles, self.rootfiles_out)
		assert CompareRecursive(Local.rootfiles, Local.rootfiles_out)
		Globals.change_ownership = None
		self.refresh(self.rootfiles, self.rootfiles_out,
				Local.rootfiles, Local.rootfiles_out) # remove that info

	def _testRootRemote(self):
		"""Mirroring root files both ends remote"""
		self.setPathnames('test1', '../', 'test2/tmp', '../../')
		for conn in Globals.connections:
			conn.Globals.set('change_ownership', 1)
		self.refresh(self.rootfiles, self.rootfiles_out,
				Local.rootfiles, Local.rootfiles_out) # add uid/gid info
		backup.Mirror(self.rootfiles, self.rootfiles_out)
		assert CompareRecursive(Local.rootfiles, Local.rootfiles_out)
		for coon in Globals.connections:
			conn.Globals.set('change_ownership', None)
		self.refresh(self.rootfiles, self.rootfiles_out,
				Local.rootfiles, Local.rootfiles_out) # remove that info

	def deleteoutput(self):
		assert not os.system("rm -rf testfiles/output*")
		self.rbdir = self.rpout.append('rdiff-backup-data')
		self.reset_rps()

	def reset_rps(self):
		"""Use after external changes made, to update the rps"""
		for rp in [self.rpout, Local.rpout,
				   self.rpout_inc, Local.rpout_inc,
				   self.rpout1, Local.rpout1,
				   self.rpout2, Local.rpout2,
				   self.rpout3, Local.rpout3,
				   self.rpout4, Local.rpout4]:
			rp.setdata()
		
	def runtest(self):
		self.deleteoutput()
		Time.setcurtime()
		assert not self.rbdir.lstat()
		self.Mirror(self.inc1rp, self.rpout)
		assert CompareRecursive(Local.inc1rp, Local.rpout)

		self.deleteoutput()

		self.Mirror(self.inc2rp, self.rpout)
		assert CompareRecursive(Local.inc2rp, Local.rpout)

	def run_partial_test(self):
		assert not os.system("rm -rf testfiles/output")
		assert not os.system("cp -a testfiles/increment3 testfiles/output")
		self.reset_rps()

		Time.setcurtime()
		self.Mirror(self.inc1rp, self.rpout)
		#rpath.RPath.copy_attribs(self.inc1rp, self.rpout)
		assert CompareRecursive(Local.inc1rp, Local.rpout)
		Myrm(Local.rpout.append("rdiff-backup-data").path)

		self.Mirror(self.inc2rp, self.rpout)
		assert CompareRecursive(Local.inc2rp, Local.rpout)

	def Mirror(self, rpin, rpout):
		"""Like backup.Mirror, but setup first, cleanup later"""
		Main.force = 1
		assert not rpout.append("rdiff-backup-data").lstat()
		Main.misc_setup([rpin, rpout])
		Main.backup_check_dirs(rpin, rpout)
		Main.backup_set_rbdir(rpin, rpout)
		Main.backup_set_fs_globals(rpin, rpout)
		Main.backup_final_init(rpout)
		Main.backup_set_select(rpin)
		backup.Mirror(rpin, rpout)
		log.ErrorLog.close()
		log.Log.close_logfile()
		Hardlink.clear_dictionaries()

if __name__ == "__main__": unittest.main()
