import os, unittest, time
from commontest import *
import rdiff_backup.Security as Security

#Log.setverbosity(5)

class SecurityTest(unittest.TestCase):
	def assert_exc_sec(self, exc):
		"""Fudge - make sure exception is a security violation

		This is necessary because of some kind of pickling/module
		problem.

		"""
		assert isinstance(exc, Security.Violation), exc
		#assert str(exc).find("Security") >= 0, "%s\n%s" % (exc, repr(exc))

	def test_vet_request_ro(self):
		"""Test vetting of ConnectionRequests on read-only server"""
		remote_cmd = "../rdiff-backup --server --restrict-read-only foo"
		conn = SetConnections.init_connection(remote_cmd)
		assert type(conn.os.getuid()) is type(5)
		try: conn.os.remove("/tmp/foobar")
		except Exception, e: self.assert_exc_sec(e)
		else: assert 0, "No exception raised"
		SetConnections.CloseConnections()

	def test_vet_request_minimal(self):
		"""Test vetting of ConnectionRequests on minimal server"""
		remote_cmd = "../rdiff-backup --server --restrict-update-only foo"
		conn = SetConnections.init_connection(remote_cmd)
		assert type(conn.os.getuid()) is type(5)
		try: conn.os.remove("/tmp/foobar")
		except Exception, e: self.assert_exc_sec(e)
		else: assert 0, "No exception raised"
		SetConnections.CloseConnections()

	def test_vet_rpath(self):
		"""Test to make sure rpaths not in restricted path will be rejected"""
		remote_cmd = "../rdiff-backup --server --restrict-update-only foo"
		conn = SetConnections.init_connection(remote_cmd)

		for rp in [RPath(Globals.local_connection, "blahblah"),
				   RPath(conn, "foo/bar")]:
			conn.Globals.set("TEST_var", rp)
			assert conn.Globals.get("TEST_var").path == rp.path

		for path in ["foobar", "/usr/local", "foo/../bar"]:
			try:
				rp = rpath.RPath(conn, path)
				conn.Globals.set("TEST_var", rp)
			except Exception, e:
				self.assert_exc_sec(e)
				continue
			assert 0, "No violation raised by rp %s" % (rp,)
			
		SetConnections.CloseConnections()

	def test_vet_rpath_root(self):
		"""Test vetting when restricted to root"""
		remote_cmd = "../rdiff-backup --server --restrict-update-only /"
		conn = SetConnections.init_connection(remote_cmd)
		for rp in [RPath(Globals.local_connection, "blahblah"),
				   RPath(conn, "foo/bar")]:
			conn.Globals.set("TEST_var", rp)
			assert conn.Globals.get("TEST_var").path == rp.path
		SetConnections.CloseConnections()

	def secure_rdiff_backup(self, in_dir, out_dir, in_local, restrict_args,
							extra_args = "", success = 1, current_time = None):
		"""Run rdiff-backup locally, with given restrict settings"""
		if not current_time: current_time = int(time.time())
		prefix = ('rdiff-backup --current-time %s ' % (current_time,) +
				  '--remote-schema %s ')

		if in_local: out_dir = ("'rdiff-backup %s --server'::%s" %
								(restrict_args, out_dir))
		else: in_dir = ("'rdiff-backup %s --server'::%s" %
						(restrict_args, in_dir))

		cmdline = "%s %s %s %s" % (prefix, extra_args, in_dir, out_dir)
		print "Executing:", cmdline
		exit_val = os.system(cmdline)
		if success: assert not exit_val
		else: assert exit_val, "Success when wanted failure"

	def test_restrict_positive(self):
		"""Test that --restrict switch doesn't get in the way

		This makes sure that basic backups with the restrict operator
		work, (initial backup, incremental, restore).

		"""
		Myrm("testfiles/output")
		self.secure_rdiff_backup('testfiles/various_file_types',
								 'testfiles/output', 1,
								 '--restrict testfiles/output',
								 current_time = 10000)
		# Note the backslash below -- test for bug in path normalization
		self.secure_rdiff_backup('testfiles/various_file_types',
								 'testfiles/output', 1,
								 '--restrict testfiles/output/')

		Myrm("testfiles/restore_out")
		self.secure_rdiff_backup('testfiles/output',
								 'testfiles/restore_out', 1,
								 '--restrict testfiles/restore_out',
								 extra_args = '-r now')

	def test_restrict_negative(self):
		"""Test that --restrict switch denies certain operations"""
		# Backup to wrong directory
		Myrm("testfiles/output testfiles/output2")
		self.secure_rdiff_backup('testfiles/various_file_types',
								 'testfiles/output2', 1,
								 '--restrict testfiles/output',
								 success = 0)

		# Restore to wrong directory
		Myrm("testfiles/output testfiles/restore_out")
		rdiff_backup(1, 1, 'testfiles/various_file_types',
					 'testfiles/output')
		self.secure_rdiff_backup('testfiles/output',
								 'testfiles/restore_out', 1,
								 '--restrict testfiles/output2',
								 extra_args = '-r now',
								 success = 0)

		# Backup from wrong directory
		Myrm("testfiles/output")
		self.secure_rdiff_backup('testfiles/various_file_types',
								 'testfiles/output', 0,
								 '--restrict testfiles/foobar',
								 success = 0)

	def test_restrict_readonly_positive(self):
		"""Test that --restrict-read-only switch doesn't impair normal ops"""
		Myrm("testfiles/output testfiles/restore_out")
		self.secure_rdiff_backup('testfiles/various_file_types',
								 'testfiles/output', 0,
						   '--restrict-read-only testfiles/various_file_types')
								 
		self.secure_rdiff_backup('testfiles/output',
								 'testfiles/restore_out', 0,
								 '--restrict-read-only testfiles/output',
								 extra_args = '-r now')

	def test_restrict_readonly_negative(self):
		"""Test that --restrict-read-only doesn't allow too much"""
		# Backup to restricted directory
		Myrm('testfiles/output')
		self.secure_rdiff_backup('testfiles/various_file_types',
								 'testfiles/output', 1,
								 '--restrict-read-only testfiles/output',
								 success = 0)

		# Restore to restricted directory
		Myrm('testfiles/output testfiles/restore_out')
		rdiff_backup(1, 1, 'testfiles/various_file_types', 'testfiles/output')
		self.secure_rdiff_backup('testfiles/output',
								 'testfiles/restore_out', 1,
								 '--restrict-read-only testfiles/restore_out',
								 extra_args = '-r now',
								 success = 0)

	def test_restrict_updateonly_positive(self):
		"""Test that --restrict-update-only allows intended use"""
		Myrm('testfiles/output')
		rdiff_backup(1, 1, 'testfiles/various_file_types', 'testfiles/output',
					 current_time = 10000)
		self.secure_rdiff_backup('testfiles/various_file_types',
								 'testfiles/output', 1,
								 '--restrict-update-only testfiles/output')

	def test_restrict_updateonly_negative(self):
		"""Test that --restrict-update-only impairs unintended"""
		Myrm('testfiles/output')
		self.secure_rdiff_backup('testfiles/various_file_types',
								 'testfiles/output', 1,
								 '--restrict-update-only testfiles/output',
								 success = 0)

		Myrm('testfiles/output testfiles/restore_out')
		rdiff_backup(1, 1, 'testfiles/various_file_types', 'testfiles/output')
		self.secure_rdiff_backup('testfiles/output',
								 'testfiles/restore_out', 1,
							   '--restrict-update-only testfiles/restore_out',
								 extra_args = '-r now',
								 success = 0)


if __name__ == "__main__": unittest.main()
		
