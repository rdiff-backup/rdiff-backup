import unittest
import pwd
import code
from rdiff_backup import Globals
from rdiffbackup.utils import usrgrp
from rdiffbackup.locations.map import owners as map_owners


class UserGroupTest(unittest.TestCase):
    """Test user and group functionality"""

    def test_basic_conversion(self):
        """Test basic id2name.  May need to modify for different systems"""
        usrgrp._uid2uname = {}
        usrgrp._gid2gname = {}
        self.assertEqual(usrgrp.uid2uname(0), "root")
        self.assertEqual(usrgrp.uid2uname(0), "root")
        self.assertEqual(usrgrp.gid2gname(0), "root")
        self.assertEqual(usrgrp.gid2gname(0), "root")
        # Assume no user has uid 29378
        self.assertIsNone(usrgrp.gid2gname(29378))
        self.assertIsNone(usrgrp.gid2gname(29378))

    def test_basic_reverse(self):
        """Test basic name2id.  Depends on systems users/groups"""
        usrgrp._uname2uid = {}
        usrgrp._gname2gid = {}
        self.assertEqual(usrgrp.uname2uid("root"), 0)
        self.assertEqual(usrgrp.uname2uid("root"), 0)
        self.assertEqual(usrgrp.gname2gid("root"), 0)
        self.assertEqual(usrgrp.gname2gid("root"), 0)
        self.assertIsNone(usrgrp.uname2uid("aoeuth3t2ug89"))
        self.assertIsNone(usrgrp.uname2uid("aoeuth3t2ug89"))

    def test_default_mapping(self):
        """Test the default user mapping"""
        Globals.isdest = 1
        rootid = 0
        binid = pwd.getpwnam('bin')[2]
        syncid = pwd.getpwnam('sync')[2]
        map_owners.init_users_mapping()
        self.assertEqual(map_owners._user_map(0), rootid)
        self.assertEqual(map_owners._user_map(0, 'bin'), binid)
        self.assertEqual(map_owners._user_map(0, 'sync'), syncid)
        self.assertIsNone(map_owners._user_map.map_acl(0, 'aoeuth3t2ug89'))

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
        map_owners.init_users_mapping(mapping_string)

        self.assertEqual(map_owners._user_map(rootid, 'root'), binid)
        self.assertEqual(map_owners._user_map(binid, 'bin'), rootid)
        self.assertEqual(map_owners._user_map(0), syncid)
        self.assertEqual(map_owners._user_map(syncid, 'sync'), 0)
        self.assertEqual(map_owners._user_map(500), 501)

        self.assertEqual(map_owners._user_map(501), 501)
        self.assertEqual(map_owners._user_map(123, 'daemon'), daemonid)

        self.assertIsNone(map_owners._user_map.map_acl(29378, 'aoeuth3t2ug89'))
        self.assertIs(map_owners._user_map.map_acl(0, 'aoeuth3t2ug89'), syncid)

        if 0:
            code.InteractiveConsole(globals()).interact()

    def test_overflow(self):
        """Make sure querying large uids/gids doesn't raise exception"""
        large_num = 4000000000
        self.assertIsNone(usrgrp.uid2uname(large_num))
        self.assertIsNone(usrgrp.gid2gname(large_num))


if __name__ == "__main__":
    unittest.main()
