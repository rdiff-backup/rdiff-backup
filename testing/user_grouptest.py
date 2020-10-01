import unittest
import pwd
import code
from rdiff_backup import user_group, Globals


class UserGroupTest(unittest.TestCase):
    """Test user and group functionality"""

    def test_basic_conversion(self):
        """Test basic id2name.  May need to modify for different systems"""
        user_group._uid2uname_dict = {}
        user_group._gid2gname_dict = {}
        self.assertEqual(user_group.uid2uname(0), "root")
        self.assertEqual(user_group.uid2uname(0), "root")
        self.assertEqual(user_group.gid2gname(0), "root")
        self.assertEqual(user_group.gid2gname(0), "root")
        # Assume no user has uid 29378
        self.assertIsNone(user_group.gid2gname(29378))
        self.assertIsNone(user_group.gid2gname(29378))

    def test_basic_reverse(self):
        """Test basic name2id.  Depends on systems users/groups"""
        user_group._uname2uid_dict = {}
        user_group._gname2gid_dict = {}
        self.assertEqual(user_group._uname2uid("root"), 0)
        self.assertEqual(user_group._uname2uid("root"), 0)
        self.assertEqual(user_group._gname2gid("root"), 0)
        self.assertEqual(user_group._gname2gid("root"), 0)
        self.assertIsNone(user_group._uname2uid("aoeuth3t2ug89"))
        self.assertIsNone(user_group._uname2uid("aoeuth3t2ug89"))

    def test_default_mapping(self):
        """Test the default user mapping"""
        Globals.isdest = 1
        rootid = 0
        binid = pwd.getpwnam('bin')[2]
        syncid = pwd.getpwnam('sync')[2]
        user_group.init_user_mapping()
        self.assertEqual(user_group._user_map(0), rootid)
        self.assertEqual(user_group._user_map(0, 'bin'), binid)
        self.assertEqual(user_group._user_map(0, 'sync'), syncid)
        self.assertIsNone(user_group._user_map.map_acl(0, 'aoeuth3t2ug89'))

    def test_user_mapping(self):
        """Test the user mapping file through the _DefinedMap class"""
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

        self.assertEqual(user_group._user_map(rootid, 'root'), binid)
        self.assertEqual(user_group._user_map(binid, 'bin'), rootid)
        self.assertEqual(user_group._user_map(0), syncid)
        self.assertEqual(user_group._user_map(syncid, 'sync'), 0)
        self.assertEqual(user_group._user_map(500), 501)

        self.assertEqual(user_group._user_map(501), 501)
        self.assertEqual(user_group._user_map(123, 'daemon'), daemonid)

        self.assertIsNone(user_group._user_map.map_acl(29378, 'aoeuth3t2ug89'))
        self.assertIs(user_group._user_map.map_acl(0, 'aoeuth3t2ug89'), syncid)

        if 0:
            code.InteractiveConsole(globals()).interact()

    def test_overflow(self):
        """Make sure querying large uids/gids doesn't raise exception"""
        large_num = 4000000000
        self.assertIsNone(user_group.uid2uname(large_num))
        self.assertIsNone(user_group.gid2gname(large_num))


if __name__ == "__main__":
    unittest.main()
