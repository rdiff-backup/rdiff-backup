#!/usr/bin/env python3

import unittest
import io
import sys
import os
from commontest import abs_test_dir, re_init_rpath_dir, Myrm, \
    abs_output_dir, rdiff_backup, abs_testing_dir, MakeOutputDir
from rdiff_backup import hash, rpath, Globals, Security, SetConnections
from rdiffbackup.meta import stdattr


class HashTest(unittest.TestCase):
    """Test the hash module"""
    s1 = "Hello, world!"
    s1_hash = "943a702d06f34599aee1f8da8ef9f7296031d699"
    s2 = "The quick brown dog jumped over the lazy fox"
    s2_hash = "eab21fb1a18b408909bae552b847f6b13f370f62"
    s3 = "foobar"
    s3_hash = "8843d7f92416211de9ebb963ff4ce28125932878"

    root_rp = rpath.RPath(Globals.local_connection, abs_test_dir)

    def test_basic(self):
        """Compare sha1sum of a few strings"""
        b1 = self.s1.encode()
        sfile = io.BytesIO(b1)
        fw = hash.FileWrapper(sfile)
        self.assertEqual(fw.read(), b1)
        report = fw.close()
        self.assertEqual(report.sha1_digest, self.s1_hash)

        sfile2 = io.BytesIO(b1)
        fw2 = hash.FileWrapper(sfile2)
        self.assertEqual(fw2.read(5), b1[:5])
        self.assertEqual(fw2.read(), b1[5:])
        report2 = fw2.close()
        self.assertEqual(report2.sha1_digest, self.s1_hash)

    def make_dirs(self):
        """Make two input directories"""
        d1 = self.root_rp.append("hashtest1")
        re_init_rpath_dir(d1)
        d2 = self.root_rp.append("hashtest2")
        re_init_rpath_dir(d2)

        d1f1 = d1.append("file1")
        d1f1.write_string(self.s1)
        d1f1l = d1.append("file1_linked")
        d1f1l.hardlink(d1f1.path)

        d1f2 = d1.append("file2")
        d1f2.write_string(self.s2)
        d1f2l = d1.append("file2_linked")
        d1f2l.hardlink(d1f2.path)

        d1_hashlist = [
            None, self.s1_hash, self.s1_hash, self.s2_hash, self.s2_hash
        ]

        d2f1 = d2.append("file1")
        rpath.copy_with_attribs(d1f1, d2f1)
        d2f1l = d2.append("file1_linked")
        d2f1l.write_string(self.s3)

        d1f2 = d2.append("file2")
        d1f2.mkdir()

        d2_hashlist = [None, self.s1_hash, self.s3_hash, None]

        return (d1, d1_hashlist, d2, d2_hashlist)

    def extract_hashs(self, metadata_rp):
        """Return list of hashes in the metadata_rp"""
        result = []
        comp = metadata_rp.isinccompressed()
        extractor = stdattr.AttrExtractor(metadata_rp.open("r", comp))
        for rorp in extractor.iterate():
            if rorp.has_sha1():
                result.append(rorp.get_sha1())
            else:
                result.append(None)
        return result

    @unittest.skip(
        "Skipping until hash of hard links is fixed, see issue #23.")
    def test_session(self):
        """Run actual sessions and make sure proper hashes recorded

        There are a few code paths here we need to test:  creating
        ordinary files, updating ordinary files with diffs, hard
        linking, and keeping files the same.

        """
        in_rp1, hashlist1, in_rp2, hashlist2 = self.make_dirs()
        Myrm(abs_output_dir)

        rdiff_backup(1, 1, in_rp1.path, abs_output_dir, 10000)
        meta_prefix = rpath.RPath(
            Globals.local_connection,
            os.path.join(abs_output_dir, b"rdiff-backup-data",
                         b"mirror_metadata"))
        incs = meta_prefix.get_incfiles_list()
        self.assertEqual(len(incs), 1)
        metadata_rp = incs[0]
        hashlist = self.extract_hashs(metadata_rp)
        self.assertEqual(hashlist, hashlist1)

        rdiff_backup(1, 1, in_rp2.path, abs_output_dir, 20000)
        incs = meta_prefix.get_incfiles_list()
        self.assertEqual(len(incs), 2)
        if incs[0].getinctype() == 'snapshot':
            inc = incs[0]
        else:
            inc = incs[1]
        hashlist = self.extract_hashs(inc)
        self.assertEqual(hashlist, hashlist2)

    def test_rorpiter_xfer(self):
        """Test if hashes are transferred in files, rorpiter"""
        Security._security_level = "override"
        conn = SetConnections._init_connection(
            b'%b %b/server.py' %
            (os.fsencode(sys.executable), abs_testing_dir))
        # make a connection sanity check
        self.assertEqual(conn.reval("lambda x: x+1", 4), 5)

        fp = hash.FileWrapper(io.BytesIO(self.s1.encode()))
        conn.Globals.set('tmp_file', fp)
        fp_remote = conn.Globals.get('tmp_file')
        self.assertEqual(fp_remote.read(), self.s1.encode())
        self.assertEqual(fp_remote.close().sha1_digest, self.s1_hash)

        # Tested xfer of file, now test xfer of files in rorpiter
        root = MakeOutputDir()
        rp1 = root.append('s1')
        rp1.write_string(self.s1)
        rp2 = root.append('s2')
        rp2.write_string(self.s2)
        rp1.setfile(hash.FileWrapper(rp1.open('rb')))
        rp2.setfile(hash.FileWrapper(rp2.open('rb')))
        rpiter = iter([rp1, rp2])

        conn.Globals.set('tmp_conn_iter', rpiter)
        remote_iter = conn.Globals.get('tmp_conn_iter')

        rorp1 = next(remote_iter)
        fp = hash.FileWrapper(rorp1.open('rb'))
        read_s1 = fp.read().decode()
        self.assertEqual(read_s1, self.s1)
        ret_val = fp.close()
        self.assertIsInstance(ret_val, hash.Report)
        self.assertEqual(ret_val.sha1_digest, self.s1_hash)
        rorp2 = next(remote_iter)
        fp2 = hash.FileWrapper(rorp2.open('rb'))
        read_s2 = fp2.read().decode()
        self.assertEqual(read_s2, self.s2)
        self.assertEqual(fp2.close().sha1_digest, self.s2_hash)

        conn.quit()


if __name__ == "__main__":
    unittest.main()
