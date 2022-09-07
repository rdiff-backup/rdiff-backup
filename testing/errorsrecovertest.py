import unittest
from commontest import abs_test_dir, re_init_rpath_dir, rdiff_backup
from rdiff_backup import rpath, Globals

# This testing file is meant for tests based on errors introduced by
# earlier versions of rdiff-backup and how newer versions are able to cope
# with those.


class BrokenRepoTest(unittest.TestCase):
    """Handling of somehow broken repos"""
    def makerp(self, path):
        return rpath.RPath(Globals.local_connection, path)

    def makeext(self, path):
        return self.root.new_index(tuple(path.split("/")))

    def testDuplicateMetadataTimestamp(self):
        """This test is based on issue #322 where a diff and a snapshot
        metadata mirror files had the same timestamp, which made rdiff-backup
        choke. We check that rdiff-backup still fails by default but can be
        taught to ignore the error with --allow-duplicate-timestamps so that
        the repo can be fixed."""

        # create an empty directory
        test_base_rp = self.makerp(abs_test_dir).append("dupl_meta_time")
        re_init_rpath_dir(test_base_rp)

        # create enough incremental backups to have one metadata snapshot
        # in-between, which we can manipulate to simulate the error
        source_rp = test_base_rp.append("source")
        target_rp = test_base_rp.append("target")
        source_rp.mkdir()
        for suffix in range(1, 15):
            source_rp.append("file%02d" % suffix).touch()
            rdiff_backup(1, 1, source_rp.__fspath__(), target_rp.__fspath__(),
                         current_time=suffix * 10000)
        # identify the oldest (aka first) mirror metadata snapshot
        # and sort the list because some filesystems don't respect the order
        rb_data_rp = target_rp.append("rdiff-backup-data")
        files_list = sorted(filter(
            lambda x: x.startswith(b"mirror_metadata."),
            rb_data_rp.listdir()))
        meta_snapshot_rp = rb_data_rp.append(files_list[8])
        # create a diff with the same data as the identified snapshot
        meta_dupldiff_rp = rb_data_rp.append(files_list[8].replace(
            b".snapshot.gz", b".diff.gz"))
        rpath.copy(meta_snapshot_rp, meta_dupldiff_rp)

        # this succeeds
        rdiff_backup(1, 1, target_rp.__fspath__(), None,
                     extra_options=b"--check-destination-dir")
        # now this should fail
        source_rp.append("file15").touch()
        rdiff_backup(1, 1, source_rp.__fspath__(), target_rp.__fspath__(),
                     current_time=15 * 10000,
                     expected_ret_code=Globals.RET_CODE_ERR)
        # and this should also fail
        rdiff_backup(1, 1, target_rp.__fspath__(), None,
                     expected_ret_code=Globals.RET_CODE_ERR,
                     extra_options=b"--check-destination-dir")
        # but this should succeed (with a warning)
        rdiff_backup(1, 1, target_rp.__fspath__(), None,
                     extra_options=b"--allow-duplicate-timestamps --check-destination-dir",
                     expected_ret_code=Globals.RET_CODE_WARN)
        # now we can clean-up, getting rid of the duplicate metadata mirrors
        # NOTE: we could have cleaned-up even without checking/fixing the directory
        #       but this shouldn't be the recommended practice.
        rdiff_backup(1, 1, target_rp.__fspath__(), None,
                     extra_options=b"--remove-older-than 100000 --force")
        # and this should at last succeed
        source_rp.append("file16").touch()
        rdiff_backup(1, 1, source_rp.__fspath__(), target_rp.__fspath__(),
                     current_time=16 * 10000)


if __name__ == "__main__":
    unittest.main()
