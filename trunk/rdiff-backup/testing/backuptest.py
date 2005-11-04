import unittest
from commontest import *
from rdiff_backup import Globals, SetConnections, user_group

class RemoteMirrorTest(unittest.TestCase):
	"""Test mirroring"""
	def setUp(self):
		"""Start server"""
		Log.setverbosity(5)
		Globals.change_source_perms = 1
		SetConnections.UpdateGlobal('checkpoint_interval', 3)
		user_group.init_user_mapping()
		user_group.init_group_mapping()

	def testMirror(self):
		"""Testing simple mirror"""
		MirrorTest(None, None, ["testfiles/increment1"])

	def testMirror2(self):
		"""Test mirror with larger data set"""
		MirrorTest(1, None, ['testfiles/increment1', 'testfiles/increment2',
							 'testfiles/increment3', 'testfiles/increment4'])

	def testMirror3(self):
		"""Local version of testMirror2"""
		MirrorTest(1, 1, ['testfiles/increment1', 'testfiles/increment2',
						  'testfiles/increment3', 'testfiles/increment4'])


if __name__ == "__main__": unittest.main()
