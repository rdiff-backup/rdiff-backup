import os, unittest
from commontest import *
import rdiff_backup.Security

#Log.setverbosity(5)

class SecurityTest(unittest.TestCase):
	def assert_exc_sec(self, exc):
		"""Fudge - make sure exception is a security violation

		This is necessary because of some kind of pickling/module
		problem.

		"""
		assert isinstance(exc, rdiff_backup.Security.Violation)
		#assert str(exc).find("Security") >= 0, "%s\n%s" % (exc, repr(exc))

	def test_vet_request_ro(self):
		"""Test vetting of ConnectionRequests on read-only server"""
		remote_cmd = "rdiff-backup --server --restrict-read-only foo"
		conn = SetConnections.init_connection(remote_cmd)
		assert type(conn.os.getuid()) is type(5)
		try: conn.os.remove("/tmp/foobar")
		except Exception, e: self.assert_exc_sec(e)
		else: assert 0, "No exception raised"
		SetConnections.CloseConnections()

	def test_vet_request_minimal(self):
		"""Test vetting of ConnectionRequests on minimal server"""
		remote_cmd = "rdiff-backup --server --restrict-update-only foo"
		conn = SetConnections.init_connection(remote_cmd)
		assert type(conn.os.getuid()) is type(5)
		try: conn.os.remove("/tmp/foobar")
		except Exception, e: self.assert_exc_sec(e)
		else: assert 0, "No exception raised"
		SetConnections.CloseConnections()

	def test_vet_rpath(self):
		"""Test to make sure rpaths not in restricted path will be rejected"""
		remote_cmd = "rdiff-backup --server --restrict-update-only foo"
		conn = SetConnections.init_connection(remote_cmd)

		for rp in [RPath(Globals.local_connection, "blahblah"),
				   RPath(conn, "foo/bar")]:
			conn.Globals.set("TEST_var", rp)
			assert conn.Globals.get("TEST_var").path == rp.path

		for rp in [RPath(conn, "foobar"),
				   RPath(conn, "/usr/local"),
				   RPath(conn, "foo/../bar")]:
			try: conn.Globals.set("TEST_var", rp)
			except Exception, e:
				self.assert_exc_sec(e)
				continue
			assert 0, "No violation raised by rp %s" % (rp,)

		SetConnections.CloseConnections()

if __name__ == "__main__": unittest.main()
		
