import unittest
import pwd
import code
from rdiff_backup import user_group, Globals


class UserGroupTest(unittest.TestCase):
    """Test user and group functionality"""

    def test_basic_conversion(self):
        """Test basic id2name.  May need to modify for different systems"""
        user_group.uid2uname_dict = {}
        user_group.gid2gname_dict = {}
        assert user_group.uid2uname(0) == "root"
        assert user_group.uid2uname(0) == "root"
        assert user_group.gid2gname(0) == "root"
        assert user_group.gid2gname(0) == "root"
        # Assume no user has uid 29378
        assert user_group.gid2gname(29378) is None
        assert user_group.gid2gname(29378) is None

    def test_basic_reverse(self):
        """Test basic name2id.  Depends on systems users/groups"""
        user_group.uname2uid_dict = {}
        user_group.gname2gid_dict = {}
        assert user_group.uname2uid("root") == 0
        assert user_group.uname2uid("root") == 0
        assert user_group.gname2gid("root") == 0
        assert user_group.gname2gid("root") == 0
        assert user_group.uname2uid("aoeuth3t2ug89") is None
        assert user_group.uname2uid("aoeuth3t2ug89") is None

    def test_default_mapping(self):
        """Test the default user mapping"""
        Globals.isdest = 1
        rootid = 0
        binid = pwd.getpwnam('bin')[2]
        syncid = pwd.getpwnam('sync')[2]
        user_group.init_user_mapping()
        assert user_group.UserMap(0) == rootid
        assert user_group.UserMap(0, 'bin') == binid
        assert user_group.UserMap(0, 'sync') == syncid
        assert user_group.UserMap.map_acl(0, 'aoeuth3t2ug89') is None

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

        assert user_group.UserMap(rootid, 'root') == binid
        assert user_group.UserMap(binid, 'bin') == rootid
        assert user_group.UserMap(0) == syncid
        assert user_group.UserMap(syncid, 'sync') == 0
        assert user_group.UserMap(500) == 501

        assert user_group.UserMap(501) == 501
        assert user_group.UserMap(123, 'daemon') == daemonid

        assert user_group.UserMap.map_acl(29378, 'aoeuth3t2ug89') is None
        assert user_group.UserMap.map_acl(0, 'aoeuth3t2ug89') is syncid

        if 0:
            code.InteractiveConsole(globals()).interact()

    def test_overflow(self):
        """Make sure querying large uids/gids doesn't raise exception"""
        large_num = 4000000000
        assert user_group.uid2uname(large_num) is None
        assert user_group.gid2gname(large_num) is None


if __name__ == "__main__":
    unittest.main()
