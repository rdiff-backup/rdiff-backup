import unittest, pwd, grp, code
from commontest import *
from rdiff_backup import user_group


class UserGroupTest(unittest.TestCase):
	"""Test user and group functionality"""
	def test_basic_conversion(self):
		"""Test basic id2name.  May need to modify for different systems"""
		user_group.uid2uname_dict = {}; user_group.gid2gname_dict = {}
		assert user_group.uid2uname(0) == "root"
		assert user_group.uid2uname(0) == "root"
		assert user_group.gid2gname(0) == "root"
		assert user_group.gid2gname(0) == "root"

	def test_default_mapping(self):
		"""Test the default user mapping"""
		Globals.isdest = 1
		rootid = 0
		binid = pwd.getpwnam('bin')[2]
		syncid = pwd.getpwnam('sync')[2]
		user_group.init_user_mapping()
		assert user_group.UserMap.get_id(0) == 0
		assert user_group.UserMap.get_id(0, 'bin') == binid
		assert user_group.UserMap.get_id(binid, 'sync') == syncid

	def test_user_mapping(self):
		"""Test the user mapping file through the DefinedMap class"""
		mapping_string = """
root:bin
bin:root
500:501
0:sync
sync:0"""
		Globals.isdest = 1
		rootid = 0
		binid = pwd.getpwnam('bin')[2]
		syncid = pwd.getpwnam('sync')[2]
		daemonid = pwd.getpwnam('daemon')[2]
		user_group.init_user_mapping(mapping_string)

		assert user_group.UserMap.get_id(rootid, 'root') == binid
		assert user_group.UserMap.get_id(binid, 'bin') == rootid
		assert user_group.UserMap.get_id(0) == syncid
		assert user_group.UserMap.get_id(syncid, 'sync') == 0
		assert user_group.UserMap.get_id(500) == 501

		assert user_group.UserMap.get_id(501) == 501
		assert user_group.UserMap.get_id(123, 'daemon') == daemonid
		
		if 0: code.InteractiveConsole(globals()).interact()
			   
		

if __name__ == "__main__": unittest.main()
