import unittest

execfile("commontest.py")
rbexec("main.py")


class RemoteMirrorTest(unittest.TestCase):
	"""Test mirroring"""
	def setUp(self):
		"""Start server"""
		Log.setverbosity(5)
		Globals.change_source_perms = 1
		SetConnections.UpdateGlobal('checkpoint_interval', 3)

	def testMirror(self):
		"""Testing simple mirror"""
		MirrorTest(None, None, ["testfiles/increment1"])

	def testMirror2(self):
		"""Test mirror with larger data set"""
		MirrorTest(1, None, ['testfiles/increment1', 'testfiles/increment2',
							 'testfiles/increment3', 'testfiles/increment4'])

	def testMirrorWithCheckpointing(self):
		"""Like testMirror but this time checkpoint"""
		MirrorTest(None, None, ["testfiles/increment1"], 1)

	def testMirrorWithCheckpointing2(self):
		"""Larger data set"""
		MirrorTest(1, None, ['testfiles/increment1', 'testfiles/increment2',
							 'testfiles/increment3', 'testfiles/increment4'],
				   1)



if __name__ == "__main__": unittest.main()
